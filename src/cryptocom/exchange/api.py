import asyncio
import hashlib
import hmac
import json
import logging
import os
import pathlib
import random
import re
import ssl
import time
import uuid
from urllib.parse import urljoin

import aiolimiter
import async_timeout
import httpx
import websockets

from .exceptions import (
    ApiAuthError,
    ApiError,
    ExchangeError,
    api_error_from_response,
    is_retryable_error_code,
)

__all__ = [
    "ApiAuthError",
    "ApiError",
    "ApiProvider",
    "ExchangeError",
    "RecordApiProvider",
]

# HTTP statuses that are transient BY NATURE (outcome may still be unknown
# for writes - errors built from them carry the indeterminate contract).
RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

RATE_LIMITS = {
    # =====================================================================
    # Crypto.com Exchange API Rate Limits
    # Source: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction
    #
    # REST API (Authenticated/Private):
    #   - Specific endpoints listed below have custom limits
    #   - All other private endpoints: 3 requests per 100ms
    #   - Staking endpoints: 50 requests per second
    #
    # REST API (Public/Market Data):
    #   - All public endpoints: 100 requests per second (per IP)
    #
    # WebSocket:
    #   - User API: 150 requests per second
    #   - Market Data: 100 requests per second
    # =====================================================================
    # Order management methods (15 req/100ms)
    (
        "private/create-order",
        "private/cancel-order",
        "private/cancel-all-orders",
    ): (15, 0.1),
    # Order detail methods (30 req/100ms)
    ("private/get-order-detail",): (30, 0.1),
    # General trade methods (1 req/s)
    ("private/get-trades", "private/get-order-history"): (1, 1),
    # Note: All other private endpoints use general_private_limit (3 req/100ms)
    # Note: All staking endpoints use general_staking_limit (50 req/s)
    # Note: All public endpoints use general_public_limit (100 req/s)
}


def params_to_str(obj, level) -> str:
    if level >= 3:
        return str(obj)

    return_str = ""
    for key in sorted(obj):
        return_str += str(key)
        if obj[key] is None:
            return_str += "null"
        elif isinstance(obj[key], list):
            for sub_obj in obj[key]:
                return_str += params_to_str(sub_obj, level + 1)
        else:
            return_str += str(obj[key])
    return return_str


class ApiListenAsyncIterable:
    """Listen websocket iterator."""

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
        sub_data = {
            "id": random.randint(0, 2**63 - 1),
            "method": "subscribe",
            "params": {"channels": self.channels},
            "nonce": int(time.time() * 1000),
        }

        # [0] sign auth request to listen private methods
        if not self.auth_sent and self.sign:
            auth_data = self.api.sign("public/auth", {})
            await self.ws.send(json.dumps(auth_data))
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

            # One chain, evaluated per received frame (each __anext__
            # consumes exactly one frame; non-data frames return None and
            # are skipped by the listen() wrapper).
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
            # [2] subscribe to channels (after auth ack)
            elif (
                data["method"] == "public/auth"
                and data.get("code") == 0
                and not self.sub_data_sent
            ):
                await self.ws.send(json.dumps(sub_data))
                self.sub_data_sent = True
            # [3] consume data
            elif self.sub_data_sent and result:
                if result["subscription"] not in self.channels:
                    raise ApiError(
                        f"Wrong channel data received: {result['subscription']} "
                        f"not in {self.channels}"
                    )
                return result
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
        retry_backoff: float = 0.0,
        logger: logging.Logger | None = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.ssl_context = httpx.create_ssl_context()
        self.api_key = api_key
        self.api_secret = api_secret
        self.root_url = root_url
        self.ws_root_url = ws_root_url
        self.timeout = timeout
        self.retries = retries
        # Sleep between retries of transient failures (0 = tight loop).
        self.retry_backoff = retry_backoff
        self.last_request_path = ""

        self.rate_limiters = {}

        for urls, limit in RATE_LIMITS.items():
            for url in urls:
                self.rate_limiters[url] = aiolimiter.AsyncLimiter(*limit)

        # limits for not matched methods
        # Private APIs: 3 requests per 100ms (REST API - authenticated)
        # Source: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction
        self.general_private_limit = aiolimiter.AsyncLimiter(3, 0.1)
        # Public APIs: 100 requests per second (Market APIs - per IP)
        # Source: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction
        self.general_public_limit = aiolimiter.AsyncLimiter(100, 1)
        # Staking APIs: 50 requests per second
        # Source: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction
        self.general_staking_limit = aiolimiter.AsyncLimiter(50, 1)

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
            if path.startswith("private/staking"):
                return self.general_staking_limit
            elif path.startswith("private"):
                return self.general_private_limit
            elif path.startswith("public"):
                return self.general_public_limit
            else:
                raise ApiError(f"Wrong path: {path}")

    async def _http_request(self, client, method, url, *, params, json_body, headers):
        """Transport seam: the single outbound HTTP call.

        Override point for offline tests (retry/error classification can be
        driven without a network).
        """
        return await client.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=headers,
        )

    @staticmethod
    def _classify_http_status(status: int, resp_json, method_path: str):
        """Typed error for a non-200 HTTP response (taxonomy-aware)."""
        body = resp_json if isinstance(resp_json, dict) else {}
        code = body.get("code")
        message = body.get("message") or str(resp_json)
        if status in (401, 403):
            return ApiAuthError(
                f"HTTP {status}: {message}", code=code or status, method=method_path
            )
        if isinstance(code, int) and code:
            # Body still carries the structured API code - trust the taxonomy.
            return api_error_from_response(
                code, body.get("message"), method=method_path
            )
        if status >= 500:
            # Server-side failure without a structured answer: the request
            # may have been processed. INDETERMINATE.
            return ApiError(f"HTTP {status}: {message}", method=method_path)
        # Other 4xx without a code: the request was rejected, definitely.
        return ExchangeError(
            f"HTTP {status}: {message}", code=status, method=method_path
        )

    async def request(self, method, path, params=None, data=None, sign=False):
        original_data = data
        self.logger.debug(f"{method.upper()} {path} params={params} data={data}")
        limiter = self.get_limiter(path)
        # One budget for ALL failure kinds (transport, HTTP, transient API
        # code, null result): `retries` RETRIES after the first attempt.
        # (The old counter only advanced on parsed responses, so repeated
        # transport errors retried FOREVER.)
        attempt = 0
        start_time = time.time()
        while True:
            attempt += 1
            exhausted = attempt > self.retries
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=self.timeout),
                verify=self.ssl_context,
            )
            if sign:
                data = self.sign(path, original_data)
            try:
                async with limiter:
                    resp = await self._http_request(
                        client,
                        method,
                        urljoin(self.root_url, path),
                        params=params,
                        json_body=data,
                        headers={"content-type": "application/json"},
                    )
                    resp_json = resp.json()
                    if resp.status_code != 200:
                        error = self._classify_http_status(
                            resp.status_code, resp_json, path
                        )
                        retryable = resp.status_code in RETRYABLE_HTTP_STATUSES or (
                            isinstance(resp_json, dict)
                            and is_retryable_error_code(resp_json.get("code", 0))
                        )
                        if retryable and not exhausted:
                            if self.retry_backoff:
                                await asyncio.sleep(self.retry_backoff)
                            continue
                        raise error
            except (
                TimeoutError,
                httpx.HTTPError,
                ssl.SSLError,
                json.JSONDecodeError,
            ) as exc:
                if exhausted:
                    raise ApiError(
                        f"Timeout or read error, retries: {self.retries}. "
                        f"Path: {path}. Data: {data}. Exc: {exc}"
                    ) from exc
                self.logger.warning(
                    f"Retry {attempt}/{self.retries}: {method} {path} - {exc}"
                )
                if self.retry_backoff:
                    await asyncio.sleep(self.retry_backoff)
                continue
            finally:
                await client.aclose()

            if resp_json["code"] == 0:
                result = resp_json.get("result", {})
                if "data" in result:
                    result = result["data"]
                if result is None:
                    if exhausted:
                        raise ApiError(
                            f"Null result after {self.retries} retries. "
                            f"Path: {path}. Data: {data}"
                        )
                    if self.retry_backoff:
                        await asyncio.sleep(self.retry_backoff)
                    continue
                if data and data["id"] != resp_json["id"]:
                    raise ApiError(f"Not matched req = resp {resp_json}")
                elapsed = time.time() - start_time
                self.logger.debug(f"{method.upper()} {path} received in {elapsed:.3f}s")
                return result

            # Non-zero API error code -> typed exception. Deterministic
            # rejections raise immediately; only transient codes retry.
            error = api_error_from_response(
                resp_json["code"], resp_json.get("message"), method=path
            )
            if not is_retryable_error_code(resp_json["code"]) or exhausted:
                raise error
            if self.retry_backoff:
                await asyncio.sleep(self.retry_backoff)

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
            except (TimeoutError, websockets.ConnectionClosed):
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
        self.fake_account_id = fake_account_id
        # client_oids auto-generated via uuid4 must be identical between
        # capture and replay, otherwise request args never match. Capture
        # mode logs the issued ids; replay mode serves them back in order.
        self.uuid_log: list[str] = []
        self._uuid_replay: list[str] = []

        if self.capture:
            self.cache_file.parent.mkdir(exist_ok=True, parents=True)
            if self.cache_file.exists():
                self.cache_file.unlink()
            self.records = {}
            super().__init__(from_env=True)
        else:
            self.records = {}
            if self.cache_file.exists():
                self.records = json.loads(self.cache_file.read_text())
            self._uuid_replay = list(reversed(self.records.pop("__uuids__", [])))
            super().__init__(api_key="dummy", api_secret="dummy", auth_required=False)

    def next_uuid(self):
        """uuid4 replacement keeping client_oids capture/replay consistent.

        Capture: real random ids, logged into the cache file.
        Replay: the exact recorded ids, in order.
        """
        if self.capture:
            value = uuid.uuid4()
            self.uuid_log.append(value.hex)
            return value
        if not self._uuid_replay:
            raise ApiError(
                "uuid replay exhausted: code generated more client ids "
                "than were captured - re-record with API_CAPTURE=true"
            )
        return uuid.UUID(hex=self._uuid_replay.pop())

    async def request(self, method, path, params=None, data=None, sign=False):
        key = f"{method}_{path}"
        args_data = data or params or {}
        args_data = sorted(args_data.items(), key=lambda v: v[0])
        args = ",".join(f"{key}={value}" for key, value in args_data)
        # Volatile values: 13-digit epoch-millis (time windows, ids that
        # embed time) differ every run. Normalize in BOTH modes so capture
        # keys and replay lookups match. Call sequence is still strictly
        # enforced by the per-args queues.
        args = re.sub(r"\d{13}", "<ts>", args)

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
            except (KeyError, IndexError):
                # Strict: never borrow a mismatched response. A miss here
                # means the code drifted from the capture (different args,
                # different call sequence, or exhausted uuids).
                available_args = list(self.records.get(key, {}).keys())
                raise ApiError(
                    f"Replay miss for {key} args=[{args}]; "
                    f"captured args: {available_args}. Code no longer "
                    "matches the capture - re-record with API_CAPTURE=true."
                ) from None
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
            for args in self.records.values():
                for arg, data in args.items():
                    args[arg] = sorted(data, key=lambda v: v["timestamp"])
            payload = dict(self.records)
            if self.uuid_log:
                payload["__uuids__"] = self.uuid_log
            self.cache_file.write_text(json.dumps(payload, indent=2))
