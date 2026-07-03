import asyncio
import time

import async_timeout
import pytest

import cryptocom.exchange as cro
from cryptocom.exchange.structs import OrderStatus


def calculate_min_quantity(pair: cro.Pair, price: float) -> int:
    """Calculate minimum quantity to ensure $1.0+ notional."""
    return max(1, int(pair.min_order_notional_usd / price) + 1)


@pytest.mark.asyncio
async def test_account_get_balance(account: cro.Account):
    balance = await account.get_balance()
    price = await account.exchange.get_price(cro.pairs.CRO_USD)

    async with async_timeout.timeout(120):
        while (
            cro.instruments.CRO not in balance
            or balance[cro.instruments.CRO].available < 30
        ):
            # Calculate amount needed to reach 30 CRO, with minimum $1.0 notional
            cro_bal = balance.get(cro.instruments.CRO)
            cro_needed = 30 - cro_bal.available if cro_bal else 30
            usd_amount = max(1.0, cro_needed * price)
            await account.buy_market(cro.pairs.CRO_USD, usd_amount)
            balance = await account.get_balance()
        while (
            cro.instruments.USD not in balance
            or balance[cro.instruments.USD].available < 2
        ):
            # Calculate CRO to sell to get $2 USD, with minimum $1.0 notional
            usd_bal = balance.get(cro.instruments.USD)
            usd_needed = 2 - usd_bal.available if usd_bal else 2
            cro_to_sell = max(
                int(usd_needed / price + 1), 17
            )  # Ensure >= $1.0 notional
            await account.sell_market(cro.pairs.CRO_USD, cro_to_sell)
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
        start_ts=time.time() - cro.TimeDelta.DAYS * 5,
        end_ts=cro.TimeDelta.resolve(cro.TimeDelta.NOW),
    )
    assert not transactions


@pytest.mark.asyncio
async def test_no_duplicate_mass_limit_orders(
    account: cro.Account,
    exchange: cro.Exchange,
):
    current_price = await exchange.get_price(cro.pairs.CRO_USD)
    buy_price = round(current_price - 0.01, 4)  # Set below market to keep order open
    orders_count = 2
    # Calculate minimum quantity to ensure $1.0+ notional
    qty = calculate_min_quantity(cro.pairs.CRO_USD, buy_price)
    order_ids = await asyncio.gather(
        *[
            account.buy_limit(cro.pairs.CRO_USD, qty, round(buy_price - i * 0.0001, 4))
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
    current_price = await exchange.get_price(cro.pairs.CRO_USD)
    buy_price = round(current_price - 0.01, 4)  # Set below market to keep order open
    sell_price = round(current_price + 0.01, 4)  # Set above market to keep order open
    # Calculate minimum quantity to ensure $1.0+ notional
    qty = calculate_min_quantity(cro.pairs.CRO_USD, buy_price)

    # Check available CRO balance for sell orders
    balance = await account.get_balance()
    cro_bal = balance.get(cro.instruments.CRO)
    available_cro = cro_bal.available if cro_bal else 0

    # Adjust sell orders based on available balance (keep some CRO)
    # Use minimum quantity to ensure we don't exceed available balance
    sell_qty = qty  # Use minimum quantity that ensures $1.0+ notional

    # 3 buy orders + sell orders based on balance
    order_ids = await asyncio.gather(
        *[account.buy_limit(cro.pairs.CRO_USD, qty, buy_price) for _ in range(3)]
    )
    # Only create sell orders if we have enough balance (need at least sell_qty * 2)
    if available_cro >= sell_qty * 2:
        order_ids += await asyncio.gather(
            *[
                account.sell_limit(cro.pairs.CRO_USD, sell_qty, sell_price)
                for _ in range(2)
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
    balance = await account.get_balance()

    # Check available balances
    cro_bal = balance.get(cro.instruments.CRO)
    usd_bal = balance.get(cro.instruments.USD)
    available_cro = cro_bal.available if cro_bal else 0
    available_usd = usd_bal.available if usd_bal else 0

    # Calculate minimum quantity based on pair's min notional requirement
    # Add 50% safety margin to ensure we meet minimum notional even if price fluctuates
    min_qty = int((cro.pairs.CRO_USD.min_order_notional_usd / price) * 1.5) + 1

    # Use smaller quantities to avoid balance issues, but ensure minimum notional
    # Use 20% of available balance to leave room for other operations
    qty = max(min_qty, int(available_cro * 0.2))
    spend = max(
        cro.pairs.CRO_USD.min_order_notional_usd,
        min(available_usd * 0.2, qty * price * 1.1),
    )

    # Only create orders if we have sufficient balance
    if spend >= cro.pairs.CRO_USD.min_order_notional_usd and qty >= min_qty:
        order_id = await account.buy_market(cro.pairs.CRO_USD, spend)
        order_ids["buy"].append(order_id)

        order_id = await account.sell_market(cro.pairs.CRO_USD, qty)
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
        if index > 3:
            break


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account, exchange: cro.Exchange):
    order_ids = {"buy": [], "sell": []}
    orders = []
    l_orders = []
    l_balances = []
    task = asyncio.create_task(listen_orders(account, l_orders))
    task_bal = asyncio.create_task(listen_balances(account, l_balances))
    while not l_balances:
        await asyncio.sleep(1)

    # Only create one set of trades to avoid balance issues
    await make_trades(account, exchange, order_ids)

    # Skip test if no orders were created (insufficient balance)
    if not order_ids["buy"] or not order_ids["sell"]:
        task.cancel()
        task_bal.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await task_bal
        except asyncio.CancelledError:
            pass
        pytest.skip("Insufficient balance for market orders")

    orders = await asyncio.gather(
        *[
            account.get_order(order_id)
            for order_id in order_ids["buy"] + order_ids["sell"]
        ]
    )

    # Wait for listen orders to receive updates
    for _ in range(10):
        if l_orders:
            break
        await asyncio.sleep(1)

    # Check orders are filled or partially filled (MARKET BUY can have filled > quantity)
    for order in orders:
        assert order.status in (OrderStatus.FILLED, OrderStatus.CANCELED), order
        if order.status == OrderStatus.FILLED:
            assert order.remain_quantity <= 0, (
                f"Order should have no remain quantity: {order}"
            )

    assert l_orders
    assert l_balances
    assert set(o.id for o in l_orders) == set(o.id for o in orders)

    trades = await account.get_trades(
        cro.pairs.CRO_USD, limit=len(order_ids["buy"]) + len(order_ids["sell"])
    )
    for trade in trades:
        if trade.is_buy:
            assert trade.order_id in order_ids["buy"]
            assert trade.order_id not in order_ids["sell"]
        elif trade.is_sell:
            assert trade.order_id in order_ids["sell"]
            assert trade.order_id not in order_ids["buy"]

    assert len(orders) == len(order_ids["buy"]) + len(order_ids["sell"])

    # Properly cancel tasks
    task.cancel()
    task_bal.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    try:
        await task_bal
    except asyncio.CancelledError:
        pass

    if not task.cancelled():
        task.cancel()


# @pytest.mark.asyncio
# async def test_account_get_accounts(account: cro.Account):
#     data = await account.get_accounts()
#     print(data)
#     import pprint

#     pprint.pprint(data)
#     pprint.pprint(await account.get_balance_history())
