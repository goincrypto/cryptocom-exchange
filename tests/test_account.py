import asyncio

import pytest

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    data = await account.get_balance()
    assert data['CRO']['available']
    assert data['USDT']['available']


@pytest.mark.asyncio
async def test_no_dublicated_mass_limit_orders(
        exchange: cro.Exchange, account: cro.Account):
    buy_price = round(await exchange.get_price(cro.Pair.CROUSDT) / 2, 4)
    order_ids = await asyncio.gather(*[
        account.buy_limit(
            cro.Pair.CROUSDT, 0.01,
            round(buy_price / 2 + i / 10000.0, 4)
        )
        for i in range(150)
    ])

    orders = await account.get_open_orders(cro.Pair.CROUSDT)
    assert sorted(o['id'] for o in orders) == sorted(order_ids)


@pytest.mark.asyncio
async def test_account_buy_limit(exchange: cro.Exchange, account: cro.Account):
    buy_price = round(await exchange.get_price(cro.Pair.CROUSDT) / 2, 4)
    order_ids = await asyncio.gather(*[
        account.buy_limit(cro.Pair.CROUSDT, 0.01, buy_price)
        for i in range(10)
    ])
    all_orders = await account.get_orders(cro.Pair.CROUSDT, page_size=10)

    await account.cancel_order(
        order_ids[0], cro.Pair.CROUSDT, wait_for_cancel=True)
    order = await account.get_order(order_ids[0])
    assert order['status'] == cro.OrderStatus.CANCELED.value

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.Pair.CROUSDT)

    open_orders = [
        order
        for order in await account.get_open_orders(cro.Pair.CROUSDT)
        if order['id'] in order_ids
    ]
    assert not open_orders

    all_orders = await account.get_orders(cro.Pair.CROUSDT, page_size=10)
    ids = [order['id'] for order in all_orders]
    assert set(ids) & set(order_ids)


@pytest.mark.asyncio
async def test_account_sell_limit(
        exchange: cro.Exchange, account: cro.Account):
    sell_price = round(await exchange.get_price(cro.Pair.CROUSDT) * 2, 4)
    order_ids = [
        await account.sell_limit(cro.Pair.CROUSDT, 1, sell_price)
        for _ in range(3)
    ]

    all_orders = await account.get_orders(cro.Pair.CROUSDT, page_size=10)
    await account.cancel_open_orders(cro.Pair.CROUSDT)

    open_orders = [
        order
        for order in await account.get_open_orders(cro.Pair.CROUSDT)
        if order['id'] in order_ids
    ]

    for _ in range(10):
        for order in open_orders:
            assert order['status'] == cro.OrderStatus.CANCELED.value

        open_orders = [
            order
            for order in await account.get_open_orders(cro.Pair.CROUSDT)
            if order['id'] in order_ids
        ]

        if not open_orders:
            break

    assert not open_orders

    all_orders = await account.get_orders(cro.Pair.CROUSDT, page_size=10)
    ids = [order['id'] for order in all_orders]
    assert set(ids) & set(order_ids)


async def make_trades(account, order_ids):
    order_id = await account.buy_market(cro.Pair.CROUSDT, 0.001)
    order = await account.get_order(order_id)
    assert order['status'] == cro.OrderStatus.FILLED.value
    assert order['id']
    order_ids['buy'].append(order_id)

    order_id = await account.sell_market(cro.Pair.CROUSDT, 0.001)
    order = await account.get_order(order_id)
    assert order['status'] == cro.OrderStatus.FILLED.value
    order_ids['sell'].append(order_id)


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account):
    order_ids = {'buy': [], 'sell': []}
    await asyncio.gather(*[
        make_trades(account, order_ids) for _ in range(15)
    ])

    trades = await account.get_trades(cro.Pair.CROUSDT, page_size=40)
    for trade in trades:
        if trade['side'] == cro.OrderSide.BUY:
            assert trade['id'] in order_ids['buy']
            assert trade['id'] not in order_ids['sell']
        elif trade['side'] == cro.OrderSide.SELL:
            assert trade['id'] in order_ids['sell']
            assert trade['id'] not in order_ids['buy']
