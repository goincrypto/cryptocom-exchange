import os
import json
import gzip
import time
import hmac
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
            auth_required=True, timeout=3, retries=20,
            root_url='https://api.crypto.com/v2/',
            ws_root_url='wss://stream.crypto.com/v2/'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.root_url = root_url
        self.ws_root_url = ws_root_url
        self.timeout = timeout
        self.retries = retries

        # NOTE: do not change this, due to crypto.com rate-limits
        self.semaphore = asyncio.Semaphore(50)

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
        data.update({'nonce': sign_time, 'api_key': self.api_key, 'id': 5959})

        data_params = data.get('params', {})
        if not data_params:
            data['params'] = {}
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

    async def request(self, method, path, params=None, data=None, sign=False):
        if sign:
            data = self._sign(path, data)

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        for count in range(self.retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with self.semaphore:
                        resp = await session.request(
                            method, urljoin(self.root_url, path),
                            params=params, json=data,
                            headers={'content-type': 'application/json'}
                        )
                        resp_json = await resp.json()
                        if resp.status != 200:
                            raise ApiError(
                                f"Error: {resp_json}. Status: {resp.status}")
            except aiohttp.ClientConnectorError:
                raise ApiError(f"Cannot connect to host {self.root_url}")
            except asyncio.TimeoutError:
                if count == self.retries:
                    raise ApiError(
                        f"Timeout error, retries: {self.retries}. "
                        f"Code: {resp.status}. Data: {data}"
                    )

                await asyncio.sleep(0.1)
                continue
            except ContentTypeError:
                if resp.status == 429:
                    await asyncio.sleep(0.1)
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

            await asyncio.sleep(0.1)
            continue

    async def get(self, path, params=None):
        return await self.request('get', path, params=params)

    async def post(self, path, data=None, sign=True):
        return await self.request('post', path, data=data, sign=sign)
