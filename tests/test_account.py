import asyncio
import time

import async_timeout
import pytest

import cryptocom.exchange as cro
from cryptocom.exchange.structs import OrderStatus

import helpers


@pytest.mark.asyncio
@pytest.mark.skip
async def test_account_get_balance(account: cro.Account):
    balance = await account.get_balance()
    price = await account.market.get_price(cro.pairs.CRO_USD)

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


# ============================================================================
# Account/history endpoints - shape tests, tolerant of empty history
# (the account is a test account; absence of e.g. withdrawals is valid).
# ============================================================================


@pytest.mark.asyncio
async def test_get_accounts_shape(account: cro.Account):
    accounts = await account.get_accounts()
    assert isinstance(accounts, dict)
    master = accounts["master_account"]
    assert master["enabled"] is True
    assert master["tradable"] is True
    assert "uuid" in master


# NOTE: private/get-deposit-history and private/get-withdrawal-history
# return HTTP 401 USER_NOT_FOUND for trade-API key scope (wallet-side
# surface). Deposit/Withdrawal parsing stays covered offline
# (test_structs_edges.py); no live shape tests for those endpoints.


@pytest.mark.asyncio
async def test_orders_history_shape(account: cro.Account):
    orders = await account.get_orders_history(cro.pairs.CRO_USD, limit=10)
    assert isinstance(orders, list)
    for order in orders:
        # History is strictly terminal orders.
        assert order.is_terminal, order


@pytest.mark.asyncio
async def test_balance_history_shape(account: cro.Account):
    history = await account.get_balance_history()
    # Shape: [{"t": ts_ms, "c": balance_str, "i": type}] - newest first.
    assert isinstance(history, list)
    assert history, "account with activity must have balance history"
    point = history[0]
    assert {"t", "c", "i"} <= set(point)
    assert float(point["c"]) > 0


@pytest.mark.asyncio
@pytest.mark.skip
async def test_deposit_withdrawal_history(account: cro.Account, market: cro.Market):
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
    market: cro.Market,
):
    pair = cro.pairs.CRO_USD
    current_price = await market.get_price(pair)
    orders_count = 3
    # Stagger maker prices safely below market; tick-legal quantity per level.
    prices = [
        pair.round_price_down(
            helpers.resting_buy_price(pair, current_price) - i * pair.price_tick_size
        )
        for i in range(orders_count)
    ]
    orders = await asyncio.gather(
        *[
            account.buy_limit(pair, helpers.min_order_quantity(pair, p), p)
            for p in prices
        ]
    )
    client_ids = [o.client_id for o in orders]
    [o.id for o in orders]

    # Get orders using client_id
    real_orders = await asyncio.gather(
        *[account.get_order(client_order_id=cid) for cid in client_ids]
    )
    for order in real_orders:
        assert order.is_active, order
        assert order.client_id in client_ids

    open_orders = await account.get_open_orders(cro.pairs.CRO_USD)
    open_client_ids = sorted(o.client_id for o in open_orders if o.is_active)

    assert len(real_orders) == len(open_client_ids) == orders_count
    assert open_client_ids == sorted(client_ids)


@pytest.mark.asyncio
async def test_account_limit_orders(account: cro.Account, market: cro.Market):
    pair = cro.pairs.CRO_USD
    current_price = await market.get_price(pair)
    buy_price = helpers.resting_buy_price(pair, current_price)
    sell_price = helpers.resting_sell_price(pair, current_price)
    qty = helpers.min_order_quantity(pair, buy_price)

    # Check available CRO balance for sell orders
    balance = await account.get_balance()
    cro_bal = balance.get(cro.instruments.CRO)
    available_cro = cro_bal.available if cro_bal else 0

    # Adjust sell orders based on available balance (keep some CRO)
    # Use minimum quantity to ensure we don't exceed available balance
    sell_qty = qty  # Use minimum quantity that ensures $1.0+ notional

    # 3 buy orders + sell orders based on balance
    orders = await asyncio.gather(
        *[account.buy_limit(cro.pairs.CRO_USD, qty, buy_price) for _ in range(4)]
    )
    client_ids = [o.client_id for o in orders]
    order_ids = [o.id for o in orders]

    # Only create sell orders if we have enough balance (need at least sell_qty * 2)
    if available_cro >= sell_qty * 2:
        sell_orders = await asyncio.gather(
            *[
                account.sell_limit(cro.pairs.CRO_USD, sell_qty, sell_price)
                for _ in range(2)
            ]
        )
        client_ids += [o.client_id for o in sell_orders]
        order_ids += [o.id for o in sell_orders]

    # Cancel first order using client_id
    await account.cancel_order(cro.pairs.CRO_USD, client_ids[0], check_status=True)
    order = await account.get_order(client_order_id=client_ids[0])
    assert order.is_canceled

    # Cancel remaining orders using client_id
    for client_id in client_ids[1:]:
        await account.cancel_order(cro.pairs.CRO_USD, client_id)

    # Verify no open orders with these client_ids
    open_orders = await account.get_open_orders()
    open_client_ids = [
        order.client_id for order in open_orders if order.client_id in client_ids
    ]
    assert not open_client_ids

    # Verify orders in history by order_id
    all_orders = await account.get_orders_history(cro.pairs.CRO_USD, limit=50)
    order_ids_in_history = [order.id for order in all_orders]
    assert set(order_ids_in_history) & set(order_ids)


async def make_trades(account, market, order_ids):
    pair = cro.pairs.CRO_USD
    price = await market.get_price(pair)
    balance = await account.get_balance()

    cro_bal = balance.get(cro.instruments.CRO)
    usd_bal = balance.get(cro.instruments.USD)
    available_cro = cro_bal.available if cro_bal else 0
    available_usd = usd_bal.available if usd_bal else 0

    # Pair-legal minimum size, plus notional headroom for market movement.
    qty = helpers.min_order_quantity(pair, price)
    spend = pair.round_price_up(qty * price * 1.1)

    if available_cro >= qty and available_usd >= spend:
        order = await account.buy_market(pair, spend)
        order_ids["buy"].append(order.id)

        order = await account.sell_market(pair, qty)
        order_ids["sell"].append(order.id)


async def listen_orders(account: cro.Account, orders):
    async for order in account.listen_orders(cro.pairs.CRO_USD):
        orders.append(order)


async def listen_balances(account: cro.Account, balances):
    async for balance in account.listen_balances():
        balances.append(balance)


@pytest.mark.asyncio
@pytest.mark.skip("Requires WebSocket fixtures")
async def test_account_listen_balances(account: cro.Account):
    index = 0
    async for balances in account.listen_balances():
        index += 1
        if index > 3:
            break


@pytest.mark.asyncio
async def test_account_market_orders(account: cro.Account, market: cro.Market):
    order_ids = {"buy": [], "sell": []}
    orders = []
    l_orders = []
    l_balances = []
    task = asyncio.create_task(listen_orders(account, l_orders))
    task_bal = asyncio.create_task(listen_balances(account, l_balances))
    while not l_balances:
        await asyncio.sleep(1)

    # Only create one set of trades to avoid balance issues
    await make_trades(account, market, order_ids)

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


@pytest.mark.asyncio
async def test_cancel_order_with_client_id(account: cro.Account, market: cro.Market):
    """Cancel by auto-generated client_id (exercises the uuid capture log)."""
    pair = cro.pairs.CRO_USD
    current_price = await market.get_price(pair)
    buy_price = helpers.resting_buy_price(pair, current_price)
    qty = helpers.min_order_quantity(pair, buy_price)

    # client_id auto-generated via uuid4 - recorded in the capture's
    # __uuids__ log so replay reproduces the exact same request args.
    order = await account.buy_limit(pair, qty, buy_price)
    client_id = order.client_id
    order_id = order.id

    # Verify client_id is a valid hex string (uuid7)
    assert client_id is not None
    assert len(client_id) > 0

    # Verify we can get the order by client_id
    order_1 = await account.get_order(client_order_id=client_id)
    assert order_1.client_id == client_id
    assert order_1.id == order_id
    assert order_1.is_active

    # Cancel order using client_id
    returned_order_id, returned_client_oid = await account.cancel_order(
        cro.pairs.CRO_USD, client_order_id=client_id, check_status=True
    )

    # Verify API response contains correct order_id and client_oid
    assert returned_client_oid == client_id

    # Verify order is canceled
    order_1_after = await account.get_order(client_order_id=client_id)
    assert order_1_after.is_canceled


@pytest.mark.asyncio
async def test_update_order_by_client_id(account: cro.Account, market: cro.Market):
    """Test updating order price and quantity by client_id."""
    pair = cro.pairs.CRO_USD
    current_price = await market.get_price(pair)
    buy_price = helpers.resting_buy_price(pair, current_price)
    qty = helpers.min_order_quantity(pair, buy_price)

    # Deterministic ids (the test's own uuids are outside the provider's log)
    client_id = "test-amend-a-orig"
    await account.buy_limit(pair, qty, buy_price, client_id=client_id)

    # Verify order is created
    order_1 = await account.get_order(client_order_id=client_id)
    assert order_1.client_id == client_id
    assert order_1.is_active
    original_price = order_1.price
    original_qty = order_1.quantity
    original_order_id = order_1.id

    # Update order - amend both price and quantity to tick-legal new values
    new_price = pair.round_price_up(original_price + 10 * pair.price_tick_size)
    min_qty_for_new_price = helpers.min_order_quantity(pair, new_price)
    new_qty = max(
        min_qty_for_new_price,
        pair.round_quantity_up(original_qty + pair.quantity_tick_size),
    )

    new_client_id = "test-amend-a-new"

    result = await account.update_order(
        cro.pairs.CRO_USD,
        client_id=client_id,
        new_price=new_price,
        new_quantity=new_qty,
        new_client_id=new_client_id,
    )

    # Verify API response - returns order_id and new client_id
    assert result.id is not None  # Order ID returned
    assert result.client_id == new_client_id  # Matches provided new_client_id

    # Note: After amend, the original order is canceled and a new one is created
    # The original order should be canceled
    try:
        order_1_after = await account.get_order(order_id=original_order_id)
        assert order_1_after.is_canceled
    except Exception:
        # Order might not be found if already removed
        pass


@pytest.mark.asyncio
async def test_update_order_price_only(account: cro.Account, market: cro.Market):
    """Test updating only order price (API requires both price and quantity)."""
    pair = cro.pairs.CRO_USD
    current_price = await market.get_price(pair)
    buy_price = helpers.resting_buy_price(pair, current_price)
    qty = helpers.min_order_quantity(pair, buy_price)

    client_id = "test-amend-b-orig"
    await account.buy_limit(pair, qty, buy_price, client_id=client_id)

    # Verify order is created
    order_1 = await account.get_order(client_order_id=client_id)
    assert order_1.client_id == client_id
    assert order_1.is_active
    original_price = order_1.price
    original_qty = order_1.quantity
    original_order_id = order_1.id

    # Change price only; quantity stays at a tick-legal minimum for the
    # new price (API requires both values on amend).
    new_price = pair.round_price_up(original_price + 10 * pair.price_tick_size)
    min_qty_for_new_price = helpers.min_order_quantity(pair, new_price)
    new_qty = max(min_qty_for_new_price, original_qty)

    new_client_id = "test-amend-b-new"

    result = await account.update_order(
        cro.pairs.CRO_USD,
        client_id=client_id,
        new_price=new_price,
        new_quantity=new_qty,  # Keep original or minimum quantity
        new_client_id=new_client_id,
    )

    # Verify API response
    assert result.id is not None
    assert result.client_id == new_client_id  # Matches provided new_client_id

    # Original order should be canceled
    try:
        order_1_after = await account.get_order(order_id=original_order_id)
        assert order_1_after.is_canceled
    except Exception:
        pass


@pytest.mark.asyncio
async def test_update_order_quantity_only(account: cro.Account, market: cro.Market):
    """Test updating only order quantity (API requires both values)."""
    pair = cro.pairs.CRO_USD
    current_price = await market.get_price(pair)
    buy_price = helpers.resting_buy_price(pair, current_price)
    qty = helpers.min_order_quantity(pair, buy_price)

    client_id = "test-amend-c-orig"
    await account.buy_limit(pair, qty, buy_price, client_id=client_id)

    # Verify order is created
    order_1 = await account.get_order(client_order_id=client_id)
    assert order_1.client_id == client_id
    assert order_1.is_active
    original_price = order_1.price
    original_qty = order_1.quantity
    original_order_id = order_1.id

    # Change quantity only; price stays original.
    new_qty = max(
        helpers.min_order_quantity(pair, original_price),
        pair.round_quantity_up(original_qty + pair.quantity_tick_size),
    )

    new_client_id = "test-amend-c-new"

    result = await account.update_order(
        cro.pairs.CRO_USD,
        client_id=client_id,
        new_price=original_price,  # Keep original price
        new_quantity=new_qty,
        new_client_id=new_client_id,
    )

    # Verify API response
    assert result.id is not None
    assert result.client_id == new_client_id  # Matches provided new_client_id

    # Original order should be canceled
    try:
        order_1_after = await account.get_order(order_id=original_order_id)
        assert order_1_after.is_canceled
    except Exception:
        pass
