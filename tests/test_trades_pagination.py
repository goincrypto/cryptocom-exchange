"""Trade pagination must not lose trades at a page boundary.

WHY THIS FILE EXISTS. `Market.get_trades` paginates by walking `end_ts` back to the oldest
trade it has seen. The venue answers that parameter in NANOSECONDS (`trade_time_ns <= end_ts`),
but the cursor was built from `trade.time`, which is SECONDS — so the next page asked for
"trades at or before the START of that second" and every remaining trade in that second was
skipped, silently.

That is not uniform data loss. It removes trades from BUSY seconds, and a busy second is exactly
what sets an OHLC bar's high and low. Measured on CRO_USD: a page boundary landing inside a
141-trade second lost 121 trades and 74% of that 5-minute bar's volume. The existing
`test_trades_match_candles_ohlcv_from_trades` does not catch it: it records
`max_high_diff_pct`/`max_low_diff_pct` but never asserts them, and it measures only the direction
(`trade.high > api.high`) that losing trades cannot produce — losing trades make a bar's high
too LOW, never too high.

These tests use no capture file and no credentials, so they run anywhere and cannot rot into a
replay of their own assumptions. The scripted venue below implements `end_ts` the way the real
one does; a venue that ignored the cursor would prove nothing.
"""

import pytest

import cryptocom.exchange as cro

NS = 1_000_000_000
PAGE_SIZE = 150
#: A past epoch second, so the scripted window below is explicit and the test does not care
#: what the wall clock says. (An end_ts in the future makes `get_trades`, which defaults to
#: `time.time()`, filter the whole tape out and pass by answering nothing at all.)
BASE = 1_780_000_000
#: A second carrying many trades — the shape that costs trades at a second-aligned cursor.
BUSY_SECOND = BASE - 141


def trade_row(ns: int, quantity: str = "164") -> dict:
    """One row in the shape `public/get-trades` answers (d/t/tn/p/q/s)."""
    return {
        "d": str(ns),
        "t": ns // 1_000_000,
        "tn": ns,
        "p": "0.05686",
        "q": quantity,
        "s": "sell",
        "i": "CRO_USD",
    }


def busy_tape() -> list[dict]:
    """140 single-trade seconds, then 30 trades inside one second, then 60 more.

    Newest first, as the venue answers. With a 150-row page, page one ends ten trades into the
    busy second: precisely the boundary that a second-granular cursor truncates.
    """
    rows = [trade_row((BASE - 1 - i) * NS + 500) for i in range(140)]
    rows += [trade_row(BUSY_SECOND * NS + i) for i in reversed(range(30))]
    rows += [trade_row((BUSY_SECOND - 1 - i) * NS + 500) for i in range(60)]
    return rows


class ScriptedVenue(cro.ApiProvider):
    """Answers `end_ts` the way the venue does: trades with trade_time_ns <= end_ts."""

    def __init__(self, rows: list[dict]) -> None:
        super().__init__(api_key="dummy", api_secret="dummy", auth_required=False)
        self.rows = rows
        self.cursors: list[int] = []

    async def get(self, path, params=None, sign=False):  # noqa: ANN001, ANN001
        assert path == "public/get-trades", path
        end_ts = int(params["end_ts"])
        self.cursors.append(end_ts)
        return [row for row in self.rows if int(row["tn"]) <= end_ts][:PAGE_SIZE]


@pytest.fixture
def pair() -> cro.Pair:
    return cro.pairs.CRO_USD


@pytest.mark.asyncio
async def test_a_page_boundary_inside_a_busy_second_loses_no_trades(
    pair: cro.Pair,
) -> None:
    venue = ScriptedVenue(busy_tape())
    market = cro.Market(api=venue)

    trades = [t async for t in market.get_trades(pair, end_ts=BASE, count=None)]

    assert len(trades) == 230, (
        f"expected all 230 trades, got {len(trades)} — "
        f"{230 - len(trades)} lost at the page boundary"
    )
    in_busy = [t for t in trades if t.time == BUSY_SECOND]
    assert len(in_busy) == 30, (
        f"only {len(in_busy)} of 30 trades survived the busy second; a cursor aligned to a "
        "second boundary discards the rest of that second"
    )


@pytest.mark.asyncio
async def test_the_pagination_cursor_keeps_nanosecond_precision(pair: cro.Pair) -> None:
    """The property directly, not only through the total: no cursor may land on a second edge."""
    venue = ScriptedVenue(busy_tape())
    market = cro.Market(api=venue)

    _ = [t async for t in market.get_trades(pair, end_ts=BASE, count=None)]

    assert len(venue.cursors) >= 2, "fixture no longer crosses a page boundary"
    for cursor in venue.cursors[1:]:
        assert cursor % NS != 0, (
            f"cursor {cursor} is aligned to a second boundary; the venue's end_ts is "
            "nanoseconds, so the rest of that second is never requested"
        )


@pytest.mark.asyncio
async def test_the_requested_window_includes_its_final_second(pair: cro.Pair) -> None:
    """`end_ts` is documented in seconds, so the last second of the window belongs to it.

    Converting `end_ts` to the START of that second excluded every trade printed later in it —
    a window ending at 14:00:00 stopped at 13:59:59.999999999 and the caller never hears about it.
    """
    venue = ScriptedVenue([trade_row(BASE * NS + 500_000_000)])
    market = cro.Market(api=venue)

    trades = [t async for t in market.get_trades(pair, end_ts=BASE, count=None)]

    assert len(trades) == 1, (
        "a trade printed inside the requested final second must be yielded "
        f"(end_ts={BASE}, trade at {BASE}.5)"
    )
