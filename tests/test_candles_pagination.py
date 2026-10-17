"""Candle pagination: no lost bars, and a bar opening exactly at `end_ts` is still a candle.

Two different things are pinned here, and they behave differently:

INSIDE a window - candle pagination is sound. A bar is one row per timeframe and the cursor is
set to the oldest bar's own timestamp, so unlike `get_trades` (where hundreds of prints share a
second and a second-granular cursor discarded all but the first) nothing can hide between rows.
Measured live on CRO_USD: 30 days of M5 through `get_candles` = 8,640 bars, 0 gaps, 0 duplicates.
Scripted below, so the property is checked without the network.

THE UPPER EDGE - documented, not fixed. `end_ts` is sent as `end_ts * 1000`, and the venue's
candle boundary is EXCLUSIVE, so a bar OPENING exactly at `end_ts` is not returned:

    end_ts = T        -> newest bar returned is T - 300
    end_ts = T + 999ms -> newest bar returned is T

This is the one place candle and trade pagination could look analogous, and it is not: a candle
row's timestamp is its OPEN time, so the bar in question trades entirely after `end_ts` (or has
just opened and is empty), and no bar can open "later inside" the final second, because opens land
on whole-second multiples of the timeframe. The venue's exclusive reading of "up to end_ts" is the
defensible one even though the yield filter treats `time == end_ts` as inside the window. The test
below pins that behavior so changing it is a decision rather than a surprise. Widening the window
here, by analogy to the trades fix, would hand a live caller a just-opened empty bar.
"""

import pytest

import cryptocom.exchange as cro

STEP = 300  # M5, seconds
PAGE_SIZE = 300
BASE = 1_780_000_000 - (1_780_000_000 % STEP)


def candle_row(time_s: int) -> dict:
    """One row in the shape `public/get-candlestick` answers (t/o/h/l/c/v)."""
    price = f"{0.05 + (time_s % 97) / 100000:.5f}"
    return {
        "t": time_s * 1000,
        "o": price,
        "h": price,
        "l": price,
        "c": price,
        "v": "12345.6",
    }


def tape(bars: int) -> list[dict]:
    return [candle_row(BASE + i * STEP) for i in range(bars)]


class ScriptedVenue(cro.ApiProvider):
    """Answers candles the way the venue does.

    Ascending order in the response, and an EXCLUSIVE `end_ts`: measured against the live API
    (see the module docstring), so `t == end_ts` is not returned. A scripted venue that returned
    everything, or used `<=`, would make the upper-edge test pass for the wrong reason.
    """

    def __init__(self, rows: list[dict]) -> None:
        super().__init__(api_key="dummy", api_secret="dummy", auth_required=False)
        self.rows = rows
        self.cursors: list[int] = []

    async def get(self, path, params=None, sign=False):  # noqa: ANN001
        assert path == "public/get-candlestick", path
        end_ts = int(params["end_ts"])
        self.cursors.append(end_ts)
        eligible = [r for r in self.rows if int(r["t"]) < end_ts]
        return eligible[-PAGE_SIZE:]


@pytest.fixture
def pair() -> cro.Pair:
    return cro.pairs.CRO_USD


@pytest.mark.asyncio
async def test_a_bar_opening_exactly_at_end_ts_is_not_part_of_the_window(
    pair: cro.Pair,
) -> None:
    """Characterization test - it pins today's boundary, it does not endorse it.

    A caller that aligns to the timeframe (`now // 300 * 300`, or a bar's own timestamp) does not
    get the bar opening at that instant, because the venue's candle boundary is exclusive and the
    request is sent at the second's start. See the module docstring for why that reading is the
    defensible one for open-timed bars. If this test starts failing, the boundary changed: make
    sure that was the plan, and re-read what it means for `end_ts = now` on a live pair.
    """
    venue = ScriptedVenue(tape(6))
    market = cro.Market(api=venue)
    last_bar = BASE + 5 * STEP

    times = [
        c.time
        async for c in market.get_candles(
            pair, cro.Timeframe.MIN_5, start_ts=BASE, end_ts=last_bar, count=None
        )
    ]

    assert last_bar not in times, (
        "a bar opening exactly at end_ts entered the window; its trades all happen after "
        "end_ts, so this changes what 'candles up to end_ts' returns for every caller"
    )
    assert times == [BASE + i * STEP for i in range(5)][::-1], (
        f"expected the five bars that closed by end_ts, got {sorted(times)}"
    )


@pytest.mark.asyncio
async def test_a_multi_page_candle_walk_yields_a_contiguous_sequence(
    pair: cro.Pair,
) -> None:
    """Three pages, no gaps, no duplicates - the property `get_trades` failed."""
    bars = 700  # 300 + 300 + 100
    venue = ScriptedVenue(tape(bars))
    market = cro.Market(api=venue)
    last_bar = BASE + (bars - 1) * STEP
    # One second before the NEXT bar opens: `end_ts` on a bar's own open would exclude that bar
    # (pinned by the test above), which is a boundary question, not the contiguity one.
    end_ts = BASE + bars * STEP - 1

    times = sorted(
        [
            c.time
            async for c in market.get_candles(
                pair, cro.Timeframe.MIN_5, start_ts=BASE, end_ts=end_ts, count=None
            )
        ],
        reverse=True,
    )

    assert len(venue.cursors) >= 3, "fixture no longer crosses a page boundary"
    assert len(times) == len(set(times)) == bars, (
        f"expected {bars} distinct bars, got {len(times)} ({len(set(times))} distinct)"
    )
    assert times[0] == last_bar, "the newest bar is missing"
    assert times[-1] == BASE, "the oldest bar is missing"
    steps = {a - b for a, b in zip(times, times[1:])}
    assert steps == {STEP}, (
        f"bar spacing is not uniform ({sorted(steps)}); a bar was skipped"
    )
