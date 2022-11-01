import asyncio
import time

import async_timeout
import pytest

import cryptocom.exchange as cro
from cryptocom.exchange.helpers import round_up
from cryptocom.exchange.structs import (
    DepositStatus,
    Timeframe,
    WithdrawalStatus,
)


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    balances = await account.get_balance()

    async with async_timeout.timeout(120):
        while balances[cro.coins.CRO].available < 10:
            await account.buy_market(cro.pairs.CRO_USDT, 1)
            balances = await account.get_balance()
        while balances[cro.coins.USDT].available < 10:
            await account.sell_market(cro.pairs.CRO_USDT, 10)
            balances = await account.get_balance()

    balances = await account.get_balance()
    local_coins = cro.coins.all()
    assert balances[cro.coins.CRO].available > 1
    assert balances[cro.coins.USDT].available > 1
    for coin in balances:
        assert coin in local_coins


@pytest.mark.asyncio
async def test_missing_old_pairs(account: cro.Account):
    missing_pair = account.pairs["LINK_CRO"]
    assert missing_pair.price_precision == 8
    assert missing_pair.quantity_precision == 8


@pytest.mark.asyncio
async def test_deposit_withdrawal_history(
    account: cro.Account, exchange: cro.Exchange
):
    transactions = await account.get_withdrawal_history(cro.coins.CRO)
    assert transactions
    assert transactions[0].status == cro.WithdrawalStatus.COMPLETED

    transactions = await account.get_deposit_history(cro.coins.CRO)
    assert transactions
    assert transactions[0].status == cro.DepositStatus.ARRIVED

    transactions = await account.get_deposit_history(
        cro.coins.CRO, status=DepositStatus.NOT_ARRIVED
    )
    assert not transactions

    transactions = await account.get_withdrawal_history(
        cro.coins.CRO, status=WithdrawalStatus.CANCELLED
    )
    assert not transactions

    transactions = await account.get_deposit_history(
        cro.coins.CRO,
        start_ts=time.time() - Timeframe.DAYS * 5,
        end_ts=Timeframe.resolve(Timeframe.NOW),
    )
    assert not transactions


@pytest.mark.asyncio
async def test_no_duplicate_mass_limit_orders(
    account: cro.Account,
    exchange: cro.Exchange,
):
    buy_price = round(await exchange.get_price(cro.pairs.CRO_USDT) / 2, 4)
    orders_count = 20
    order_ids = await asyncio.gather(
        *[
            account.buy_limit(
                cro.pairs.CRO_USDT, 1, round(buy_price + i * 0.0001, 4)
            )
            for i in range(orders_count)
        ]
    )

    real_orders = await asyncio.gather(
        *[account.get_order(id_) for id_ in order_ids]
    )
    for order in real_orders:
        assert order.is_active, order

    await asyncio.sleep(2)

    open_orders = await account.get_open_orders(cro.pairs.CRO_USDT)
    open_order_ids = sorted(o.id for o in open_orders if o.is_active)

    assert len(real_orders) == len(open_order_ids) == orders_count
    assert open_order_ids == sorted(order_ids)


@pytest.mark.asyncio
async def test_account_limit_orders(
    account: cro.Account, exchange: cro.Exchange
):
    buy_price = round(await exchange.get_price(cro.pairs.CRO_USDT) / 2, 4)
    order_ids = await asyncio.gather(
        *[
            account.buy_limit(cro.pairs.CRO_USDT, 1, buy_price)
            for _ in range(10)
        ]
    )
    order_ids += await asyncio.gather(
        *[
            account.sell_limit(cro.pairs.CRO_USDT, 1, round(buy_price * 4, 4))
            for _ in range(10)
        ]
    )

    await account.cancel_order(
        order_ids[0], cro.pairs.CRO_USDT, check_status=True
    )
    order = await account.get_order(order_ids[0])
    assert order.is_canceled

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.pairs.CRO_USDT)

    open_orders = [
        order
        for order in await account.get_open_orders()
        if order.id in order_ids
    ]
    assert not open_orders

    all_orders = await account.get_orders_history(
        cro.pairs.CRO_USDT, page_size=50
    )
    ids = [order.id for order in all_orders]
    assert set(ids) & set(order_ids)


async def make_trades(account, exchange, order_ids):
    price = await exchange.get_price(cro.pairs.CRO_USDT)
    order_id = await account.buy_market(cro.pairs.CRO_USDT, 1)
    order = await account.get_order(order_id)
    assert order_id == order.id, (order_id, order.id)
    assert order.is_filled, (order_id, order.id, order)
    order_ids["buy"].append(order.id)

    order_id = await account.sell_market(
        cro.pairs.CRO_USDT, int(round_up(1 / price, 0))
    )
    order = await account.get_order(order_id)
    assert order.is_filled
    assert order_id == order.id
    order_ids["sell"].append(order.id)


async def listen_orders(account: cro.Account, orders):
    async for order in account.listen_orders(cro.pairs.CRO_USDT):
        orders.append(order)


async def listen_balances(account: cro.Account, balances):
    async for balance in account.listen_balances():
        balances.append(balance)


@pytest.mark.asyncio
async def test_account_market_orders(
    account: cro.Account, exchange: cro.Exchange
):
    order_ids = {"buy": [], "sell": []}
    orders = []
    l_orders = []
    l_balances = []
    trades_count = 10
    task = asyncio.create_task(listen_orders(account, l_orders))
    task = asyncio.create_task(listen_balances(account, l_balances))
    await asyncio.sleep(20)

    await asyncio.gather(
        *[
            make_trades(account, exchange, order_ids)
            for _ in range(trades_count)
        ]
    )

    orders = await asyncio.gather(
        *[
            account.get_order(order_id)
            for order_id in order_ids["buy"] + order_ids["sell"]
        ]
    )
    await asyncio.sleep(10)

    for order in orders:
        assert order.trades, order

    assert l_orders
    assert l_balances
    assert set(o.id for o in l_orders) == set(o.id for o in orders)

    trades = await account.get_trades(
        cro.pairs.CRO_USDT, page_size=trades_count * 2
    )
    for trade in trades:
        if trade.is_buy:
            assert trade.order_id in order_ids["buy"]
            assert trade.order_id not in order_ids["sell"]
        elif trade.is_sell:
            assert trade.order_id in order_ids["sell"]
            assert trade.order_id not in order_ids["buy"]

    await asyncio.sleep(20)

    assert len(orders) >= len(order_ids["buy"]) + len(order_ids["sell"])

    if not task.cancelled():
        task.cancel()
    await asyncio.sleep(1)
