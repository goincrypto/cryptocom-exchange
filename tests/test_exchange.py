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


@pytest.mark.asyncio
async def test_get_tickers(exchange: cro.Exchange):
    tickers = await exchange.get_tickers()
    keys = sorted(['b', 'k', 'a', 't', 'v', 'h', 'l', 'c'])
    for data in tickers.values():
        assert keys == sorted(data)
    sorted(p.value for p in tickers) == sorted(p.value for p in cro.Pair)
    ticker = await exchange.get_tickers(cro.Pair.BTCUSDT)
    assert keys == sorted(ticker)


@pytest.mark.asyncio
async def test_get_trades(exchange: cro.Exchange):
    trades = await exchange.get_trades(cro.Pair.CROUSDT)
    keys = sorted(['p', 'q', 's', 'd', 't'])
    for trade in trades:
        assert sorted(trade) == keys


@pytest.mark.asyncio
async def test_get_price(exchange: cro.Exchange):
    price = await exchange.get_price(cro.Pair.CROUSDT)
    assert price > 0


@pytest.mark.asyncio
async def test_get_orderbook(exchange: cro.Exchange):
    data = await exchange.get_orderbook(cro.Pair.CROUSDT, depth=50)
    asks = data['asks']
    bids = data['bids']
    # price, quantity, number of orders
    assert asks and bids
    assert len(asks[0]) == 3
    assert len(bids[0]) == 3


# web-sockets will be added soon
# @pytest.mark.asyncio
# async def test_listen_candles(exchange: cro.Exchange):
#     candles = []
#     async for candle in exchange.listen_candles(cro.Pair.CROUSDT):
#         candles.append(candle)
#         break
#     assert isinstance(candles[-1], cro.Candle)


# @pytest.mark.asyncio
# async def test_listen_trades(exchange: cro.Exchange):
#     all_trades = []
#     async for trades in exchange.listen_trades(cro.Pair.CROUSDT):
#         all_trades.extend(trades)
#         break
#     keys = sorted(['amount', 'price', 'ds', 'id', 'side', 'ts', 'vol'])
#     assert sorted(all_trades[0]) == keys


# @pytest.mark.asyncio
# async def test_listen_orderbook(exchange: cro.Exchange):
#     async for orders in exchange.listen_order_book(
#             cro.Pair.CROUSDT):
#         asks = orders['asks']
#         bids = orders['bids']
#         assert asks and bids
#         assert len(asks[0]) == 2
#         assert len(bids[0]) == 2
#         break
