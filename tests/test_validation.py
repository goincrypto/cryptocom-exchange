"""Validation raises + wait_for_order semantics, fully offline."""

import pytest
from test_cancel_wait import ScriptedApi, _order_detail

import cryptocom.exchange as cro


def _account(**kwargs):
    return cro.Account(api=ScriptedApi(**kwargs))


PAIR = cro.pairs.CRO_USD


# ============================================================================
# create_order / update_order validation (deterministic ValueErrors, no API)
# ============================================================================


@pytest.mark.asyncio
async def test_create_order_below_min_notional_rejected():
    account = _account(order=None)
    with pytest.raises(ValueError, match="notional"):
        await account.create_order(
            PAIR,
            cro.OrderSide.BUY,
            cro.OrderType.LIMIT,
            quantity=1.0,  # 1 unit of CRO ~ cents - below min notional
            price=0.0001,
            client_id="val-a1",
        )


@pytest.mark.asyncio
async def test_create_order_market_with_price_rejected():
    account = _account(order=None)
    with pytest.raises(ValueError, match="MARKET"):
        await account.create_order(
            PAIR,
            cro.OrderSide.BUY,
            cro.OrderType.MARKET,
            quantity=1000.0,
            price=0.05,
            client_id="val-a2",
        )


@pytest.mark.asyncio
async def test_create_order_rejects_empty_client_id():
    account = _account(order=None)
    with pytest.raises(ValueError):
        await account.create_order(
            PAIR,
            cro.OrderSide.BUY,
            cro.OrderType.LIMIT,
            quantity=1000.0,
            price=0.05,
            client_id="",
        )


@pytest.mark.asyncio
async def test_update_order_requires_order_id():
    account = _account(order=None)
    with pytest.raises(ValueError, match="order_id"):
        await account.update_order(PAIR, new_price=0.05, new_quantity=1000.0)


@pytest.mark.asyncio
async def test_update_order_requires_new_values():
    account = _account(order=None)
    with pytest.raises(ValueError, match="new_price"):
        await account.update_order(PAIR, client_id="val-b1")


@pytest.mark.asyncio
async def test_update_order_below_min_notional_rejected():
    account = _account(order=None)
    with pytest.raises(ValueError, match="notional"):
        await account.update_order(
            PAIR,
            client_id="val-b2",
            new_price=0.0001,
            new_quantity=1.0,
            new_client_id="val-b3",
        )


# ============================================================================
# wait_for_order
# ============================================================================


@pytest.mark.asyncio
async def test_wait_for_order_times_out_indeterminate():
    account = _account(order=_order_detail("ACTIVE"))
    with pytest.raises(cro.exceptions.WaitNotConfirmedError) as exc_info:
        await account.wait_for_order(
            (cro.OrderStatus.FILLED,),
            client_order_id="b1-b1",
            timeout=0.2,
            poll_interval=0.05,
        )
    assert exc_info.value.is_indeterminate
    assert account.api.detail_calls >= 2  # really polled


@pytest.mark.asyncio
async def test_wait_for_order_returns_on_status_change():
    """NEW on first poll, FILLED on second -> returns FILLED order."""
    account = _account(order=_order_detail("NEW"))
    original_post = account.api.post

    async def filling_post(method, payload=None):
        if method == "private/get-order-detail" and account.api.detail_calls >= 2:
            account.api.order["status"] = "FILLED"
        return await original_post(method, payload)

    account.api.post = filling_post

    order = await account.wait_for_order(
        (cro.OrderStatus.FILLED,),
        client_order_id="b1-b1",
        timeout=2.0,
        poll_interval=0.01,
    )
    assert order.status is cro.OrderStatus.FILLED


@pytest.mark.asyncio
async def test_wait_for_order_tolerates_absent_until_deadline():
    """A just-vanished order must not end the wait early - only timeout can."""
    account = _account(order=None)  # always absent
    with pytest.raises(cro.exceptions.WaitNotConfirmedError, match="absent"):
        await account.wait_for_order(
            (cro.OrderStatus.FILLED,),
            client_order_id="b1-b9",
            timeout=0.15,
            poll_interval=0.05,
        )


@pytest.mark.asyncio
async def test_wait_for_order_requires_an_id():
    account = _account(order=None)
    with pytest.raises(ValueError, match="order_id"):
        await account.wait_for_order((cro.OrderStatus.FILLED,))


@pytest.mark.asyncio
async def test_wait_for_status_deprecated_but_working():
    account = _account(order=_order_detail("ACTIVE"))
    with pytest.warns(DeprecationWarning, match="wait_for_order"):
        await account.wait_for_status(
            "900000000001", (cro.OrderStatus.ACTIVE,), delay=0.01
        )


# ============================================================================
# Order struct properties (from realistic API payloads)
# ============================================================================


def test_order_price_prefers_filled_then_limit():
    unfilled = cro.Order.create_from_api(cro.pairs.CRO_USD, _order_detail("ACTIVE"), [])
    assert unfilled.limit_price == 0.05
    # avg_price 0.0 is falsy -> price falls back to limit_price
    assert unfilled.price == 0.05

    filled_detail = _order_detail("FILLED")
    filled_detail["avg_price"] = 0.0512
    filled = cro.Order.create_from_api(cro.pairs.CRO_USD, filled_detail, [])
    assert filled.price == 0.0512


def test_order_remain_quantity_rounds_down():
    order = cro.Order.create_from_api(cro.pairs.CRO_USD, _order_detail("ACTIVE"), [])
    # quantity 1000, filled 0 -> remain 1000 (tick-legal)
    assert order.remain_quantity == 1000.0
    assert order.is_terminal is False


def test_order_is_terminal_for_all_terminal_statuses():
    for status in ("FILLED", "CANCELED", "REJECTED", "EXPIRED"):
        order = cro.Order.create_from_api(cro.pairs.CRO_USD, _order_detail(status), [])
        assert order.is_terminal is True, status
    for status in ("NEW", "PENDING", "ACTIVE"):
        order = cro.Order.create_from_api(cro.pairs.CRO_USD, _order_detail(status), [])
        assert order.is_terminal is False, status
