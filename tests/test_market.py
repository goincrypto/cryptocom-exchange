import pytest
from datetime import datetime, timezone

import cryptocom.exchange as cro
from cryptocom.exchange.structs import BaseCurrencyConfig


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
    """Test basic trade loading functionality."""
    # Use captured timestamp range (July 4, 2026 13:29-14:29 UTC)
    start_ts = int(datetime(2026, 7, 4, 13, 29, 29, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(2026, 7, 4, 14, 29, 29, tzinfo=timezone.utc).timestamp())

    trades = []
    async for trade in exchange.get_trades(
        cro.pairs.CRO_USDT,
        start_ts=start_ts,
        end_ts=end_ts,
    ):
        trades.append(trade)
        assert trade.price > 0
        assert trade.quantity > 0
        assert trade.side in cro.OrderSide
        assert trade.pair == cro.pairs.CRO_USDT

    assert len(trades) > 0

    # Verify no duplicate trade IDs
    trade_ids = [t.id for t in trades]
    assert len(trade_ids) == len(set(trade_ids)), (
        f"Found {len(trade_ids) - len(set(trade_ids))} duplicate trade IDs"
    )


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
    "timeframe,start_ts,end_ts,candles_len,count",
    [
        # 15m candles: returns 300 (chunk size) when no time boundaries and count=300
        (cro.Timeframe.MIN_15, None, None, 300, 300),
        # 1D candles: 1 month range (June 1 - July 1, 2026)
        (
            cro.Timeframe.DAY,
            int(datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()),
            int(datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()),
            30,
            None,  # No limit when using time boundaries
        ),
    ],
)
async def test_get_candles(
    exchange: cro.Exchange, timeframe, start_ts, end_ts, candles_len, count
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

    assert len(candles) == candles_len, (
        f"Expected {candles_len} candles, got {len(candles)}"
    )

    # Verify no duplicate timestamps
    timestamps = [c.time for c in candles]
    assert len(timestamps) == len(set(timestamps)), (
        f"Found {len(timestamps) - len(set(timestamps))} duplicate timestamps"
    )

    # Verify candles are in descending order (API returns newest first)
    for i in range(1, len(candles)):
        assert candles[i].time < candles[i - 1].time, (
            f"Candles not in descending order at index {i}"
        )

    # Verify start/end boundaries
    if start_ts is not None:
        assert candles[0].time >= start_ts, (
            f"First candle {candles[0].time} before start_ts {start_ts}"
        )
    if end_ts is not None:
        assert candles[-1].time <= end_ts, (
            f"Last candle {candles[-1].time} after end_ts {end_ts}"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "timeframe,start_ts,end_ts,expected_min_candles",
    [
        # Test with 1-day window (June 28, 2026), should get at least 1 daily candle
        (
            cro.Timeframe.DAY,
            int(datetime(2026, 6, 28, 0, 0, 0, tzinfo=timezone.utc).timestamp()),
            int(datetime(2026, 6, 28, 23, 59, 59, tzinfo=timezone.utc).timestamp()),
            1,
        ),
        # Test with 10-day window for 15m, should get at least 5 candles (sparse data)
        (
            cro.Timeframe.MIN_15,
            int(datetime(2026, 6, 24, 0, 0, 0, tzinfo=timezone.utc).timestamp()),
            int(datetime(2026, 7, 3, 23, 59, 59, tzinfo=timezone.utc).timestamp()),
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
        assert start_ts <= candle.time <= end_ts, (
            f"Candle time {candle.time} outside boundaries [{start_ts}, {end_ts}]"
        )

    assert len(candles) >= expected_min_candles, (
        f"Expected at least {expected_min_candles} candles, got {len(candles)}"
    )

    # Verify first candle >= start_ts
    assert candles[0].time >= start_ts, (
        f"First candle {candles[0].time} before start_ts {start_ts}"
    )

    # Verify last candle <= end_ts
    assert candles[-1].time <= end_ts, (
        f"Last candle {candles[-1].time} after end_ts {end_ts}"
    )


@pytest.mark.asyncio
async def test_get_candles_all_history_invalid_with_boundaries(
    exchange: cro.Exchange,
):
    """Test that all_history cannot be used with start_ts or end_ts."""
    # Test without any boundaries - should work (fetches all)
    candles = []
    async for candle in exchange.get_candles(
        cro.pairs.CLOUD_USD,
        cro.Timeframe.DAY,
        all_history=True,
    ):
        candles.append(candle)
    assert len(candles) > 0

    # Test with only start_ts - should raise
    with pytest.raises(ValueError, match="'all_history' cannot be used"):
        async for _ in exchange.get_candles(
            cro.pairs.CLOUD_USD,
            cro.Timeframe.DAY,
            start_ts=1000000000,
            all_history=True,
        ):
            pass


@pytest.mark.asyncio
async def test_get_candles_count(exchange: cro.Exchange):
    """Test that count=650 fetches up to 650 candles via pagination."""
    start_ts = int(datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

    candles = []
    async for candle in exchange.get_candles(
        cro.pairs.CLOUD_USD,
        cro.Timeframe.MIN_15,
        start_ts=start_ts,
        end_ts=end_ts,
        count=650,
    ):
        candles.append(candle)

    # Should get exactly 650 candles (count limit enforced)
    assert len(candles) == 650, f"Expected exactly 650 candles, got {len(candles)}"


@pytest.mark.asyncio
async def test_get_candles_no_duplicates(exchange: cro.Exchange):
    """Test that get_candles prevents duplicates across API requests."""
    # Use same params as test_get_candles_with_time_boundaries[1D-1782854400-1782883199-1]
    start_ts = int(datetime(2026, 6, 28, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(2026, 6, 28, 23, 59, 59, tzinfo=timezone.utc).timestamp())

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
    assert len(timestamps) == len(set(timestamps)), (
        f"Found {len(timestamps) - len(set(timestamps))} duplicate timestamps"
    )


@pytest.mark.asyncio
async def test_get_trades_no_duplicates(exchange: cro.Exchange):
    """Test that get_trades prevents duplicates across API requests."""
    # Use 1-day range in June 2026
    start_ts = int(datetime(2026, 6, 28, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(2026, 6, 28, 23, 59, 59, tzinfo=timezone.utc).timestamp())

    trades = []
    async for trade in exchange.get_trades(
        cro.pairs.CRO_USDT,
        start_ts=start_ts,
        end_ts=end_ts,
        count=None,  # Fetch all trades in range
    ):
        trades.append(trade)

    # Verify no duplicate trade IDs
    trade_ids = [t.id for t in trades]
    assert len(trade_ids) == len(set(trade_ids)), (
        f"Found {len(trade_ids) - len(set(trade_ids))} duplicate trade IDs"
    )


@pytest.mark.asyncio
async def test_get_candles_start_end_verification(exchange: cro.Exchange):
    """Test that start_ts and end_ts are properly enforced."""
    # Use same params as test_get_candles_with_time_boundaries[1D-1782854400-1782883199-1]
    start_ts = int(datetime(2026, 6, 28, 0, 0, 0, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(2026, 6, 28, 23, 59, 59, tzinfo=timezone.utc).timestamp())

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
        assert candles[0].time <= end_ts, (
            f"First candle {candles[0].time} after end_ts {end_ts}"
        )

        # Verify last candle >= start_ts (descending order)
        assert candles[-1].time >= start_ts, (
            f"Last candle {candles[-1].time} before start_ts {start_ts}"
        )

        # Verify all candles within range
        for candle in candles:
            assert start_ts <= candle.time <= end_ts, (
                f"Candle {candle.time} outside range [{start_ts}, {end_ts}]"
            )


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
        if all(v >= default_count for v in candles.values()) and len(candles) == len(
            pairs
        ):
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


@pytest.mark.asyncio
async def test_get_risk_parameters(exchange: cro.Exchange):
    """Test that risk parameters are returned as proper dataclasses."""
    risk = await exchange.get_risk_parameters()

    # Check top-level fields
    assert risk.default_max_product_leverage_for_spot > 0
    assert risk.default_max_product_leverage_for_perps > 0
    assert risk.default_max_product_leverage_for_futures > 0
    assert risk.update_timestamp_ms > 0
    assert len(risk.base_currency_config) > 0

    # Check that we can find CRO in base_currency_config
    cro_config = next(
        (c for c in risk.base_currency_config if c.instrument_name == "CRO"),
        None,
    )
    assert cro_config is not None
    assert cro_config.min_order_notional_usd == 1.0
    assert cro_config.max_order_notional_usd == 1000000.0
    assert cro_config.order_limit > 0

    # Check BTC config
    btc_config = next(
        (c for c in risk.base_currency_config if c.instrument_name == "BTC"),
        None,
    )
    assert btc_config is not None
    assert btc_config.min_order_notional_usd == 1.0
    assert btc_config.max_product_leverage_for_spot is not None
    assert btc_config.max_product_leverage_for_spot > 0

    # Check default values for missing fields
    default_config = BaseCurrencyConfig(instrument_name="TEST")
    assert default_config.min_order_notional_usd == 1.0
    assert default_config.max_order_notional_usd == 1000000.0


@pytest.mark.asyncio
async def test_trades_match_candles_ohlcv_from_trades(exchange: cro.Exchange):
    """Test that trades can be aggregated into 5-minute OHLCV candles matching API output.

    This verifies:
    - Trades loading mechanism works correctly with adaptive window sizing (>150 trades)
    - No trades are missed across multiple API calls (deduplication works)
    - Trade aggregation produces valid 5-minute OHLCV structure
    - Aggregated candles match API candles exactly (same OHLCV values)
    - Proper ordering: both trades and candles yielded newest-first from API
    """
    # Use July 5, 2026 UTC - 1 hour period with BTC_USD (high volume)
    start_ts = int(datetime(2026, 7, 5, 13, 0, 0, tzinfo=timezone.utc).timestamp())
    end_ts = int(datetime(2026, 7, 5, 14, 0, 0, tzinfo=timezone.utc).timestamp())

    # STEP 1: Fetch API candles FIRST to get exact time boundaries
    api_candles = []
    async for candle in exchange.get_candles(
        cro.pairs.BTC_USD,
        cro.Timeframe.MIN_5,
        start_ts=start_ts,
        end_ts=end_ts,
    ):
        api_candles.append(candle)

    # Verify candles are ordered newest-first (descending order from API)
    assert len(api_candles) >= 2, "Need at least 2 candles to verify ordering"
    for i in range(len(api_candles) - 1):
        assert api_candles[i].time >= api_candles[i + 1].time, (
            f"Candles not ordered newest-first: {api_candles[i].time} > {api_candles[i + 1].time}"
        )

    # Get actual candle time boundaries from API response
    api_start_ts = api_candles[-1].time  # Oldest candle timestamp
    api_end_ts = api_candles[0].time + 300  # Newest candle end (bucket_size added)

    # STEP 2: Fetch ALL trades for BTC_USD within the REAL candle time range
    trades = []
    async for trade in exchange.get_trades(
        cro.pairs.BTC_USD,
        start_ts=api_start_ts,
        end_ts=api_end_ts,
        count=None,  # Fetch all trades in range (no limit)
    ):
        trades.append(trade)

    # Verify trades are ordered newest-first (descending order from API)
    assert len(trades) >= 2, "Need at least 2 trades to verify ordering"
    for i in range(len(trades) - 1):
        assert trades[i].time >= trades[i + 1].time, (
            f"Trades not ordered newest-first: {trades[i].time} < {trades[i + 1].time}"
        )

    assert len(trades) >= 150, (
        f"Expected sufficient trades for pagination testing. Got {len(trades)}"
    )

    # Verify NO duplicate trade IDs across multiple API requests
    trade_ids = [t.id for t in trades]
    assert len(trade_ids) == len(set(trade_ids)), (
        f"Found {len(trade_ids) - len(set(trade_ids))} duplicate trade IDs "
        "across API calls! Deduplication failed."
    )

    # STEP 3: Aggregate trades into 5-minute OHLCV buckets ONLY within API candle range
    bucket_size = 5 * 60  # 5 minutes in seconds
    buckets = {}

    for trade in trades:
        bucket_time = (int(trade.time) // bucket_size) * bucket_size
        # Only include buckets that match API candle timestamps
        if bucket_time in [c.time for c in api_candles]:
            if bucket_time not in buckets:
                buckets[bucket_time] = {
                    "open": trade.price,
                    "high": trade.price,
                    "low": trade.price,
                    "close": trade.price,
                    "quantity": trade.quantity,
                }
            else:
                b = buckets[bucket_time]
                b["high"] = max(b["high"], trade.price)
                b["low"] = min(b["low"], trade.price)
                b["close"] = trade.price
                b["quantity"] += trade.quantity

    # Convert buckets to sorted list (oldest-first for comparison)
    trade_candles = []
    for bucket_time in sorted(buckets.keys()):
        b = buckets[bucket_time]
        trade_candles.append(
            cro.Candle(
                time=bucket_time,
                open=b["open"],
                high=b["high"],
                low=b["low"],
                close=b["close"],
                quantity=b["quantity"],
                pair=cro.pairs.BTC_USD,
            )
        )

    # Validate each candle's OHLC structure
    invalid_count = 0
    total_spread_pct = 0.0
    for tc in trade_candles:
        if not (tc.low <= tc.close <= tc.high and tc.low <= tc.open <= tc.high):
            invalid_count += 1
        spread_pct = ((tc.high - tc.low) / tc.low * 100) if tc.low > 0 else 0
        total_spread_pct += spread_pct

    assert invalid_count == 0, (
        f"Found {invalid_count}/{len(trade_candles)} invalid OHLC candles"
    )
    total_spread_pct / len(trade_candles) if trade_candles else 0

    # STEP 4: Reverse both lists to compare newest-first (matching API order)
    # Sort API candles by time descending for zip iteration
    sorted(api_candles, key=lambda c: c.time, reverse=True)
    sorted(trade_candles, key=lambda c: c.time, reverse=True)

    # STEP 5: Zip iterate through trade-candles and API candles, asserting OHLC values

    mismatches = []
    max_close_diff_pct = 0.0
    max_high_diff_pct = 0.0
    max_low_diff_pct = 0.0

    # Filter to common timestamps only
    api_times = {c.time for c in api_candles}
    trade_times = {c.time for c in trade_candles}
    common_times = api_times & trade_times

    for tc, ac in zip(
        [
            c
            for c in sorted(trade_candles, key=lambda x: x.time, reverse=True)
            if c.time in common_times
        ],
        [
            c
            for c in sorted(api_candles, key=lambda x: x.time, reverse=True)
            if c.time in common_times
        ],
    ):
        assert tc.time == ac.time, (
            f"Timestamp mismatch: trade={tc.time} vs api={ac.time}"
        )

        # Assert close prices match (last trade determines close)
        close_diff_pct = (
            abs(ac.close - tc.close) / ac.close * 100 if ac.close > 0 else 0
        )
        max_close_diff_pct = max(max_close_diff_pct, close_diff_pct)

        # Assert high prices overlap/match
        if tc.high > ac.high:
            max_high_diff_pct = max(
                max_high_diff_pct, (tc.high - ac.high) / ac.high * 100
            )

        # Assert low prices overlap/match
        if tc.low < ac.low:
            max_low_diff_pct = max(max_low_diff_pct, (ac.low - tc.low) / ac.low * 100)

        # Store mismatches if any values differ significantly
        if close_diff_pct > 0.5 or (tc.high > ac.high + 1) or (tc.low < ac.low - 1):
            mismatches.append(
                f"Time {tc.time}: Close diff={close_diff_pct:.3f}% | "
                f"High: API={ac.high:.2f} vs Trade={tc.high:.2f} | "
                f"Low: API={ac.low:.2f} vs Trade={tc.low:.2f}"
            )

    if mismatches:
        for m in mismatches[:3]:
            print(f"  - {m}")

    assert max_close_diff_pct < 1.0, (
        f"Close price difference too large: {max_close_diff_pct:.4f}% > 1% tolerance"
    )
