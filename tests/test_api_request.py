"""Offline tests for ApiProvider.request via the _http_request seam.

Pins the error contract end-to-end (without network):
- deterministic codes raise immediately, no retry burn;
- transient codes retry and, when exhausted, raise typed errors
  (timeout/internal additionally marked indeterminate);
- HTTP statuses map through the taxonomy (auth vs server vs client);
- transport blowups exhaust to an indeterminate ApiError.
"""

import asyncio

import httpx
import pytest

import cryptocom.exchange as cro


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = (
            payload
            if payload is not None
            else {
                "code": 0,
                "id": 1,
                "result": {"data": ["ok"]},
            }
        )

    def json(self):
        return self._payload


class ScriptedHttp(cro.ApiProvider):
    """ApiProvider with the transport seam faked; rest is real logic."""

    def __init__(self, script, retries=2):
        super().__init__(
            api_key="k", api_secret="s", retries=retries, retry_backoff=0.0
        )
        self.script = list(script)
        self.calls = 0

    async def _http_request(self, client, method, url, *, params, json_body, headers):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _payload(code, message=None):
    body = {"code": code, "id": 1}
    if message:
        body["message"] = message
    return body


OK = FakeResponse(200, {"code": 0, "id": 1, "result": {"data": ["ok"]}})


@pytest.mark.asyncio
async def test_success_first_try():
    api = ScriptedHttp([OK])
    assert await api.get("public/ping") == ["ok"]
    assert api.calls == 1


@pytest.mark.asyncio
async def test_deterministic_error_never_retries():
    api = ScriptedHttp([FakeResponse(200, _payload(40401, "no order"))] * 3)
    with pytest.raises(cro.exceptions.OrderNotFoundError):
        await api.get("private/get-order-detail")
    assert api.calls == 1  # the whole point: no retry burn on rejections


@pytest.mark.asyncio
async def test_transient_recovers_within_budget():
    api = ScriptedHttp([FakeResponse(200, _payload(42901, "rate")), OK])
    assert await api.get("public/ping") == ["ok"]
    assert api.calls == 2


@pytest.mark.asyncio
async def test_transient_exhaustion_raises_typed_indeterminate():
    """Request timeout exhaustion: typed AND outcome-unknown."""
    api = ScriptedHttp([FakeResponse(200, _payload(40801, "timeout"))] * 3, retries=2)
    with pytest.raises(cro.exceptions.RequestTimeoutError) as exc_info:
        await api.get("public/ping")
    assert exc_info.value.is_indeterminate
    assert api.calls == 3


@pytest.mark.asyncio
async def test_rate_limit_exhaustion_stays_deterministic():
    """Rate-limit rejection = request definitely NOT processed."""
    api = ScriptedHttp([FakeResponse(200, _payload(42901, "rate"))] * 3, retries=2)
    with pytest.raises(cro.exceptions.RateLimitExceededError) as exc_info:
        await api.get("public/ping")
    assert not exc_info.value.is_indeterminate


@pytest.mark.asyncio
async def test_http_401_maps_to_auth_error():
    api = ScriptedHttp([FakeResponse(401, {"message": "invalid key"})])
    with pytest.raises(cro.exceptions.ApiAuthError, match="HTTP 401"):
        await api.get("private/user-balance")
    assert api.calls == 1


@pytest.mark.asyncio
async def test_http_400_with_body_code_uses_taxonomy():
    api = ScriptedHttp([FakeResponse(400, _payload(213, "bad qty"))])
    with pytest.raises(cro.exceptions.InvalidOrderError) as exc_info:
        await api.get("private/create-order")
    assert exc_info.value.code == 213
    assert not exc_info.value.is_indeterminate


@pytest.mark.asyncio
async def test_http_502_without_code_is_indeterminate():
    api = ScriptedHttp([FakeResponse(502, {"message": "bad gateway"})] * 3, retries=2)
    with pytest.raises(cro.exceptions.ApiError) as exc_info:
        await api.get("public/ping")
    err = exc_info.value
    assert err.code is None  # no structured answer -> outcome unknown
    assert err.is_indeterminate
    assert api.calls == 3  # 5xx is transient -> burned the retry budget


@pytest.mark.asyncio
async def test_http_404_without_code_is_deterministic():
    api = ScriptedHttp([FakeResponse(404, {"message": "no path"})])
    with pytest.raises(cro.exceptions.ExchangeError) as exc_info:
        await api.get("public/nope")
    assert exc_info.value.code == 404
    assert not exc_info.value.is_indeterminate


@pytest.mark.asyncio
async def test_transport_errors_exhaust_indeterminate():
    api = ScriptedHttp(
        [httpx.ConnectError("down"), TimeoutError(), httpx.ReadError("x")],
        retries=2,
    )
    with pytest.raises(cro.exceptions.ApiError, match="Timeout or read error") as exc:
        await api.get("public/ping")
    assert exc.value.is_indeterminate


@pytest.mark.asyncio
async def test_response_id_mismatch_raises():
    mismatch = FakeResponse(200, {"code": 0, "id": 999, "result": {"data": ["x"]}})
    api = ScriptedHttp([mismatch])
    with pytest.raises(cro.exceptions.ApiError, match="Not matched"):
        await api.post("private/ping", {"id": 1, "params": {}})


@pytest.mark.asyncio
async def test_null_result_retries_then_succeeds():
    nullish = FakeResponse(200, {"code": 0, "id": 1, "result": {"data": None}})
    api = ScriptedHttp([nullish, OK])
    assert await api.get("public/ping") == ["ok"]
    assert api.calls == 2


@pytest.mark.asyncio
async def test_retry_backoff_is_observable():
    api = ScriptedHttp([FakeResponse(200, _payload(42901, "rate")), OK], retries=2)
    api.retry_backoff = 0.05
    loop = asyncio.get_running_loop()
    start = loop.time()
    assert await api.get("public/ping") == ["ok"]
    assert loop.time() - start >= 0.05
