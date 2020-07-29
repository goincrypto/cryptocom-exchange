import asyncio

import pytest

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    data = await account.get_balance()
    assert data['CRO']['available'] > 2
    assert data['USDT']['available'] > 2


@pytest.mark.asyncio
async def test_no_dublicated_mass_limit_orders(
        exchange: cro.Exchange, account: cro.Account):
    buy_price = round(await exchange.get_price(cro.Pair.CRO_USDT) / 2, 4)
    order_ids = await asyncio.gather(*[
        account.buy_limit(
            cro.Pair.CRO_USDT, 0.001,
            round(buy_price / 1000 + i / 10000.0, 4)
        )
        for i in range(100)
    ])

    real_orders = await asyncio.gather(*[
        account.get_order(id_)
        for id_ in order_ids
    ])
    for order in real_orders:
        assert order['status'] == 'ACTIVE', order

    assert len(real_orders) == 100

    orders = await account.get_open_orders(cro.Pair.CRO_USDT)
    assert sorted(o['id'] for o in orders) == sorted(order_ids)


@pytest.mark.asyncio
async def test_account_buy_limit(exchange: cro.Exchange, account: cro.Account):
    buy_price = round(await exchange.get_price(cro.Pair.CRO_USDT) / 10, 4)
    order_ids = await asyncio.gather(*[
        account.buy_limit(cro.Pair.CRO_USDT, 0.001, buy_price)
        for i in range(25)
    ])
    all_orders = await account.get_orders(cro.Pair.CRO_USDT, page_size=50)

    await account.cancel_order(
        order_ids[0], cro.Pair.CRO_USDT, wait_for_cancel=True)
    order = await account.get_order(order_ids[0])
    assert order['status'] == cro.OrderStatus.CANCELED.value

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.Pair.CRO_USDT)

    open_orders = [
        order
        for order in await account.get_open_orders(cro.Pair.CRO_USDT)
        if order['id'] in order_ids
    ]
    assert not open_orders

    all_orders = await account.get_orders(cro.Pair.CRO_USDT, page_size=50)
    ids = [order['id'] for order in all_orders]
    assert set(ids) & set(order_ids)


@pytest.mark.asyncio
async def test_account_sell_limit(
        exchange: cro.Exchange, account: cro.Account):
    sell_price = round(await exchange.get_price(cro.Pair.CRO_USDT) * 10, 4)
    order_ids = [
        await account.sell_limit(cro.Pair.CRO_USDT, 0.001, sell_price)
        for _ in range(25)
    ]

    all_orders = await account.get_orders(cro.Pair.CRO_USDT, page_size=50)
    await account.cancel_open_orders(cro.Pair.CRO_USDT)

    open_orders = [
        order
        for order in await account.get_open_orders(cro.Pair.CRO_USDT)
        if order['id'] in order_ids
    ]

    for _ in range(10):
        for order in open_orders:
            assert order['status'] == cro.OrderStatus.CANCELED.value

        open_orders = [
            order
            for order in await account.get_open_orders(cro.Pair.CRO_USDT)
            if order['id'] in order_ids
        ]

        if not open_orders:
            break

    assert not open_orders

    all_orders = await account.get_orders(cro.Pair.CRO_USDT, page_size=50)
    ids = [order['id'] for order in all_orders]
    assert set(ids) & set(order_ids)


async def make_trades(account, order_ids):
    order_id = await account.buy_market(cro.Pair.CRO_USDT, 0.0001)
    order = await account.get_order(order_id)
    assert order['status'] == cro.OrderStatus.FILLED.value
    assert order['id']
    order_ids['buy'].append(order_id)

    order_id = await account.sell_market(cro.Pair.CRO_USDT, 0.0001)
    order = await account.get_order(order_id)
    assert order['status'] == cro.OrderStatus.FILLED.value
    order_ids['sell'].append(order_id)


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account):
    order_ids = {'buy': [], 'sell': []}
    await asyncio.gather(*[
        make_trades(account, order_ids) for _ in range(10)
    ])

    trades = await account.get_trades(cro.Pair.CRO_USDT, page_size=40)
    keys = sorted([
        'side', 'instrument_name', 'fee', 'id', 'create_time', 'traded_price',
        'traded_quantity', 'fee_currency', 'order_id'
    ])
    assert trades
    assert keys == sorted(trades[0].keys())

    for trade in trades:
        if trade['side'] == cro.OrderSide.BUY:
            assert trade['order_id'] in order_ids['buy']
            assert trade['order_id'] not in order_ids['sell']
        elif trade['side'] == cro.OrderSide.SELL:
            assert trade['order_id'] in order_ids['sell']
            assert trade['order_id'] not in order_ids['buy']
