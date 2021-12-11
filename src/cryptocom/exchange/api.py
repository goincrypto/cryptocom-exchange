import os
import json
import time
import hmac
import random
import asyncio
import hashlib

from urllib.parse import urljoin
from aiolimiter import AsyncLimiter


import aiohttp
import async_timeout

from aiohttp.client_exceptions import ContentTypeError


RATE_LIMITS = {
    # order methods
    (
        'private/create-order',
        'private/cancel-order',
        'private/cancel-all-orders',
        'private/margin/create-order',
        'private/margin/cancel-order',
        'private/margin/cancel-all-orders',
    ): (14, 0.1),

    # order detail methods
    (
        'private/get-order-detail',
        'private/margin/get-order-detail',
    ): (29, 0.1),

    # general trade methods
    (
        'private/get-trades',
        'private/margin/get-trades',
        'private/get-order-history',
        'private/margin/get-order-history'
    ): (1, 1)
}


class ApiError(Exception):
    pass


class ApiProvider:
    """Provides HTTP-api requests and websocket requests."""
    def __init__(
            self, *, api_key='', api_secret='', from_env=False,
            auth_required=True, timeout=25, retries=6,
            root_url='https://api.crypto.com/v2/',
            ws_root_url='wss://stream.crypto.com/v2/', logger=None):

        self.api_key = api_key
        self.api_secret = api_secret
        self.root_url = root_url
        self.ws_root_url = ws_root_url
        self.timeout = timeout
        self.retries = retries
        self.last_request_path = ''

        self.rate_limiters = {}

        for urls in RATE_LIMITS:
            for url in urls:
                self.rate_limiters[url] = AsyncLimiter(*RATE_LIMITS[urls])

        # limits for not matched methods
        self.general_private_limit = AsyncLimiter(3, 0.1)
        self.general_public_limit = AsyncLimiter(100, 1)

        if not auth_required:
            return

        if from_env:
            self.read_keys_from_env()

        if not self.api_key or not self.api_secret:
            raise ValueError('Provide api_key and api_secret')

    def read_keys_from_env(self):
        self.api_key = os.environ.get('CRYPTOCOM_API_KEY', '')
        if not self.api_key:
            raise ValueError('Provide CRYPTOCOM_API_KEY env value')
        self.api_secret = os.environ.get('CRYPTOCOM_API_SECRET', '')
        if not self.api_secret:
            raise ValueError('Provide CRYPTOCOM_API_SECRET env value')

    def _sign(self, path, data):
        data = data or {}
        data['method'] = path

        sign_time = int(time.time() * 1000)
        data.update({'nonce': sign_time, 'api_key': self.api_key})

        data['id'] = random.randint(1000, 10000)
        data_params = data.get('params', {})
        params = ''.join(
            f'{key}{data_params[key]}'
            for key in sorted(data_params)
        )

        payload = f"{path}{data['id']}" \
            f"{self.api_key}{params}{data['nonce']}"

        data['sig'] = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return data

    def get_limit(self, path):
        if path in self.rate_limiters.keys():
            return self.rate_limiters[path]
        else:
            if path.startswith('private'):
                return self.general_private_limit
            elif path.startswith('public'):
                return self.general_public_limit
            else:
                raise ApiError(f'Wrong path: {path}')

    async def request(self, method, path, params=None, data=None, sign=False):
        original_data = data
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        limiter = self.get_limit(path)

        for count in range(self.retries + 1):
            if sign:
                data = self._sign(path, original_data)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with limiter:
                        resp = await session.request(
                            method, urljoin(self.root_url, path),
                            params=params, json=data,
                            headers={'content-type': 'application/json'}
                        )
                        resp_json = await resp.json()
                        if resp.status != 200:
                            raise ApiError(
                                f"Error: {resp_json}. "
                                f"Status: {resp.status}. Json params: {data}")
            except aiohttp.ClientConnectorError:
                raise ApiError(f"Cannot connect to host {self.root_url}")
            except asyncio.TimeoutError:
                if count == self.retries:
                    raise ApiError(
                        f"Timeout error, retries: {self.retries}. "
                        f"Code: {resp.status}. Data: {data}"
                    )

                await asyncio.sleep(0.5)
                continue
            except ContentTypeError:
                if resp.status == 429:
                    await asyncio.sleep(0.5)
                    continue
                text = await resp.text()
                raise ApiError(
                    f"Can't decode json, content: {text}. "
                    f"Code: {resp.status}")

            if resp_json['code'] == 0:
                result = resp_json.get('result', {})
                return result.get('data', {}) or result

            if count == self.retries:
                raise ApiError(
                    f"System error, retries: {self.retries}. "
                    f"Code: {resp.status}. Json: {resp_json}. "
                    f"Data: {data}"
                )

            await asyncio.sleep(0.5)
            continue

    async def get(self, path, params=None, sign=False):
        return await self.request('get', path, params=params, sign=sign)

    async def post(self, path, data=None, sign=True):
        return await self.request('post', path, data=data, sign=sign)

    async def listen(self, url, *channels, sign=False):
        while True:
            try:
                async with async_timeout.timeout(3 * 60) as timeout:
                    async for data in self.listen_once(
                            url, *channels, sign=sign):
                        timeout.shift(3 * 60)
                        yield data
            except TimeoutError:
                await asyncio.sleep(5)

    async def listen_once(self, url, *channels, sign=False):
        timeout = aiohttp.ClientTimeout(self.timeout)
        url = urljoin(self.ws_root_url, url)
        sub_data = {
            'id': random.randint(1000, 10000),
            "method": "subscribe",
            'params': {"channels": list(channels)},
            "nonce": int(time.time())
        }
        auth_data = {}
        if sign:
            auth_data = self._sign('public/auth', auth_data)

        sub_data_sent = False
        auth_sent = False

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(
                    url, heartbeat=self.timeout,
                    receive_timeout=self.timeout) as ws:
                # sleep because too many requests from docs
                await asyncio.sleep(1)

                # [0] if not sign start connection with subscription
                if not sign:
                    await ws.send_str(json.dumps(sub_data))
                    sub_data_sent = True

                async for msg in ws:
                    data = json.loads(msg.data)
                    result = data.get('result')

                    # [1] send heartbeat to keep connection alive
                    if data['method'] == 'public/heartbeat':
                        await ws.send_str(json.dumps({
                            'id': data['id'],
                            'method': 'public/respond-heartbeat'
                        }))
                    elif sub_data_sent:
                        # [4] consume data
                        if result:
                            yield result
                        continue

                    # [2] sign auth request to listen private methods
                    if sign and not auth_sent:
                        await ws.send_str(json.dumps(auth_data))
                        auth_sent = True

                    # [3] subscribe to channels
                    if (
                            data['method'] == 'public/auth' and
                            data['code'] == 0 and not sub_data_sent
                    ):
                        await ws.send_str(json.dumps(sub_data))
                        sub_data_sent = True
