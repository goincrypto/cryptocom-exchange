import os
import asyncio
import aiohttp
import datetime

import pytest

import cryptocom.exchange as cro


@pytest.fixture
def exchange() -> cro.Exchange:
    return cro.Exchange()


@pytest.fixture
@pytest.mark.asyncio
async def account() -> cro.Account:
    acc = cro.Account(from_env=True)
    yield acc
    await acc.cancel_open_orders(cro.Symbol.CROUSDT)


def test_api_args(monkeypatch):
    with pytest.raises(ValueError):
        cro.Account()

    with pytest.raises(ValueError):
        cro.Account(api_key='123')

    with pytest.raises(ValueError):
        cro.Account(api_secret='3333')

    with pytest.raises(ValueError):
        cro.ApiProvider(api_key='123')

    with pytest.raises(ValueError):
        cro.ApiProvider(api_secret='123')

    monkeypatch.setattr(os, 'environ', {})

    with pytest.raises(ValueError):
        cro.Account(from_env=True)

    with pytest.raises(ValueError):
        cro.ApiProvider(from_env=True)

    monkeypatch.setattr(os, 'environ', {'CRYPTOCOM_API_KEY': '123'})

    with pytest.raises(ValueError):
        cro.Account(from_env=True)

    with pytest.raises(ValueError):
        cro.ApiProvider(from_env=True)


@pytest.mark.asyncio
async def test_wrong_api_response():
    api = cro.ApiProvider(from_env=True)

    with pytest.raises(cro.ApiError):
        await api.get('somepath')

    api = cro.ApiProvider(auth_required=False)
    with pytest.raises(cro.ApiError):
        await api.post('account')


@pytest.mark.asyncio
async def test_get_symbols(exchange: cro.Exchange):
    data = await exchange.get_symbols()
    symbols = [d['symbol'] for d in data]
    assert sorted(symbols) == sorted(s.value for s in cro.Symbol)


@pytest.mark.asyncio
async def test_get_tickers(exchange: cro.Exchange):
    tickers = await exchange.get_tickers()
    assert sorted(tickers) == sorted(s.value for s in cro.Symbol)
    keys = sorted(['amount', 'close', 'high', 'open', 'low', 'rose', 'vol'])
    for data in tickers.values():
        assert keys == sorted(data)
    ticker = await exchange.get_ticker(cro.Symbol.BTCUSDT)
    assert keys == sorted(ticker)


@pytest.mark.asyncio
async def test_get_candles(exchange: cro.Exchange):
    candles = [candle async for candle in exchange.get_candles(
        cro.Symbol.CROUSDT, cro.Period.D1)]
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
    tickers = await exchange.get_prices()
    assert sorted(tickers) == sorted(s.value for s in cro.Symbol)


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
    async for candle in exchange.listen_candles(
            cro.Symbol.CROUSDT, cro.Period.MIN1):
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


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    data = await account.get_balance()
    assert float(data['total_asset']) > 0
    assert data['coin_list']


@pytest.mark.asyncio
async def test_account_buy_limit(
        exchange: cro.Exchange, account: cro.Account):
    buy_price = round(await exchange.get_price(cro.Symbol.CROUSDT) / 2, 4)

    order_ids = [
        await account.buy_limit(cro.Symbol.CROUSDT, 1, buy_price)
        for i in range(3)
    ]
    open_orders = await account.get_open_orders(cro.Symbol.CROUSDT)

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    await account.cancel_order(
        order_ids[0], cro.Symbol.CROUSDT, wait_for_cancel=False)
    order = await account.get_order(order_ids[0], cro.Symbol.CROUSDT)
    assert order['status'] in (
        cro.OrderStatus.CANCELED, cro.OrderStatus.PENDING_CANCEL)

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.Symbol.CROUSDT)

    open_orders = await account.get_open_orders(cro.Symbol.CROUSDT)
    assert not open_orders

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    assert all_orders[0]['id'] == order_ids[-1]


@pytest.mark.asyncio
async def test_account_sell_limit(
        exchange: cro.Exchange, account: cro.Account):
    sell_price = round(await exchange.get_price(cro.Symbol.CROUSDT) * 2, 4)
    order_ids = [
        await account.sell_limit(cro.Symbol.CROUSDT, 1, sell_price)
        for _ in range(3)
    ]

    open_orders = await account.get_open_orders(cro.Symbol.CROUSDT)

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    await account.cancel_open_orders(cro.Symbol.CROUSDT)

    open_orders = await account.get_open_orders(cro.Symbol.CROUSDT)
    while open_orders:
        for order in open_orders:
            assert order['status'] == cro.OrderStatus.PENDING_CANCEL
        open_orders = await account.get_open_orders(cro.Symbol.CROUSDT)

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    assert all_orders[0]['id'] == order_ids[-1]


async def make_trades(account, order_ids, sem):
    async with sem:
        # buy volume for 0.0001 cro
        order_id = await account.buy_market(cro.Symbol.CROUSDT, 0.0001)
        order = await account.get_order(order_id, cro.Symbol.CROUSDT)
        assert order['status'] == cro.OrderStatus.FILLED
        order_ids['buy'].append(order_id)

        # sell volume for 0.002 usdt
        order_id = await account.sell_market(cro.Symbol.CROUSDT, 0.002)
        order = await account.get_order(order_id, cro.Symbol.CROUSDT)
        assert order['status'] == cro.OrderStatus.FILLED
        order_ids['sell'].append(order_id)


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account):
    order_ids = {'buy': [], 'sell': []}
    sem = asyncio.Semaphore(10)
    await asyncio.gather(*[
        make_trades(account, order_ids, sem) for _ in range(20)
    ])

    trades = await account.get_trades(cro.Symbol.CROUSDT, page_size=40)
    for trade in trades:
        if trade['side'] == cro.OrderSide.BUY:
            assert trade['id'] in order_ids['buy']
            assert trade['id'] not in order_ids['sell']
        elif trade['side'] == cro.OrderSide.SELL:
            assert trade['id'] in order_ids['sell']
            assert trade['id'] not in order_ids['buy']
