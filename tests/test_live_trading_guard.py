"""The `account` fixture must not be able to spend money by accident. Offline.

`tests/conftest.py`'s `account` fixture calls `_rebalance_50_50`, which places
LIVE CRO/USD market orders on whatever account the environment keys name. Capture
mode drives the real transport, so before this guard `API_CAPTURE=true` plus any
test requesting `account` bought real CRO while re-recording a capture - the only
thing standing between a routine re-record and a trade was an operator
remembering not to run that fixture.

These tests pin the refusal itself. None of them needs a venue, a key, or a
socket, and none of them can spend anything: the transport spy screams instead
of the exchange.
"""

import pathlib

import pytest

import conftest
import cryptocom.exchange as cro


class VenueSpy(cro.RecordApiProvider):
    """A provider that reports any attempt to reach the venue as a test failure.

    Built in replay mode - which needs no keys, opens no socket and reads no
    file here - then re-flagged: `require_live_trade_opt_in` decides on
    `api.capture` alone, and that is exactly the flag the fixture passes.
    """

    def __init__(self, capture: bool) -> None:
        super().__init__(
            cache_file=pathlib.Path("test_live_trading_guard-unused.json"),
            capture=False,
        )
        self.capture = capture

    async def request(
        self, method, path, params=None, data=None, sign=False
    ) -> dict[str, object]:
        raise AssertionError(f"a request reached the venue: {method} {path}")

    def next_uuid(self):
        raise AssertionError("a client order id was issued")


def test_replay_mode_needs_no_opt_in(monkeypatch):
    """Replay (the mode CI runs, and every existing `account` test) is untouched."""
    monkeypatch.delenv(conftest.LIVE_TRADE_OPT_IN_ENV, raising=False)
    assert conftest.require_live_trade_opt_in(capture=False) is None


@pytest.mark.parametrize(
    "value",
    [
        None,  # unset: the ordinary accident
        "",
        "true",
        "True",
        "1",
        "yes",
        "y",
        "I-AM-SPENDING-REAL-MONEY ",  # trailing space is a typo, not an opt-in
        "i-am-spending-real-money",
        conftest.LIVE_TRADE_OPT_IN + " please",
    ],
)
def test_capture_refuses_anything_but_the_exact_sentinel(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(conftest.LIVE_TRADE_OPT_IN_ENV, raising=False)
    else:
        monkeypatch.setenv(conftest.LIVE_TRADE_OPT_IN_ENV, value)

    with pytest.raises(conftest.LiveTradeNotOptedInError) as excinfo:
        conftest.require_live_trade_opt_in(capture=True)

    # The refusal has to be actionable on its own: what it would have spent,
    # the switch that unlocks it, and the mode that is not affected.
    message = str(excinfo.value)
    assert conftest.LIVE_TRADE_OPT_IN_ENV in message
    assert conftest.LIVE_TRADE_OPT_IN in message
    assert "MARKET" in message
    assert "API_CAPTURE" in message


def test_exact_sentinel_satisfies_the_guard(monkeypatch):
    """Only the sentinel unlocks it - and it unlocks the guard, not a trade."""
    monkeypatch.setenv(conftest.LIVE_TRADE_OPT_IN_ENV, conftest.LIVE_TRADE_OPT_IN)
    assert conftest.require_live_trade_opt_in(capture=True) is None


@pytest.mark.asyncio
async def test_refusal_precedes_any_request(monkeypatch):
    """No key read, no client id, no request: the guard is the first statement."""
    monkeypatch.delenv(conftest.LIVE_TRADE_OPT_IN_ENV, raising=False)
    monkeypatch.delenv("CRYPTOCOM_API_KEY", raising=False)
    monkeypatch.delenv("CRYPTOCOM_API_SECRET", raising=False)

    with pytest.raises(conftest.LiveTradeNotOptedInError):
        await conftest.live_account(VenueSpy(capture=True))


@pytest.mark.asyncio
async def test_account_fixture_itself_refuses_capture_mode(monkeypatch):
    """The guard is wired into the fixture, not only into the helper behind it.

    Drives the undecorated async generator pytest_asyncio wraps, so replacing
    the fixture body with an unguarded account construction fails here.
    """
    monkeypatch.delenv(conftest.LIVE_TRADE_OPT_IN_ENV, raising=False)
    fixture = getattr(conftest.account, "__wrapped__", None) or getattr(
        conftest.account, "_fixture_function", None
    )
    if fixture is None:  # pragma: no cover - fails loudly on a plugin upgrade
        pytest.fail("cannot reach the undecorated `account` fixture to drive it")

    with pytest.raises(conftest.LiveTradeNotOptedInError):
        async for _account in fixture(VenueSpy(capture=True)):
            pytest.fail("the fixture handed out an account without an opt-in")


@pytest.mark.asyncio
async def test_replay_mode_still_walks_past_the_guard(monkeypatch):
    """The guard must not weaken replay: there it steps aside and the old path runs.

    With capture off, `live_account` proceeds to the balance read the rebalance
    starts with - which the spy reports as a reached venue. Anything other than
    `LiveTradeNotOptedInError` means the guard did not get in the way.
    """
    monkeypatch.delenv(conftest.LIVE_TRADE_OPT_IN_ENV, raising=False)

    with pytest.raises(AssertionError) as excinfo:
        await conftest.live_account(VenueSpy(capture=False))

    assert "reached the venue" in str(excinfo.value)
    assert "user-balance" in str(excinfo.value)
