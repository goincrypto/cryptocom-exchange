"""Offline tests for the websocket client protocol (no sockets involved).

__anext__ consumes EXACTLY ONE frame per call: handshake/heartbeat frames
return None (the listen() wrapper skips them), only subscription data
frames yield results. Protocol violations raise.
"""

import json

import pytest

import cryptocom.exchange as cro
from cryptocom.exchange.api import ApiListenAsyncIterable


class FakeWs:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload))

    async def recv(self):
        if not self.frames:
            raise cro.exceptions.ApiError("script exhausted")
        frame = self.frames.pop(0)
        if isinstance(frame, Exception):
            raise frame
        return json.dumps(frame)


def _provider():
    return cro.ApiProvider(api_key="k", api_secret="s")


def _iter(frames, channels=("user.order.CRO_USD",), sign=True):
    return ApiListenAsyncIterable(_provider(), FakeWs(frames), list(channels), sign)


async def next_result(it, max_steps=8):
    """Drive one-frame-per-call until a data result appears."""
    for _ in range(max_steps):
        result = await it.__anext__()
        if result is not None:
            return result
    raise AssertionError("no result within frame budget")


AUTH_OK = {"method": "public/auth", "code": 0, "id": 1, "result": {}}
SUB_ACK = {"method": "subscribe", "code": 0, "id": 2, "result": None}
HEARTBEAT = {"method": "public/heartbeat", "id": 7}
DATA = {
    "method": "subscription",
    "code": 0,
    "id": 3,
    "result": {"subscription": "user.order.CRO_USD", "data": [{"x": 1}]},
}


@pytest.mark.asyncio
async def test_private_handshake_order_and_data():
    it = _iter([AUTH_OK, SUB_ACK, HEARTBEAT, DATA])
    result = await next_result(it)
    assert result["subscription"] == "user.order.CRO_USD"

    methods = [m["method"] for m in it.ws.sent]
    assert methods == ["public/auth", "subscribe", "public/respond-heartbeat"]
    assert it.ws.sent[1]["params"]["channels"] == ["user.order.CRO_USD"]


@pytest.mark.asyncio
async def test_public_stream_subscribes_without_auth():
    book_data = {
        "method": "subscription",
        "code": 0,
        "id": 3,
        "result": {"subscription": "book.CRO_USD.50", "data": [[0.05, 1.0]]},
    }
    it = _iter([SUB_ACK, book_data], channels=("book.CRO_USD.50",), sign=False)
    result = await next_result(it)
    assert result["data"] == [[0.05, 1.0]]
    assert it.ws.sent[0]["method"] == "subscribe"
    assert all(m["method"] != "public/auth" for m in it.ws.sent)


@pytest.mark.asyncio
async def test_heartbeat_is_answered_not_yielded():
    it = _iter([HEARTBEAT, DATA], channels=("user.order.CRO_USD",), sign=False)
    result = await next_result(it)
    assert result["subscription"] == "user.order.CRO_USD"
    assert {"id": 7, "method": "public/respond-heartbeat"} in it.ws.sent


@pytest.mark.asyncio
async def test_wrong_channel_raises():
    frame = {
        "method": "subscription",
        "code": 0,
        "id": 4,
        "result": {"subscription": "user.order.BTC_USD", "data": []},
    }
    it = _iter([frame], sign=False)  # subscribe sent on first call
    with pytest.raises(cro.exceptions.ApiError, match="Wrong channel"):
        await it.__anext__()


@pytest.mark.asyncio
async def test_error_code_frame_raises_auth_error():
    frame = {"method": "public/auth", "code": 40102, "message": "bad nonce"}
    it = _iter([frame])
    with pytest.raises(cro.exceptions.ApiAuthError):
        await it.__anext__()


@pytest.mark.asyncio
async def test_transport_error_propagates():
    """Socket-level failures must surface (listen()'s reconnect loop owns them)."""
    it = _iter([ConnectionResetError("boom")])
    with pytest.raises(ConnectionResetError):
        await it.__anext__()
