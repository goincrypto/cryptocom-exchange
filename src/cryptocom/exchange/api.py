import os
import json
import time
import hmac
import random
import asyncio
import hashlib

from urllib.parse import urljoin

import httpx
import websockets
import async_timeout
import aiolimiter


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


class ApiListenAsyncIterable:
    def __init__(self, api, ws, channels, sign):
        self.api = api
        self.ws = ws
        self.channels = channels

        self.sign = sign
        self.sub_data_sent = False
        self.auth_sent = False
        self.connected = False
        self.auth_data = None

    async def connect(self):
        self.auth_data = {}
        if self.sign:
            self.auth_data = self.api.sign('public/auth', self.auth_data)

        # sleep because too many requests from docs
        await asyncio.sleep(1)

        self.connected = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.connected:
            await asyncio.sleep(1)

        if not self.sub_data_sent:
            sub_data = {
                'id': random.randint(1000, 10000),
                "method": "subscribe",
                'params': {"channels": self.channels},
                "nonce": int(time.time())
            }

        # [0] if not sign start connection with subscription
        if not self.sub_data_sent and not self.sign:
            await self.ws.send(json.dumps(sub_data))
            self.sub_data_sent = True

        data = await self.ws.recv()

        if data:
            data = json.loads(data)
            result = data.get('result')

            # [1] send heartbeat to keep connection alive
            if data['method'] == 'public/heartbeat':
                await self.ws.send(json.dumps({
                    'id': data['id'],
                    'method': 'public/respond-heartbeat'
                }))
            elif self.sub_data_sent and result:
                # [4] consume data
                return result

            # [2] sign auth request to listen private methods
            if self.sign and not self.auth_sent:
                await self.ws.send(json.dumps(self.auth_data))
                self.auth_sent = True

            # [3] subscribe to channels
            if (
                    data['method'] == 'public/auth' and
                    data['code'] == 0 and not self.sub_data_sent
            ):
                await self.ws.send(json.dumps(sub_data))
                self.sub_data_sent = True


class ApiProvider:
    """Provides HTTP-api requests and websocket requests."""
    def __init__(
            self, *, api_key='', api_secret='', from_env=False,
            auth_required=True, timeout=25, retries=6,
            root_url='https://api.crypto.com/v2/',
            ws_root_url='wss://stream.crypto.com/v2/', logger=None):
        self.ssl_context = httpx.create_ssl_context()
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
                self.rate_limiters[url] =\
                    aiolimiter.AsyncLimiter(*RATE_LIMITS[urls])

        # limits for not matched methods
        self.general_private_limit = aiolimiter.AsyncLimiter(3, 0.1)
        self.general_public_limit = aiolimiter.AsyncLimiter(100, 1)

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

    def sign(self, path, data):
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

    def get_limiter(self, path):
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
        limiter = self.get_limiter(path)

        for count in range(self.retries + 1):
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                verify=self.ssl_context
            )
            if sign:
                data = self.sign(path, original_data)
            try:
                async with limiter:
                    resp = await client.request(
                        method, urljoin(self.root_url, path),
                        params=params, json=data,
                        headers={'content-type': 'application/json'}
                    )
                    resp_json = resp.json()
                    if resp.status_code != 200:
                        raise ApiError(
                            f"Error: {resp_json}. "
                            f"Status: {resp.status_code}. Json params: {data}")
            except httpx.ConnectError:
                raise ApiError(f"Cannot connect to host {self.root_url}")
            except asyncio.TimeoutError as exc:
                if count == self.retries:
                    raise ApiError(
                        f"Timeout error, retries: {self.retries}. "
                        f"Path: {path}. Data: {data}"
                    ) from exc
                continue
            except json.JSONDecodeError:
                if resp.status_code == 429:
                    continue
                raise ApiError(
                    f"Can't decode json, content: {resp.text}. "
                    f"Code: {resp.status_code}")
            finally:
                await client.aclose()

            if resp_json['code'] == 0:
                result = resp_json.get('result', {})
                return result.get('data', {}) or result

            if count == self.retries:
                raise ApiError(
                    f"System error, retries: {self.retries}. "
                    f"Code: {resp.status_code}. Json: {resp_json}. "
                    f"Data: {data}"
                )

    async def get(self, path, params=None, sign=False):
        return await self.request('get', path, params=params, sign=sign)

    async def post(self, path, data=None, sign=True):
        return await self.request('post', path, data=data, sign=sign)

    async def listen(self, url, *channels, sign=False):
        url = urljoin(self.ws_root_url, url)
        async for ws in websockets.connect(url, open_timeout=self.timeout):
            try:
                dataiterator = ApiListenAsyncIterable(self, ws, channels, sign)
                async with async_timeout.timeout(60) as tm:
                    async for data in dataiterator:
                        if data:
                            tm.shift(60)
                            yield data
            except (websockets.ConnectionClosed, asyncio.TimeoutError):
                continue
