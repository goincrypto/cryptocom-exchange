"""Offline behavioral tests for Account.cancel_order_and_wait.

Bool contract: True = CONFIRMED not live (terminal, absent, or raced into
either); False = cancellation NOT confirmed (timeout or still live). Only
indeterminate errors raise. A scripted ApiProvider stands in for the
exchange: every cancel race and failure mode is deterministic here, which
is exactly why this logic belongs in the package next to the taxonomy.
"""

import time

import pytest

import cryptocom.exchange as cro


def _order_detail(status="NEW", client_oid="b1-b1"):
    return {
        "order_id": "900000000001",
        "account_id": "1",
        "client_oid": client_oid,
        "instrument_name": "CRO_USD",
        "order_type": "LIMIT",
        "time_in_force": "GOOD_TILL_CANCEL",
        "side": "BUY",
        "exec_inst": [],
        "quantity": 1000.0,
        "limit_price": 0.05,
        "order_value": 50.0,
        "avg_price": 0.0,
        "cumulative_quantity": 0.0,
        "cumulative_value": 0.0,
        "cumulative_fee": 0.0,
        "status": status,
        "update_user_id": "1",
        "order_date": "1700000000000",
        "fee_instrument_name": "USD",
        "create_time": 1700000000000,
        "create_time_ns": 1700000000000000000,
        "update_time": 1700000000000,
    }


class ScriptedApi(cro.ApiProvider):
    """Deterministic exchange stand-in for cancel/order-detail flows."""

    def __init__(
        self,
        order=None,
        *,
        cancel_error=None,
        cancel_lands_as=None,
        order_vanishes_on_cancel=False,
    ):
        super().__init__(api_key="test", api_secret="test", auth_required=False)
        self.order = order
        self.cancel_error = cancel_error
        self.cancel_lands_as = cancel_lands_as
        self.order_vanishes_on_cancel = order_vanishes_on_cancel
        self.cancel_calls = 0
        self.detail_calls = 0

    async def post(self, method, payload=None):
        if method == "private/get-order-detail":
            self.detail_calls += 1
            if self.order is None:
                return []
            return dict(self.order)
        if method == "private/cancel-order":
            self.cancel_calls += 1
            if self.cancel_error is not None:
                raise self.cancel_error
            if self.order_vanishes_on_cancel:
                self.order = None
            elif self.cancel_lands_as is not None:
                self.order["status"] = self.cancel_lands_as
            return {"order_id": "900000000001", "client_oid": "b1-b1"}
        raise AssertionError(f"unexpected API method in test: {method}")


def _account(**script_kwargs):
    return cro.Account(api=ScriptedApi(**script_kwargs))


@pytest.mark.asyncio
async def test_cancel_new_order_confirms_canceled():
    account = _account(order=_order_detail("NEW"), cancel_lands_as="CANCELED")
    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=2.0
    )
    assert confirmed is True
    assert account.api.cancel_calls == 1
    # Terminal found on the first poll - no busy-waiting happened.
    assert account.api.detail_calls == 2


@pytest.mark.asyncio
async def test_already_terminal_order_needs_no_cancel():
    account = _account(order=_order_detail("FILLED"))
    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=2.0
    )
    assert confirmed is True
    assert account.api.cancel_calls == 0


@pytest.mark.asyncio
async def test_absent_order_is_confirmed_not_live_without_cancel():
    account = _account(order=None)
    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=2.0
    )
    assert confirmed is True
    assert account.api.cancel_calls == 0


@pytest.mark.asyncio
async def test_cancel_racing_to_fill_is_terminal_success():
    """316 on cancel (it filled meanwhile) resolves via re-query, not error."""
    account = _account(order=_order_detail("ACTIVE"))
    account.api.cancel_error = cro.exceptions.OrderNotActiveError(
        "order is not active", code=316, method="private/cancel-order"
    )
    original_post = account.api.post

    async def post_that_fills(method, payload=None):
        if method == "private/cancel-order":
            account.api.order["status"] = "FILLED"
        return await original_post(method, payload)

    account.api.post = post_that_fills

    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=2.0
    )
    assert confirmed is True


@pytest.mark.asyncio
async def test_order_vanishing_under_cancel_is_confirmed_absent():
    account = _account(order=_order_detail("ACTIVE"), order_vanishes_on_cancel=True)
    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=2.0
    )
    assert confirmed is True


@pytest.mark.asyncio
async def test_cancel_rejected_order_confirmed_live_returns_false():
    """316 + re-query still ACTIVE => definitively not cancelled: False."""
    account = _account(order=_order_detail("ACTIVE"))
    account.api.cancel_error = cro.exceptions.OrderNotActiveError(
        "order is not active", code=316, method="private/cancel-order"
    )
    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=2.0
    )
    assert confirmed is False


@pytest.mark.asyncio
async def test_timeout_returns_false_not_cancelled():
    """Never-terminal order => False: not confirmed, cancel may still land."""
    account = _account(order=_order_detail("ACTIVE"))
    confirmed = await account.cancel_order_and_wait(
        cro.pairs.CRO_USD, "b1-b1", timeout=0.3, poll_interval=0.05
    )
    assert confirmed is False
    assert account.api.cancel_calls == 1


@pytest.mark.asyncio
async def test_indeterminate_cancel_error_propagates():
    """A transport-style ApiError on cancel must propagate, not resolve."""
    account = _account(order=_order_detail("ACTIVE"))
    account.api.cancel_error = cro.exceptions.ApiError(
        "connection reset", method="private/cancel-order"
    )
    with pytest.raises(cro.exceptions.ApiError) as exc_info:
        await account.cancel_order_and_wait(cro.pairs.CRO_USD, "b1-b1", timeout=2.0)
    assert exc_info.value.is_indeterminate


# ============================================================================
# resolve_stuck_order - the shadow-order mechanic
# ============================================================================


def _fresh_order_detail(**kwargs):
    detail = _order_detail(**kwargs)
    detail["create_time"] = int(time.time() * 1000)
    return detail


@pytest.mark.asyncio
async def test_stuck_new_order_cancelled_is_clear():
    """NEW for > stuck_after and cancelable => clear to proceed (False)."""
    account = _account(order=_order_detail("NEW"), cancel_lands_as="CANCELED")
    order = await account.get_order(client_order_id="b1-b1")
    stuck = await account.resolve_stuck_order(cro.pairs.CRO_USD, order, timeout=1.0)
    assert stuck is False
    assert account.api.cancel_calls == 1


@pytest.mark.asyncio
async def test_stuck_new_order_never_removes_is_stuck():
    """NEW for > stuck_after and NOT removable => stuck (True)."""
    account = _account(order=_order_detail("NEW"))  # cancel lands, stays NEW
    order = await account.get_order(client_order_id="b1-b1")
    stuck = await account.resolve_stuck_order(
        cro.pairs.CRO_USD, order, timeout=0.2, poll_interval=0.05
    )
    assert stuck is True


@pytest.mark.asyncio
async def test_active_order_is_never_stuck():
    account = _account(order=_order_detail("ACTIVE"))
    order = await account.get_order(client_order_id="b1-b1")
    stuck = await account.resolve_stuck_order(cro.pairs.CRO_USD, order)
    assert stuck is False
    assert account.api.cancel_calls == 0


@pytest.mark.asyncio
async def test_fresh_new_order_is_not_stuck_yet():
    """NEW but younger than stuck_after: no cancel attempted."""
    account = _account(order=_fresh_order_detail(status="NEW"))
    order = await account.get_order(client_order_id="b1-b1")
    stuck = await account.resolve_stuck_order(cro.pairs.CRO_USD, order)
    assert stuck is False
    assert account.api.cancel_calls == 0


@pytest.mark.asyncio
async def test_stuck_resolution_indeterminate_error_propagates():
    """Unknown cancel outcome raises - never reported as stuck or clear."""
    account = _account(order=_order_detail("NEW"))
    account.api.cancel_error = cro.exceptions.ApiError(
        "connection reset", method="private/cancel-order"
    )
    order = await account.get_order(client_order_id="b1-b1")
    with pytest.raises(cro.exceptions.ApiError) as exc_info:
        await account.resolve_stuck_order(cro.pairs.CRO_USD, order)
    assert exc_info.value.is_indeterminate
