"""Capture-mode roundtrip for RecordApiProvider - offline.

CI only ever REPLAYS, so capture-mode logic would drift silently. This
drives capture=True through the transport seam, saves, reloads, and proves
strict replay + the __uuids__ log roundtrip.
"""

import json

import pytest
from test_api_request import FakeResponse

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_capture_replay_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("CRYPTOCOM_API_KEY", "dummy")
    monkeypatch.setenv("CRYPTOCOM_API_SECRET", "dummy")
    cache_file = tmp_path / "roundtrip.json"

    hits = []

    class Capture(cro.RecordApiProvider):
        async def _http_request(
            self, client, method, url, *, params, json_body, headers
        ):
            hits.append(params)
            return FakeResponse(
                200,
                {"code": 0, "id": 1, "result": {"data": {"echo": dict(params or {})}}},
            )

    cap = Capture(cache_file=cache_file, capture=True)
    first = await cap.request("get", "public/echo", params={"x": "1"})
    uuid_a = cap.next_uuid()
    uuid_b = cap.next_uuid()
    cap.save()

    assert first == {"echo": {"x": "1"}}
    assert len(hits) == 1  # really went through the transport seam
    # POSIX text files end with a newline - the repo's pre-commit
    # end-of-file-fixer fails CI if a captured file does not.
    assert cache_file.read_text().endswith("}\n")
    saved = json.loads(cache_file.read_text())
    assert saved["__uuids__"] == [uuid_a.hex, uuid_b.hex]

    class Replay(cro.RecordApiProvider):
        async def _http_request(self, *args, **kwargs):
            raise AssertionError("replay must never touch the transport")

    rep = Replay(cache_file=cache_file)
    again = await rep.request("get", "public/echo", params={"x": "1"})
    assert again == first

    # Recorded uuid sequence replays exactly, in order.
    assert rep.next_uuid().hex == uuid_a.hex
    assert rep.next_uuid().hex == uuid_b.hex
    with pytest.raises(cro.exceptions.ApiError, match="uuid replay exhausted"):
        rep.next_uuid()

    # Drifted call (absent from capture) -> loud strict error, no fallback.
    with pytest.raises(cro.exceptions.ApiError, match="Replay miss"):
        await rep.request("get", "public/other", params={})


@pytest.mark.asyncio
async def test_timestamp_normalization_roundtrip(tmp_path, monkeypatch):
    """13-digit millis must normalize so capture and future replays match."""
    monkeypatch.setenv("CRYPTOCOM_API_KEY", "dummy")
    monkeypatch.setenv("CRYPTOCOM_API_SECRET", "dummy")
    cache_file = tmp_path / "ts.json"

    class Capture(cro.RecordApiProvider):
        async def _http_request(
            self, client, method, url, *, params, json_body, headers
        ):
            return FakeResponse(200, {"code": 0, "id": 1, "result": {"data": [1]}})

    cap = Capture(cache_file=cache_file, capture=True)
    await cap.request(
        "get",
        "public/candles",
        params={"start_ts": "1700000000123", "count": "300"},
    )
    cap.save()
    saved = json.loads(cache_file.read_text())
    args_keys = list(saved["get_public/candles"].keys())
    assert "<ts>" in args_keys[0]  # normalized at capture time

    rep = cro.RecordApiProvider(cache_file=cache_file)
    result = await rep.request(
        "get",
        "public/candles",
        params={"start_ts": "1900000000456", "count": "300"},  # DIFFERENT ts
    )
    assert result == [1]  # still matched - replay is time-robust
