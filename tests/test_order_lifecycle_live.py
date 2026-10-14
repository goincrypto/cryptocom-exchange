"""Real-exchange lifecycle: create -> cached reads -> amend -> cancel.

The first end-to-end proof of the Account order cache against the REAL API:
response shapes, amend OID rotation, and cancel-to-terminal semantics are
exchange truth, not emulator truth. Recorded via RecordApiProvider so CI
replays deterministically afterwards.
"""

import contextlib

import pytest

import cryptocom.exchange as cro

PAIR = cro.pairs.CRO_USD


def _counting(api, method):
    """Wrap api.post to count calls to a specific endpoint."""
    counter = {"n": 0}
    original = api.post

    async def counting_post(m, payload=None):
        if m == method:
            counter["n"] += 1
        return await original(m, payload)

    api.post = counting_post
    return counter


@pytest.mark.asyncio
async def test_order_lifecycle_with_cache(account: cro.Account):
    api = account.api
    detail_calls = _counting(api, "private/get-order-detail")

    price = await account.market.get_price(PAIR)
    # Far below market: resting maker order that will not fill during the test.
    order_price = PAIR.round_price_down(price * 0.8)
    quantity = PAIR.round_quantity_up(max(2.0 / order_price, 10.0))

    client_id = "cachelive-a1"
    keys = await account.create_order(
        PAIR,
        cro.OrderSide.BUY,
        cro.OrderType.LIMIT,
        quantity=quantity,
        price=order_price,
        client_id=client_id,
    )
    assert keys.client_id == client_id

    try:
        # --- first read: exchange truth, populates cache -------------------
        order = await account.get_order(client_order_id=client_id)
        assert order.client_id == client_id
        assert order.limit_price == order_price
        assert not order.is_terminal
        assert detail_calls["n"] == 1

        # --- second read: served by cache, ZERO new API calls --------------
        cached = await account.get_order(client_order_id=client_id)
        assert cached is order
        assert detail_calls["n"] == 1

        # --- amend rotates the OID; both sides invalidated, guessed never --
        new_client_id = "cachelive-a2"
        amended = await account.update_order(
            PAIR,
            client_id=client_id,
            new_price=PAIR.round_price_down(order_price * 0.99),
            new_quantity=quantity,
            new_client_id=new_client_id,
        )
        assert amended.client_id == new_client_id
        assert client_id not in account.order_cache
        assert new_client_id not in account.order_cache

        # --- successor is real and readable under its own OID --------------
        successor = await account.get_order(client_order_id=new_client_id)
        assert successor.client_id == new_client_id
        assert successor.limit_price < order_price

        # --- cancel to terminal through the polling primitive --------------
        final = await account.cancel_order_and_wait(PAIR, new_client_id, timeout=20.0)
        assert final is not None
        assert final.is_terminal
        assert final.status in (
            cro.OrderStatus.CANCELED,
            cro.OrderStatus.EXPIRED,
            cro.OrderStatus.REJECTED,
        )

        # --- terminal entry is now immortal (cached forever) ---------------
        calls_before = detail_calls["n"]
        again = await account.get_order(client_order_id=new_client_id)
        assert again is final
        assert detail_calls["n"] == calls_before
    finally:
        # Belt and braces: never leave a resting test order behind.
        # Best-effort - a1 is expected-absent (amended away), and a cancel
        # on an already-terminal order is a no-op.
        for oid in (client_id, new_client_id):
            with contextlib.suppress(cro.exceptions.ApiError):
                await account.cancel_order_and_wait(PAIR, oid, timeout=10.0)
