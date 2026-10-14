"""Offline behavioral tests for Account.cancel_order_and_wait.

A scripted ApiProvider stands in for the exchange: every cancel race and
failure mode is deterministic here, which is exactly why this logic belongs
in the package next to the error taxonomy.
"""

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
    order = await account.cancel_order_and_wait(cro.pairs.CRO_USD, "b1-b1", timeout=2.0)
    assert order is not None
    assert order.status == cro.OrderStatus.CANCELED
    assert order.is_terminal
    assert account.api.cancel_calls == 1
    # Terminal found on the first poll - no busy-waiting happened.
    assert account.api.detail_calls == 2


@pytest.mark.asyncio
async def test_already_terminal_order_needs_no_cancel():
    account = _account(order=_order_detail("FILLED"))
    order = await account.cancel_order_and_wait(cro.pairs.CRO_USD, "b1-b1", timeout=2.0)
    assert order.status == cro.OrderStatus.FILLED
    assert account.api.cancel_calls == 0


@pytest.mark.asyncio
async def test_absent_order_returns_none_without_cancel():
    account = _account(order=None)
    order = await account.cancel_order_and_wait(cro.pairs.CRO_USD, "b1-b1", timeout=2.0)
    assert order is None
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

    order = await account.cancel_order_and_wait(cro.pairs.CRO_USD, "b1-b1", timeout=2.0)
    assert order.status == cro.OrderStatus.FILLED


@pytest.mark.asyncio
async def test_order_vanishing_under_cancel_is_confirmed_absent():
    account = _account(order=_order_detail("ACTIVE"), order_vanishes_on_cancel=True)
    order = await account.cancel_order_and_wait(cro.pairs.CRO_USD, "b1-b1", timeout=2.0)
    assert order is None


@pytest.mark.asyncio
async def test_timeout_raises_indeterminate_cancel_error():
    """Never-terminal order => CancelNotConfirmedError, an indeterminate error."""
    account = _account(order=_order_detail("ACTIVE"))
    with pytest.raises(cro.exceptions.CancelNotConfirmedError) as exc_info:
        await account.cancel_order_and_wait(
            cro.pairs.CRO_USD, "b1-b1", timeout=0.3, poll_interval=0.05
        )
    assert exc_info.value.code is None
    assert exc_info.value.is_indeterminate
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
    assert not isinstance(exc_info.value, cro.exceptions.CancelNotConfirmedError)
