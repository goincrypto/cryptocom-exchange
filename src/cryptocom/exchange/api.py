import os
import json
import gzip
import time
import asyncio
import hashlib

from urllib.parse import urljoin

import aiohttp

from aiohttp.client_exceptions import ContentTypeError


class ApiError(Exception):
    pass


class ApiProvider:
    """Provides HTTP-api requests and websocket requests."""
    def __init__(
            self, *, api_key='', api_secret='', from_env=False,
            auth_required=True, timeout=3, retries=5,
            root_url='https://api.crypto.com/v1/',
            ws_root_url='wss://ws.crypto.com/kline-api/ws'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.root_url = root_url
        self.ws_root_url = ws_root_url
        self.timeout = timeout
        self.retries = retries

        # NOTE: do not change this, due to crypto.com rate-limit 10-per second
        self.semaphore = asyncio.Semaphore(10)

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

    def _sign(self, data):
        data = data or {}
        sign_time = int(time.time() * 1000)
        data.update({'time': sign_time, 'api_key': self.api_key})
        sign = ''.join(f'{key}{data[key]}' for key in sorted(data))
        sign = f'{sign}{self.api_secret}'
        data['sign'] = hashlib.sha256(sign.encode('utf-8')).hexdigest()
        return data

    async def ws_listen(self, data, timeout: int = None):
        timeout = aiohttp.ClientTimeout(self.timeout)
        count = 0

        while count != self.retries:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.ws_connect(self.ws_root_url) as ws:
                        await ws.send_str(json.dumps(data))
                        async for msg in ws:
                            data = gzip.decompress(msg.data).decode('utf-8')
                            data = json.loads(data)
                            yield data
                            count = 0
                except asyncio.TimeoutError:
                    if count == self.retries:
                        raise ApiError(
                            f"Timeout error, retries: {self.retries}")

                    await asyncio.sleep(0.2)
                    count += 1
                    continue

    async def ws_request(self, data, timeout: int = None):
        async for data in self.ws_listen(data, timeout=timeout):
            return data

    async def request(self, method, path, params=None, data=None, sign=False):
        if sign:
            data = self._sign(data)

        timeout = aiohttp.ClientTimeout(total=self.timeout)

        for count in range(self.retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with self.semaphore:
                        resp = await session.request(
                            method, urljoin(self.root_url, path),
                            params=params, data=data
                        )
                        resp_json = await resp.json()
            except aiohttp.ClientConnectorError:
                raise ApiError("Cannot connect to host {self.root_url}")
            except asyncio.TimeoutError:
                if count == self.retries:
                    raise ApiError(
                        f"Timeout error, retries: {self.retries}. "
                        f"Code: {resp.status}. Data: {data}"
                    )

                await asyncio.sleep(1)
                continue
            except ContentTypeError:
                if resp.status == 429:
                    await asyncio.sleep(1)
                    continue
                text = await resp.text()
                raise ApiError(
                    f"Can't decode json, content: {text}. "
                    f"Code: {resp.status}")

            if resp_json['code'] == '0':
                return resp_json['data']

            if count == self.retries:
                raise ApiError(
                    f"System error, retries: {self.retries}. "
                    f"Code: {resp.status}. Json: {resp_json}. "
                    f"Data: {data}"
                )

            await asyncio.sleep(1)
            continue

    async def get(self, path, params=None):
        return await self.request('get', path, params=params)

    async def post(self, path, data=None, sign=True):
        return await self.request('post', path, data=data, sign=sign)
