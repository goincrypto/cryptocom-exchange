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
        assert ticker.high > ticker.low
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
    depth = 50
    book = await exchange.get_orderbook(cro.pairs.CRO_USDT, depth=depth)
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
    candles = []
    pairs = (cro.pairs.CRO_USDC, cro.pairs.USDC_USDT, cro.pairs.BTC_USDT)
    count = 0
    default_count = 300

    async for candle in exchange.listen_candles(cro.Period.MINS, *pairs):
        candles.append(candle)
        count += 1
        if count == len(pairs) * default_count:
            break

    for pair in pairs:
        assert len([
            c for c in candles if c.pair == pair
        ]) == default_count


@pytest.mark.asyncio
async def test_listen_trades(exchange: cro.Exchange):
    trades = []
    count = 0
    pairs = [cro.pairs.CRO_USDT, cro.pairs.BTC_USDT]
    pairs_seen = set()
    async for trade in exchange.listen_trades(*pairs):
        trades.append(trade)
        pairs_seen.add(trade.pair)
        if count > 100:
            break
        count += 1

    assert len(pairs_seen) == len(pairs)


@pytest.mark.asyncio
async def test_listen_orderbook(exchange: cro.Exchange):
    pairs = [cro.pairs.CRO_USDT, cro.pairs.BTC_USDT]
    orderbooks = []
    depth = 50

    async for orderbook in exchange.listen_orderbook(*pairs, depth=depth):
        orderbooks.append(orderbook)
        if set(pairs) == set(o.pair for o in orderbooks):
            break

    for book in orderbooks:
        assert book.buys and book.sells
        assert book.sells[0].price > book.buys[0].price
        assert book.spread > 0
        assert len(book.sells) == len(book.buys) == depth
