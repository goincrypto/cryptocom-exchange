import pytest

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
        assert ticker.volume > 0


@pytest.mark.asyncio
async def test_get_trades(exchange: cro.Exchange):
    trades = await exchange.get_trades(cro.pairs.CRO_USDT)
    for trade in trades:
        assert trade.price > 0
        assert trade.quantity > 0
        assert trade.side in cro.OrderSide
        assert trade.pair == cro.pairs.CRO_USDT


@pytest.mark.asyncio
async def test_get_price(exchange: cro.Exchange):
    price = await exchange.get_price(cro.pairs.CRO_USDT)
    assert price > 0.01


@pytest.mark.asyncio
async def test_get_orderbook(exchange: cro.Exchange):
    depth = 150
    book = await exchange.get_orderbook(cro.pairs.CRO_USDT)
    assert book.buys and book.sells
    assert book.sells[0].price > book.buys[0].price
    assert book.spread > 0
    assert len(book.sells) == len(book.buys) == depth


@pytest.mark.asyncio
async def test_get_candles(exchange: cro.Exchange):
    candles = await exchange.get_candles(cro.pairs.CRO_USDT, cro.Period.DAY)
    for candle in candles:
        assert candle.pair == cro.pairs.CRO_USDT
        assert candle.high >= candle.low


@pytest.mark.asyncio
async def test_listen_candles(exchange: cro.Exchange):
    candles = {}
    pairs = (
        cro.pairs.BTC_USDC,
        cro.pairs.ETH_USDT,
        cro.pairs.BTC_USDT,
        cro.pairs.ETH_USDC,
    )
    default_count = 1

    async for candle in exchange.listen_candles(cro.Period.MINS, *pairs):
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
    pairs = [cro.pairs.BTC_USDC, cro.pairs.BTC_USDT]
    pairs_seen = set()
    async for trade in exchange.listen_trades(*pairs):
        trades.append(trade)
        pairs_seen.add(trade.pair)
        if len(pairs_seen) == len(pairs) and len(trades) > 30:
            break


@pytest.mark.asyncio
async def test_listen_orderbook(exchange: cro.Exchange):
    pairs = [cro.pairs.CRO_USDT, cro.pairs.CRO_USDC]
    orderbooks = []
    depth = 150

    async for orderbook in exchange.listen_orderbook(*pairs):
        orderbooks.append(orderbook)
        if set(pairs) == set(o.pair for o in orderbooks):
            break

    for book in orderbooks:
        assert book.buys and book.sells
        assert book.sells[0].price > book.buys[0].price
        assert book.spread >= 0
        assert len(book.sells) == len(book.buys) == depth
