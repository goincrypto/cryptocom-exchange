import asyncio

import pytest

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    balances = await account.get_balance()
    assert balances[cro.Coin.CRO].available > 0.2
    assert balances[cro.Coin.USDT].available > 0.2
    for coin in cro.Coin:
        assert coin.value in balances


@pytest.mark.asyncio
async def test_no_dublicated_mass_limit_orders(
        exchange: cro.Exchange, account: cro.Account):
    buy_price = round(await exchange.get_price(cro.Pair.CRO_USDT) / 2, 4)
    orders_count = 185
    order_ids = await asyncio.gather(*[
        account.buy_limit(
            cro.Pair.CRO_USDT, 0.001,
            round(buy_price / 1000 + i / 10000.0, 4)
        )
        for i in range(orders_count)
    ])

    real_orders = await asyncio.gather(*[
        account.get_order(id_)
        for id_ in order_ids
    ])
    for order in real_orders:
        assert order.is_active, order

    open_orders = await account.get_open_orders(cro.Pair.CRO_USDT)
    open_order_ids = sorted(o.id for o in open_orders if o.is_active)
    assert len(real_orders) == len(open_order_ids) == orders_count
    assert open_order_ids == sorted(order_ids)


@pytest.mark.asyncio
async def test_account_limit_orders(
        account: cro.Account, exchange: cro.Exchange):
    buy_price = round(await exchange.get_price(cro.Pair.CRO_USDT) / 10, 4)
    order_ids = await asyncio.gather(*[
        account.buy_limit(cro.Pair.CRO_USDT, 0.001, buy_price)
        for i in range(25)
    ])
    order_ids += await asyncio.gather(*[
        account.sell_limit(cro.Pair.CRO_USDT, 0.01, round(buy_price * 2, 4))
        for i in range(25)
    ])
    all_orders = await account.get_orders_history(
        cro.Pair.CRO_USDT, page_size=50)

    await account.cancel_order(
        order_ids[0], cro.Pair.CRO_USDT, check_status=True)
    order = await account.get_order(order_ids[0])
    assert order.is_canceled

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.Pair.CRO_USDT)

    open_orders = [
        order
        for order in await account.get_open_orders()
        if order.id in order_ids
    ]
    assert not open_orders

    all_orders = await account.get_orders_history(
        cro.Pair.CRO_USDT, page_size=50)
    ids = [order.id for order in all_orders]
    assert set(ids) & set(order_ids)


async def make_trades(account, exchange, order_ids):
    price = await exchange.get_price(cro.Pair.CRO_USDT)
    order_id = await account.buy_market(cro.Pair.CRO_USDT, round(price, 4))
    order = await account.get_order(order_id)
    assert order.is_filled
    assert order_id == order.id
    order_ids['buy'].append(order.id)

    order_id = await account.sell_market(cro.Pair.CRO_USDT, 1)
    order = await account.get_order(order_id)
    assert order.is_filled
    assert order_id == order.id
    order_ids['sell'].append(order.id)


@pytest.mark.asyncio
async def test_account_market_orders(
        account: cro.Account, exchange: cro.Exchange):
    order_ids = {'buy': [], 'sell': []}
    await asyncio.gather(*[
        make_trades(account, exchange, order_ids) for _ in range(10)
    ])

    trades = await account.get_trades(cro.Pair.CRO_USDT, page_size=20)
    for trade in trades:
        if trade.is_buy:
            assert trade.order_id in order_ids['buy']
            assert trade.order_id not in order_ids['sell']
        elif trade.is_sell:
            assert trade.order_id in order_ids['sell']
            assert trade.order_id not in order_ids['buy']
