import pytest

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_get_symbols(exchange: cro.Exchange):
    data = await exchange.get_symbols()
    symbols = [d['symbol'] for d in data]
    assert sorted(symbols) == sorted(s.value for s in cro.Symbol)


@pytest.mark.asyncio
async def test_get_tickers(exchange: cro.Exchange):
    tickers = await exchange.get_tickers()
    keys = sorted(['amount', 'close', 'high', 'open', 'low', 'rose', 'vol'])
    for data in tickers.values():
        assert keys == sorted(data)
    ticker = await exchange.get_ticker(cro.Symbol.BTCUSDT)
    assert keys == sorted(ticker)


@pytest.mark.asyncio
async def test_get_candles(exchange: cro.Exchange):
    candles = await exchange.get_candles(cro.Symbol.CROUSDT, cro.Period.D1)
    assert len(candles) > 10
    assert isinstance(candles[-1], cro.Candle)


@pytest.mark.asyncio
async def test_get_trades(exchange: cro.Exchange):
    trades = await exchange.get_trades(cro.Symbol.CROUSDT)
    keys = sorted(['amount', 'price', 'ctime', 'id', 'type'])
    for trade in trades:
        assert sorted(trade) == keys


@pytest.mark.asyncio
async def test_get_prices(exchange: cro.Exchange):
    prices = await exchange.get_prices()
    assert prices[cro.Symbol.BTCUSDT.value]


@pytest.mark.asyncio
async def test_get_orderbook(exchange: cro.Exchange):
    data = await exchange.get_orderbook(cro.Symbol.CROUSDT, cro.Depth.HIGH)
    asks = data['asks']
    bids = data['bids']
    assert asks and bids
    assert len(asks[0]) == 2
    assert len(bids[0]) == 2


@pytest.mark.asyncio
async def test_listen_candles(exchange: cro.Exchange):
    candles = []
    async for candle in exchange.listen_candles(cro.Symbol.CROUSDT):
        candles.append(candle)
        break
    assert isinstance(candles[-1], cro.Candle)


@pytest.mark.asyncio
async def test_listen_trades(exchange: cro.Exchange):
    all_trades = []
    async for trades in exchange.listen_trades(cro.Symbol.CROUSDT):
        all_trades.extend(trades)
        break
    keys = sorted(['amount', 'price', 'ds', 'id', 'side', 'ts', 'vol'])
    assert sorted(all_trades[0]) == keys


@pytest.mark.asyncio
async def test_listen_orderbook(exchange: cro.Exchange):
    async for orders in exchange.listen_order_book(
            cro.Symbol.CROUSDT, cro.Depth.HIGH):
        asks = orders['asks']
        bids = orders['bids']
        assert asks and bids
        assert len(asks[0]) == 2
        assert len(bids[0]) == 2
        break
