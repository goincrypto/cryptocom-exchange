import asyncio
import time

import async_timeout
import pytest

import cryptocom.exchange as cro


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    balance = await account.get_balance()

    async with async_timeout.timeout(120):
        while (
            cro.instruments.CRO not in balance
            or balance[cro.instruments.CRO].available < 30
        ):
            await account.buy_market(cro.pairs.CRO_USD, 0.1)
            balance = await account.get_balance()
        while (
            cro.instruments.USD not in balance
            or balance[cro.instruments.USD].available < 2
        ):
            await account.sell_market(cro.pairs.CRO_USD, 1)
            balance = await account.get_balance()

    balance = await account.get_balance()
    local_instruments = cro.instruments.all()
    assert balance[cro.instruments.CRO].available > 30
    assert balance[cro.instruments.USD].available > 2
    for instrument in balance:
        if instrument.exchange_name not in ("MCO", "CRPT"):
            assert instrument in local_instruments


@pytest.mark.asyncio
async def test_missing_old_pairs(account: cro.Account):
    missing_pair = account.pairs["LINK_CRO"]
    assert missing_pair.price_precision == 8
    assert missing_pair.quantity_precision == 8


@pytest.mark.asyncio
@pytest.mark.skip
async def test_deposit_withdrawal_history(account: cro.Account, exchange: cro.Exchange):
    # TODO: fix withdrawal history
    transactions = await account.get_withdrawal_history(cro.instruments.CRO)
    assert transactions
    assert transactions[0].status == cro.WithdrawalStatus.COMPLETED

    transactions = await account.get_deposit_history()
    assert transactions
    assert transactions[0].status == cro.DepositStatus.ARRIVED

    transactions = await account.get_deposit_history(
        cro.instruments.CRO, status=cro.DepositStatus.NOT_ARRIVED
    )
    assert not transactions

    transactions = await account.get_withdrawal_history(
        cro.instruments.CRO, status=cro.WithdrawalStatus.CANCELLED
    )
    assert not transactions

    transactions = await account.get_deposit_history(
        cro.instruments.USD,
        start_ts=time.time() - cro.Timeframe.DAYS * 5,
        end_ts=cro.Timeframe.resolve(cro.Timeframe.NOW),
    )
    assert not transactions


@pytest.mark.asyncio
async def test_no_duplicate_mass_limit_orders(
    account: cro.Account,
    exchange: cro.Exchange,
):
    buy_price = round(await exchange.get_price(cro.pairs.CRO_USD) / 2, 4)
    orders_count = 20
    order_ids = await asyncio.gather(
        *[
            account.buy_limit(cro.pairs.CRO_USD, 1, round(buy_price + i * 0.0001, 4))
            for i in range(orders_count)
        ]
    )

    real_orders = await asyncio.gather(*[account.get_order(id_) for id_ in order_ids])
    for order in real_orders:
        assert order.is_active, order

    open_orders = await account.get_open_orders(cro.pairs.CRO_USD)
    open_order_ids = sorted(o.id for o in open_orders if o.is_active)

    assert len(real_orders) == len(open_order_ids) == orders_count
    assert open_order_ids == sorted(order_ids)


@pytest.mark.asyncio
async def test_account_limit_orders(account: cro.Account, exchange: cro.Exchange):
    buy_price = round(await exchange.get_price(cro.pairs.CRO_USD) / 2, 4)
    order_ids = await asyncio.gather(
        *[account.buy_limit(cro.pairs.CRO_USD, 1, buy_price) for _ in range(10)]
    )
    order_ids += await asyncio.gather(
        *[
            account.sell_limit(cro.pairs.CRO_USD, 1, round(buy_price * 4, 4))
            for _ in range(10)
        ]
    )

    await account.cancel_order(order_ids[0], cro.pairs.CRO_USD, check_status=True)
    order = await account.get_order(order_ids[0])
    assert order.is_canceled

    for order_id in order_ids[1:]:
        await account.cancel_order(order_id, cro.pairs.CRO_USD)

    open_orders = [
        order for order in await account.get_open_orders() if order.id in order_ids
    ]
    assert not open_orders

    all_orders = await account.get_orders_history(cro.pairs.CRO_USD, limit=50)
    ids = [order.id for order in all_orders]
    assert set(ids) & set(order_ids)


async def make_trades(account, exchange, order_ids):
    price = await exchange.get_price(cro.pairs.CRO_USD)
    order_id = await account.buy_market(cro.pairs.CRO_USD, price * 1.1)
    order_ids["buy"].append(order_id)

    order_id = await account.sell_market(cro.pairs.CRO_USD, 1)
    order_ids["sell"].append(order_id)


async def listen_orders(account: cro.Account, orders):
    async for order in account.listen_orders(cro.pairs.CRO_USD):
        orders.append(order)


async def listen_balances(account: cro.Account, balances):
    async for balance in account.listen_balances():
        balances.append(balance)


@pytest.mark.asyncio
async def test_account_listen_balances(account: cro.Account):
    index = 0
    async for balances in account.listen_balances():
        index += 1
        print("here index", index)
        if index > 3:
            print("break here please")
            break


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account, exchange: cro.Exchange):
    order_ids = {"buy": [], "sell": []}
    orders = []
    l_orders = []
    l_balances = []
    trades_count = 10
    task = asyncio.create_task(listen_orders(account, l_orders))
    task = asyncio.create_task(listen_balances(account, l_balances))
    while not l_balances:
        await asyncio.sleep(1)

    await asyncio.gather(
        *[make_trades(account, exchange, order_ids) for _ in range(trades_count)]
    )

    orders = await asyncio.gather(
        *[
            account.get_order(order_id)
            for order_id in order_ids["buy"] + order_ids["sell"]
        ]
    )

    final_orders = {}
    while not l_orders and len(final_orders) != l_orders:
        for o in l_orders:
            final_orders[o.id] = o
        await asyncio.sleep(1)

    for order in orders:
        assert order.is_filled, order

    assert l_orders
    assert l_balances
    assert set(o.id for o in l_orders) == set(o.id for o in orders)

    trades = await account.get_trades(cro.pairs.CRO_USD, limit=trades_count * 2)
    for trade in trades:
        if trade.is_buy:
            assert trade.order_id in order_ids["buy"]
            assert trade.order_id not in order_ids["sell"]
        elif trade.is_sell:
            assert trade.order_id in order_ids["sell"]
            assert trade.order_id not in order_ids["buy"]

    assert len(orders) == len(order_ids["buy"]) + len(order_ids["sell"])

    if not task.cancelled():
        task.cancel()


# @pytest.mark.asyncio
# async def test_account_get_accounts(account: cro.Account):
#     data = await account.get_accounts()
#     print(data)
#     import pprint

#     pprint.pprint(data)
#     pprint.pprint(await account.get_balance_history())
