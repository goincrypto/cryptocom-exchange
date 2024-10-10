import asyncio
import hashlib
import hmac
import json
import os
import pathlib
import random
import ssl
import time
from urllib.parse import urljoin

import aiolimiter
import async_timeout
import httpx
import websockets

RATE_LIMITS = {
    # order methods
    (
        "private/create-order",
        "private/cancel-order",
        "private/cancel-all-orders",
    ): (14, 0.1),
    # order detail methods
    ("private/get-order-detail",): (29, 0.1),
    # general trade methods
    ("private/get-trades", "private/get-order-history"): (1, 1),
}


class ApiError(Exception):
    pass


class ApiAuthError(ApiError):
    pass


def params_to_str(obj, level):
    if isinstance(obj, str):
        return obj

    if level >= 3:
        return str(obj)

    return_str = ""
    for key in sorted(obj):
        return_str += key
        if isinstance(obj[key], list):
            for subObj in obj[key]:
                return_str += str(subObj)
        elif obj[key] is None:
            return_str += "null"
        else:
            return_str += str(obj[key])
    return return_str


class ApiListenAsyncIterable:
    def __init__(self, api, ws, channels, sign):
        self.api = api
        self.ws = ws
        self.channels = channels

        self.sign = sign
        self.sub_data_sent = False
        self.auth_sent = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.sub_data_sent:
            sub_data = {
                "id": random.randint(0, 2**63 - 1),
                "method": "subscribe",
                "params": {"channels": self.channels},
                "nonce": int(time.time()),
            }

        # [0] sign auth request to listen private methods
        if not self.auth_sent and self.sign:
            await self.ws.send(json.dumps(self.api.sign("public/auth", {})))
            self.auth_sent = True

        # [0] if not sign start connection with subscription
        if not self.sign and not self.sub_data_sent:
            await self.ws.send(json.dumps(sub_data))
            self.sub_data_sent = True

        async with async_timeout.timeout(60) as tm:
            data = await self.ws.recv()
            tm.shift(60)

        if data:
            data = json.loads(data)
            result = data.get("result")

            # [1] send heartbeat to keep connection alive
            if data["method"] == "public/heartbeat":
                await self.ws.send(
                    json.dumps(
                        {
                            "id": data["id"],
                            "method": "public/respond-heartbeat",
                        }
                    )
                )
            # [3] consume data
            elif self.sub_data_sent and result:
                if result["subscription"] not in self.channels:
                    raise ApiError(
                        f'Wrong channel data received: {result["subscription"]} '
                        f'not in {self.channels}'
                    )
                return result

            # [2] subscribe to channels
            if data["method"] == "public/auth" and data["code"] == 0:
                await self.ws.send(json.dumps(sub_data))
                self.sub_data_sent = True
            elif "code" not in data or data["code"] != 0:
                raise ApiAuthError(f"{data}")


class ApiProvider:
    """Provides HTTP-api requests and websocket requests."""

    def __init__(
        self,
        *,
        api_key="",
        api_secret="",
        from_env=False,
        auth_required=True,
        timeout=5,
        retries=5,
        root_url="https://api.crypto.com/exchange/v1/",
        ws_root_url="wss://stream.crypto.com/exchange/v1/",
        logger=None,
    ):
        self.ssl_context = httpx.create_ssl_context()
        self.api_key = api_key
        self.api_secret = api_secret
        self.root_url = root_url
        self.ws_root_url = ws_root_url
        self.timeout = timeout
        self.retries = retries
        self.last_request_path = ""

        self.rate_limiters = {}

        for urls in RATE_LIMITS:
            for url in urls:
                self.rate_limiters[url] = aiolimiter.AsyncLimiter(
                    *RATE_LIMITS[urls]
                )

        # limits for not matched methods
        self.general_private_limit = aiolimiter.AsyncLimiter(3, 0.1)
        self.general_public_limit = aiolimiter.AsyncLimiter(100, 1)

        if not auth_required:
            return

        if from_env:
            self.read_keys_from_env()

        if not self.api_key or not self.api_secret:
            raise ValueError("Provide api_key and api_secret")

    def read_keys_from_env(self):
        self.api_key = os.environ.get("CRYPTOCOM_API_KEY", "")
        if not self.api_key:
            raise ValueError("Provide CRYPTOCOM_API_KEY env value")
        self.api_secret = os.environ.get("CRYPTOCOM_API_SECRET", "")
        if not self.api_secret:
            raise ValueError("Provide CRYPTOCOM_API_SECRET env value")

    def sign(self, path, data):
        data = data or {}
        data["method"] = path
        sign_time = int(time.time() * 1000)
        data.update({"nonce": sign_time, "api_key": self.api_key})
        data["id"] = random.randint(0, 2**63 - 1)
        data_params = data.get("params", {})
        params = ""
        if data_params:
            params = params_to_str(data_params, 0)
        payload = f"{path}{data['id']}{self.api_key}{params}{data['nonce']}"
        data["sig"] = hmac.new(
            bytes(str(self.api_secret), "utf-8"),
            msg=bytes(payload, "utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return data

    def get_limiter(self, path):
        if path in self.rate_limiters:
            return self.rate_limiters[path]
        else:
            if path.startswith("private"):
                return self.general_private_limit
            elif path.startswith("public"):
                return self.general_public_limit
            else:
                raise ApiError(f"Wrong path: {path}")

    async def request(self, method, path, params=None, data=None, sign=False):
        original_data = data
        limiter = self.get_limiter(path)
        count = 0
        while count <= self.retries:
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                verify=self.ssl_context,
            )
            if sign:
                data = self.sign(path, original_data)
            try:
                async with limiter:
                    resp = await client.request(
                        method,
                        urljoin(self.root_url, path),
                        params=params,
                        json=data,
                        headers={"content-type": "application/json"},
                    )
                    resp_json = resp.json()
                    count += 1
                    if resp.status_code in [401, 400]:
                        raise ApiAuthError(resp_json)
                    elif resp.status_code != 200:
                        if count != self.retries:
                            continue
                        raise ApiError(
                            f"Error: {resp_json}. "
                            f"Status: {resp.status_code}. Json params: {data}"
                        )
            except (
                asyncio.TimeoutError,
                httpx.HTTPError,
                ssl.SSLError,
                json.JSONDecodeError,
            ) as exc:
                if count == self.retries:
                    raise ApiError(
                        f"Timeout or read error, retries: {self.retries}. "
                        f"Path: {path}. Data: {data}. Exc: {exc}"
                    ) from exc
                continue
            finally:
                await client.aclose()

            if resp_json["code"] == 0:
                result = resp_json.get("result", {})
                if "data" in result:
                    result = result["data"]
                if result is None:
                    continue
                if data:
                    if data["id"] != resp_json["id"]:
                        raise ApiError(f"Not matched req = resp {resp_json}")
                return result

            if count == self.retries:
                raise ApiError(
                    f"System error, retries: {self.retries}. "
                    f"Code: {resp.status_code}. Json: {resp_json}. "
                    f"Data: {data}"
                )

    async def get(self, path, params=None, sign=False):
        return await self.request("get", path, params=params, sign=sign)

    async def post(self, path, data=None, sign=True):
        return await self.request("post", path, data=data, sign=sign)

    async def listen(self, url, *channels, sign=False):
        url = urljoin(self.ws_root_url, url)
        async for ws in websockets.connect(url, open_timeout=self.timeout):
            try:
                dataiterator = ApiListenAsyncIterable(self, ws, channels, sign)
                async for data in dataiterator:
                    if data:
                        yield data
            except (websockets.ConnectionClosed, asyncio.TimeoutError):
                continue


class RecordApiProvider(ApiProvider):
    """Captures API and websocket responses into json files.
    If capture=False it will read them to reproduce same responses in order."""

    def __init__(
        self,
        *,
        cache_file: pathlib.Path,
        capture: bool = False,
        divide_delay: int = 1,
        fake_account_id: bool = True,
    ):
        self.capture = capture
        self.cache_file = cache_file
        self.divide_delay = divide_delay

        # TODO: implement auto-replacement
        self.fake_account_id = fake_account_id

        if self.capture:
            self.cache_file.parent.mkdir(exist_ok=True, parents=True)
            if self.cache_file.exists():
                self.cache_file.unlink()
                self.cache_file.touch()
            self.records = {}
        else:
            self.records = json.loads(self.cache_file.read_text())

        kwargs = {"from_env": capture}
        if not self.capture:
            kwargs["api_key"] = "dummy"
            kwargs["api_secret"] = "dummy"
        super().__init__(**kwargs)

    async def request(self, method, path, params=None, data=None, sign=False):
        key = f"{method}_{path}"
        args_data = data or params or {}
        args_data = sorted(args_data.items(), key=lambda v: v[0])
        args = ",".join(f"{key}={value}" for key, value in args_data)

        if self.capture:
            timestamp = time.time()
            response = await super().request(
                method, path, params=params, data=data, sign=sign
            )
            self.records.setdefault(key, {}).setdefault(args, []).append(
                {
                    "response": response,
                    "exec_time": time.time() - timestamp,
                    "timestamp": timestamp,
                }
            )
        else:
            try:
                record = self.records[key][args].pop(0)
            except KeyError:
                raise ApiError("No path found")
            await asyncio.sleep(record["exec_time"] / self.divide_delay)
            response = record["response"]

        return response

    async def listen(self, url, *channels, sign=False):
        key = "ws"
        args = ",".join(channels)
        if self.capture:
            timestamp = time.time()
            async for response in super().listen(url, *channels, sign=sign):
                self.records.setdefault(key, {}).setdefault(args, []).append(
                    {
                        "response": response,
                        "exec_time": time.time() - timestamp,
                        "timestamp": timestamp,
                    }
                )
                timestamp = time.time()
                yield response
        else:
            for record in self.records[key][args]:
                await asyncio.sleep(record["exec_time"] / self.divide_delay)
                yield record["response"]

    def save(self):
        if self.capture:
            for key, args in self.records.items():
                for arg, data in args.items():
                    args[arg] = sorted(data, key=lambda v: v["timestamp"])
            self.cache_file.write_text(json.dumps(self.records, indent=2))
