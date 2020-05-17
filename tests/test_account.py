import asyncio

import pytest

import cryptocom.exchange as cro


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

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)

    await account.cancel_order(
        order_ids[0], cro.Symbol.CROUSDT, wait_for_cancel=False)
    order = await account.get_order(order_ids[0], cro.Symbol.CROUSDT)
    assert order['status'] in (
        cro.OrderStatus.CANCELED, cro.OrderStatus.PENDING_CANCEL)

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.Symbol.CROUSDT)

    open_orders = [
        order
        for order in await account.get_open_orders(cro.Symbol.CROUSDT)
        if order['id'] in order_ids
    ]
    assert not open_orders

    # NOTE: note always orders populated fast after open orders so
    # here we check on other direction
    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    ids = [order['id'] for order in all_orders]
    assert set(ids) & set(order_ids)


@pytest.mark.asyncio
async def test_account_sell_limit(
        exchange: cro.Exchange, account: cro.Account):
    sell_price = round(await exchange.get_price(cro.Symbol.CROUSDT) * 2, 4)
    order_ids = [
        await account.sell_limit(cro.Symbol.CROUSDT, 1, sell_price)
        for _ in range(3)
    ]

    open_orders = [
        order
        for order in await account.get_open_orders(cro.Symbol.CROUSDT)
        if order['id'] in order_ids
    ]

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    await account.cancel_open_orders(cro.Symbol.CROUSDT)

    for _ in range(10):
        for order in open_orders:
            assert order['status'] in (
                cro.OrderStatus.PENDING_CANCEL,
                cro.OrderStatus.CANCELED,
                cro.OrderStatus.NEW
            )

        open_orders = [
            order
            for order in await account.get_open_orders(cro.Symbol.CROUSDT)
            if order['id'] in order_ids
        ]

        if not open_orders:
            break

    assert not open_orders

    all_orders = await account.get_orders(cro.Symbol.CROUSDT, page_size=10)
    ids = [order['id'] for order in all_orders]
    assert set(ids) & set(order_ids)


async def make_trades(account, order_ids):
    # buy volume for 0.0001 cro
    order_id = await account.buy_market(cro.Symbol.CROUSDT, 0.001)
    order = await account.get_order(order_id, cro.Symbol.CROUSDT)
    assert order['status'] == cro.OrderStatus.FILLED
    order_ids['buy'].append(order_id)

    # sell volume for 0.002 usdt
    order_id = await account.sell_market(cro.Symbol.CROUSDT, 0.02)
    order = await account.get_order(order_id, cro.Symbol.CROUSDT)
    assert order['status'] == cro.OrderStatus.FILLED
    order_ids['sell'].append(order_id)


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account):
    order_ids = {'buy': [], 'sell': []}
    await asyncio.gather(*[
        make_trades(account, order_ids) for _ in range(15)
    ])

    trades = await account.get_trades(cro.Symbol.CROUSDT, page_size=40)
    for trade in trades:
        if trade['side'] == cro.OrderSide.BUY:
            assert trade['id'] in order_ids['buy']
            assert trade['id'] not in order_ids['sell']
        elif trade['side'] == cro.OrderSide.SELL:
            assert trade['id'] in order_ids['sell']
            assert trade['id'] not in order_ids['buy']
