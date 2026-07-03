import pytest
from datetime import datetime

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_get_pairs(exchange: cro.Exchange):
    pairs = await exchange.get_pairs()
    assert sorted(exchange.pairs.keys()) == sorted(p.name for p in pairs)
    local_pairs = sorted(cro.pairs.all(), key=lambda p: p.name)
    server_pairs = sorted(pairs, key=lambda p: p.name)
    for local_pair, server_pair in zip(local_pairs, server_pairs):
        assert server_pair == local_pair, server_pair
    assert len(local_pairs) == len(server_pairs)


@pytest.mark.asyncio
async def test_get_tickers(exchange: cro.Exchange):
    tickers = await exchange.get_tickers()
    for pair, ticker in tickers.items():
        assert ticker.high >= ticker.low
        assert ticker.pair == pair
        assert ticker.volume >= 0


@pytest.mark.asyncio
async def test_get_trades(exchange: cro.Exchange):
    trades = []
    async for trade in exchange.get_trades(cro.pairs.CRO_USDT):
        trades.append(trade)
        assert trade.price > 0
        assert trade.quantity > 0
        assert trade.side in cro.OrderSide
        assert trade.pair == cro.pairs.CRO_USDT

    assert len(trades) > 0

    # Verify no duplicate trade IDs
    trade_ids = [t.id for t in trades]
    assert len(trade_ids) == len(
        set(trade_ids)
    ), f"Found {len(trade_ids) - len(set(trade_ids))} duplicate trade IDs"


@pytest.mark.asyncio
async def test_get_price(exchange: cro.Exchange):
    price = await exchange.get_price(cro.pairs.CRO_USDT)
    assert price > 0.01


@pytest.mark.asyncio
async def test_get_orderbook(exchange: cro.Exchange):
    depth = 50
    book = await exchange.get_orderbook(cro.pairs.CRO_USDT, depth=depth)
    assert book.buys and book.sells
    assert book.sells[0].price > book.buys[0].price
    assert book.spread > 0
    assert len(book.sells) == len(book.buys) == depth


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timeframe,start_ts,end_ts,count,candles_len",
    [
        # 15m candles: 50 candles (no time boundaries)
        (cro.Timeframe.MIN_15, None, None, 50, 50),
        # 1D candles: 1 month range (June 1 - July 1, 2026)
        (
            cro.Timeframe.DAY,
            int(datetime(2026, 6, 1, 0, 0, 0).timestamp()),
            int(datetime(2026, 7, 1, 0, 0, 0).timestamp()),
            30,
            30,
        ),
    ],
)
async def test_get_candles(
    exchange: cro.Exchange, timeframe, start_ts, end_ts, count, candles_len
):
    candles = []
    async for candle in exchange.get_candles(
        cro.pairs.CLOUD_USD,
        timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
        count=count,
    ):
        candles.append(candle)
        assert candle.pair == cro.pairs.CLOUD_USD
        assert candle.high >= candle.low

    assert (
        len(candles) == candles_len
    ), f"Expected {candles_len} candles, got {len(candles)}"

    # Verify no duplicate timestamps
    timestamps = [c.time for c in candles]
    assert len(timestamps) == len(
        set(timestamps)
    ), f"Found {len(timestamps) - len(set(timestamps))} duplicate timestamps"

    # Verify candles are in descending order (API returns newest first)
    for i in range(1, len(candles)):
        assert (
            candles[i].time < candles[i - 1].time
        ), f"Candles not in descending order at index {i}"

    # Verify start/end boundaries
    if start_ts is not None:
        assert (
            candles[0].time >= start_ts
        ), f"First candle {candles[0].time} before start_ts {start_ts}"
    if end_ts is not None:
        assert (
            candles[-1].time <= end_ts
        ), f"Last candle {candles[-1].time} after end_ts {end_ts}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timeframe,start_ts,end_ts,expected_min_candles",
    [
        # Test with 1-day window (June 28, 2026), should get at least 1 daily candle
        (
            cro.Timeframe.DAY,
            int(datetime(2026, 6, 28, 0, 0, 0).timestamp()),
            int(datetime(2026, 6, 28, 23, 59, 59).timestamp()),
            1,
        ),
        # Test with 10-day window for 15m, should get at least 5 candles (sparse data)
        (
            cro.Timeframe.MIN_15,
            int(datetime(2026, 6, 24, 0, 0, 0).timestamp()),
            int(datetime(2026, 7, 3, 23, 59, 59).timestamp()),
            5,
        ),
    ],
)
async def test_get_candles_with_time_boundaries(
    exchange: cro.Exchange,
    timeframe,
    start_ts,
    end_ts,
    expected_min_candles,
):
    """Test that candles respect time boundaries."""
    candles = []
    async for candle in exchange.get_candles(
        cro.pairs.CLOUD_USD,
        timeframe,
        start_ts=start_ts,
        end_ts=end_ts,
    ):
        candles.append(candle)
        assert (
            start_ts <= candle.time <= end_ts
        ), f"Candle time {candle.time} outside boundaries [{start_ts}, {end_ts}]"

    assert (
        len(candles) >= expected_min_candles
    ), f"Expected at least {expected_min_candles} candles, got {len(candles)}"

    # Verify first candle >= start_ts
    assert (
        candles[0].time >= start_ts
    ), f"First candle {candles[0].time} before start_ts {start_ts}"

    # Verify last candle <= end_ts
    assert (
        candles[-1].time <= end_ts
    ), f"Last candle {candles[-1].time} after end_ts {end_ts}"


@pytest.mark.asyncio
async def test_get_candles_include_all_with_boundaries_error(
    exchange: cro.Exchange,
):
    """Test that include_all with time boundaries raises ValueError."""
    with pytest.raises(ValueError, match="include_all cannot be used"):
        async for _ in exchange.get_candles(
            cro.pairs.CLOUD_USD,
            cro.Timeframe.DAY,
            start_ts=1234567890,
            end_ts=1234567890,
            include_all=True,
        ):
            pass


@pytest.mark.asyncio
async def test_get_candles_no_duplicates(exchange: cro.Exchange):
    """Test that get_candles prevents duplicates across API requests."""
    # Use same params as test_get_candles_with_time_boundaries[1D-1782854400-1782883199-1]
    start_ts = int(datetime(2026, 6, 28, 0, 0, 0).timestamp())
    end_ts = int(datetime(2026, 6, 28, 23, 59, 59).timestamp())

    candles = []
    async for candle in exchange.get_candles(
        cro.pairs.CLOUD_USD,
        cro.Timeframe.DAY,
        start_ts=start_ts,
        end_ts=end_ts,
    ):
        candles.append(candle)

    # Verify no duplicate timestamps
    timestamps = [c.time for c in candles]
    assert len(timestamps) == len(
        set(timestamps)
    ), f"Found {len(timestamps) - len(set(timestamps))} duplicate timestamps"


@pytest.mark.asyncio
async def test_get_trades_no_duplicates(exchange: cro.Exchange):
    """Test that get_trades prevents duplicates across API requests."""
    # Use 1-day range in June 2026
    start_ts = int(datetime(2026, 6, 28, 0, 0, 0).timestamp())
    end_ts = int(datetime(2026, 6, 28, 23, 59, 59).timestamp())

    trades = []
    async for trade in exchange.get_trades(
        cro.pairs.CRO_USDT,
        start_ts=start_ts,
        end_ts=end_ts,
    ):
        trades.append(trade)

    # Verify no duplicate trade IDs
    trade_ids = [t.id for t in trades]
    assert len(trade_ids) == len(
        set(trade_ids)
    ), f"Found {len(trade_ids) - len(set(trade_ids))} duplicate trade IDs"


@pytest.mark.asyncio
async def test_get_candles_start_end_verification(exchange: cro.Exchange):
    """Test that start_ts and end_ts are properly enforced."""
    # Use same params as test_get_candles_with_time_boundaries[1D-1782854400-1782883199-1]
    start_ts = int(datetime(2026, 6, 28, 0, 0, 0).timestamp())
    end_ts = int(datetime(2026, 6, 28, 23, 59, 59).timestamp())

    candles = []
    async for candle in exchange.get_candles(
        cro.pairs.CLOUD_USD,
        cro.Timeframe.DAY,
        start_ts=start_ts,
        end_ts=end_ts,
    ):
        candles.append(candle)

    if candles:
        # Verify first candle <= end_ts (descending order)
        assert (
            candles[0].time <= end_ts
        ), f"First candle {candles[0].time} after end_ts {end_ts}"

        # Verify last candle >= start_ts (descending order)
        assert (
            candles[-1].time >= start_ts
        ), f"Last candle {candles[-1].time} before start_ts {start_ts}"

        # Verify all candles within range
        for candle in candles:
            assert (
                start_ts <= candle.time <= end_ts
            ), f"Candle {candle.time} outside range [{start_ts}, {end_ts}]"


@pytest.mark.asyncio
async def test_listen_candles(exchange: cro.Exchange):
    candles = {}
    pairs = (
        cro.pairs.BTC_USD,
        cro.pairs.ETH_USDT,
        cro.pairs.BTC_USDT,
        cro.pairs.ETH_USD,
    )
    default_count = 1

    async for candle in exchange.listen_candles(cro.Timeframe.MIN, *pairs):
        candles.setdefault(candle.pair, 0)
        candles[candle.pair] += 1
        if all(v >= default_count for v in candles.values()) and len(
            candles
        ) == len(pairs):
            break

    for pair in pairs:
        assert candles[pair] >= default_count


@pytest.mark.asyncio
async def test_listen_trades(exchange: cro.Exchange):
    trades = []
    pairs = [cro.pairs.BTC_USD, cro.pairs.BTC_USDT]
    pairs_seen = set()
    async for trade in exchange.listen_trades(*pairs):
        trades.append(trade)
        pairs_seen.add(trade.pair)
        if len(pairs_seen) == len(pairs) and len(trades) > 30:
            break


@pytest.mark.asyncio
async def test_listen_orderbook(exchange: cro.Exchange):
    pairs = [cro.pairs.CRO_USDT, cro.pairs.CRO_USD]
    orderbooks = []
    depth = 50

    async for orderbook in exchange.listen_orderbook(*pairs):
        orderbooks.append(orderbook)
        if set(pairs) == set(o.pair for o in orderbooks):
            break

    for book in orderbooks:
        assert book.buys and book.sells
        assert book.sells[0].price > book.buys[0].price
        assert book.spread >= 0
        assert len(book.sells) == len(book.buys) == depth
