"""Offline tests for Account order cache (get_order, invalidation verbs).

The cache contract being pinned:
- UPSERT only from confirmed observations; terminal entries are immortal.
- POP only on confirmed absence (OrderNotFoundError), with a create-race
  guard that refuses to call a just-created order "absent".
- INVALIDATE on our own actions (cancel, amend) - never write assumed states.
- Indeterminate errors leave the cache untouched.
"""

import asyncio

import pytest
from test_cancel_wait import ScriptedApi, _order_detail

import cryptocom.exchange as cro


def _account(*, orders_ttl: float = 5.0, **script_kwargs):
    return cro.Account(api=ScriptedApi(**script_kwargs), orders_ttl=orders_ttl)


@pytest.mark.asyncio
async def test_fresh_cache_hit_skips_api():
    account = _account(order=_order_detail("ACTIVE"), orders_ttl=60.0)
    first = await account.get_order(client_order_id="b1-b1")
    second = await account.get_order(client_order_id="b1-b1")
    assert first is second
    assert account.api.detail_calls == 1


@pytest.mark.asyncio
async def test_terminal_entries_are_immortal():
    account = _account(order=_order_detail("FILLED"), orders_ttl=0.0)
    await account.get_order(client_order_id="b1-b1")
    for _ in range(3):
        await account.get_order(client_order_id="b1-b1")
    # Terminal: served from cache forever despite ttl=0.
    assert account.api.detail_calls == 1


@pytest.mark.asyncio
async def test_live_entries_expire_after_ttl():
    account = _account(order=_order_detail("ACTIVE"), orders_ttl=0.02)
    await account.get_order(client_order_id="b1-b1")
    await asyncio.sleep(0.05)
    await account.get_order(client_order_id="b1-b1")
    assert account.api.detail_calls == 2


@pytest.mark.asyncio
async def test_updates_take_priority_and_populate_cache():
    live = _order_detail("FILLED")
    update = cro.Order.create_from_api(cro.pairs.CRO_USD, live, [])
    account = _account(order=_order_detail("ACTIVE"), orders_ttl=60.0)

    order = await account.get_order(client_order_id="b1-b1", updates={"b1-b1": update})
    assert order.status is cro.OrderStatus.FILLED
    assert account.api.detail_calls == 0

    # Cache now holds the terminal update - no API call, no demotion.
    again = await account.get_order(client_order_id="b1-b1")
    assert again.status is cro.OrderStatus.FILLED
    assert account.api.detail_calls == 0


@pytest.mark.asyncio
async def test_terminal_cache_never_demoted_by_updates():
    account = _account(order=_order_detail("FILLED"), orders_ttl=60.0)
    await account.get_order(client_order_id="b1-b1")  # caches FILLED (terminal)

    stale_live = _order_detail("ACTIVE")
    stale = cro.Order.create_from_api(cro.pairs.CRO_USD, stale_live, [])
    order = await account.get_order(client_order_id="b1-b1", updates={"b1-b1": stale})
    # updates arg returns what the caller handed us, but the CACHE keeps truth:
    assert account.order_cache["b1-b1"].status is cro.OrderStatus.FILLED
    assert order.client_id == "b1-b1"


@pytest.mark.asyncio
async def test_ignore_cache_bypasses():
    account = _account(order=_order_detail("ACTIVE"), orders_ttl=60.0)
    await account.get_order(client_order_id="b1-b1")
    await account.get_order(client_order_id="b1-b1", ignore_cache=True)
    assert account.api.detail_calls == 2


@pytest.mark.asyncio
async def test_not_found_pops_cached_entry():
    account = _account(order=_order_detail("ACTIVE"), orders_ttl=60.0)
    await account.get_order(client_order_id="b1-b1")
    account.api.order = None  # order disappears on the exchange

    # This Account created nothing recently -> absence is confirmed.
    with pytest.raises(cro.exceptions.OrderNotFoundError):
        await account.get_order(client_order_id="b1-b1", ignore_cache=True)
    assert "b1-b1" not in account.order_cache


@pytest.mark.asyncio
async def test_create_race_reads_as_unknown_not_absent():
    """NotFound on a just-created oid must be INDETERMINATE, never NotFound."""
    account = _account(order=None)

    async def create_ok(method, payload=None):
        if method == "private/create-order":
            return {"order_id": "900000000099", "client_oid": "b1-b9"}
        return await original_post(method, payload)

    original_post = account.api.post
    account.api.post = create_ok
    await account.create_order(
        cro.pairs.CRO_USD,
        cro.OrderSide.BUY,
        cro.OrderType.LIMIT,
        quantity=1000.0,
        price=0.05,
        client_id="b1-b9",
    )
    # Exchange momentarily can't read the just-created order back.
    with pytest.raises(cro.exceptions.ApiError) as exc_info:
        await account.get_order(client_order_id="b1-b9", ignore_cache=True)
    assert not isinstance(exc_info.value, cro.exceptions.OrderNotFoundError)
    assert exc_info.value.is_indeterminate

    # Guard window passed -> absence becomes a confirmed answer again.
    account.create_race_guard = 0.0
    with pytest.raises(cro.exceptions.OrderNotFoundError):
        await account.get_order(client_order_id="b1-b9", ignore_cache=True)


@pytest.mark.asyncio
async def test_cancel_invalidates_but_does_not_write_status():
    account = _account(order=_order_detail("ACTIVE"), cancel_lands_as="CANCELED")
    await account.get_order(client_order_id="b1-b1")  # cache ACTIVE
    assert "b1-b1" in account.order_cache

    await account.cancel_order(cro.pairs.CRO_USD, client_order_id="b1-b1")
    # Entry dropped, CANCELED not synthesized - status must be observed.
    assert "b1-b1" not in account.order_cache


@pytest.mark.asyncio
async def test_amend_invalidates_predecessor_and_successor():
    account = _account(order=_order_detail("ACTIVE"))
    account.order_cache["b1-b1"] = await account.get_order(client_order_id="b1-b1")

    async def amend_ok(method, payload=None):
        if method == "private/amend-order":
            return {"result": {"order_id": "900000000002", "client_oid": "b1-b2"}}
        return await account.api_original_post(method, payload)

    account.api_original_post = account.api.post
    account.api.post = amend_ok

    await account.update_order(
        cro.pairs.CRO_USD,
        client_id="b1-b1",
        new_price=0.051,
        new_quantity=1000.0,
        new_client_id="b1-b2",
    )
    # Both oids unknown now - neither state may be served from cache.
    assert "b1-b1" not in account.order_cache
    assert "b1-b2" not in account.order_cache
