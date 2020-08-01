import pytest

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_get_pairs(exchange: cro.Exchange):
    pairs = await exchange.get_pairs()
    keys = [
        'quote_currency', 'base_currency',
        'price_decimals', 'quantity_decimals'
    ]
    for pair_keys in pairs.values():
        assert sorted(keys) == sorted(pair_keys)

    for pair in pairs:
        assert pair in cro.Pair


@pytest.mark.asyncio
async def test_get_tickers(exchange: cro.Exchange):
    tickers = await exchange.get_tickers()
    keys = sorted(['b', 'k', 'a', 't', 'v', 'h', 'l', 'c'])
    for data in tickers.values():
        assert keys == sorted(data)
    sorted(p.value for p in tickers) == sorted(p.value for p in cro.Pair)
    ticker = await exchange.get_tickers(cro.Pair.BTC_USDT)
    assert keys == sorted(ticker)


@pytest.mark.asyncio
async def test_get_trades(exchange: cro.Exchange):
    trades = await exchange.get_trades(cro.Pair.CRO_USDT)
    keys = sorted(['p', 'q', 's', 'd', 't'])
    for trade in trades:
        assert sorted(trade) == keys


@pytest.mark.asyncio
async def test_get_price(exchange: cro.Exchange):
    price = await exchange.get_price(cro.Pair.CRO_USDT)
    assert price > 0


@pytest.mark.asyncio
async def test_get_orderbook(exchange: cro.Exchange):
    data = await exchange.get_orderbook(cro.Pair.CRO_USDT, depth=50)
    asks = data['asks']
    bids = data['bids']
    # price, quantity, number of orders
    assert asks and bids
    assert len(asks[0]) == 3
    assert len(bids[0]) == 3


@pytest.mark.asyncio
async def test_listen_candles(exchange: cro.Exchange):
    candles = []
    pairs = (cro.Pair.CRO_USDC, cro.Pair.USDC_USDT, cro.Pair.BTC_USDT)
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
    pairs = [cro.Pair.CRO_USDT, cro.Pair.BTC_USDT]
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
    pairs = [cro.Pair.CRO_USDT, cro.Pair.BTC_USDT]
    orderbooks = []

    async for orderbook in exchange.listen_orderbook(*pairs):
        orderbooks.append(orderbook)
        if set(pairs) == set(o.pair for o in orderbooks):
            break

    for book in orderbooks:
        assert book.buys and book.sells
        assert book.sells[0].price > book.buys[0].price
        assert book.spread > 0
