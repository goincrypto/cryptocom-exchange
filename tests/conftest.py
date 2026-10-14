import os
import pathlib
from unittest.mock import patch

import pytest
import pytest_asyncio

import cryptocom.exchange as cro


@pytest.fixture
def api(request):
    # Get the test file path relative to tests directory, remove .py extension
    test_file = request.node.location[0].split("::")[0]
    relative_path = pathlib.Path(test_file).with_suffix("").name
    # Use node.name (includes params) instead of originalname for parametrized tests
    cache_file = pathlib.Path(
        "tests", "captured", relative_path, f"{request.node.name}.json"
    )
    value = os.environ.get("API_CAPTURE", "false")
    capture = value.lower() == "true"
    provider = cro.RecordApiProvider(
        cache_file=cache_file,
        capture=capture,
        divide_delay=10,
    )
    # client_oids are generated inside account.py - patch THAT name (the old
    # patch of uuid.uuid4 was bypassed by account's `from uuid import uuid4`).
    # next_uuid replays the exact ids recorded at capture time, so request
    # args match strictly.
    with patch("cryptocom.exchange.account.uuid4", provider.next_uuid):
        yield provider
    provider.save()


@pytest_asyncio.fixture
async def market(api: cro.RecordApiProvider) -> cro.Market:
    mkt = cro.Market(api=api)
    return mkt


REBALANCE_MIN_TOTAL_USD = 10.0
REBALANCE_TOLERANCE = 0.02  # stop when |imbalance| < 2% of total value
REBALANCE_MAX_ROUNDS = 3


async def _rebalance_50_50(acc: cro.Account) -> None:
    """Bring the USD/CRO balance to ~50/50 with pair-legal market orders.

    Rules:
    - sizes derived from live price and the pair's tick sizes/minimums
      (never hand-picked magic numbers);
    - deltas that cannot form a legal order are left alone;
    - orders wait for a terminal status so later tests see settled balances;
    - a failed round retries against refreshed balances, then gives up.
    """
    pair = cro.pairs.CRO_USD
    for round_ in range(REBALANCE_MAX_ROUNDS):
        balance = await acc.get_balance()
        usd_b = balance.get(cro.instruments.USD)
        cro_b = balance.get(cro.instruments.CRO)
        available_usd = usd_b.available if usd_b else 0.0
        available_cro = cro_b.available if cro_b else 0.0

        price = await acc.market.get_price(pair)
        if price <= 0:
            return
        total = available_usd + available_cro * price
        if total < REBALANCE_MIN_TOTAL_USD:
            return  # nothing meaningful to rebalance

        # + means holding too much CRO value, - too much USD.
        delta = available_cro * price - total / 2
        floor = max(total * REBALANCE_TOLERANCE, 2 * pair.min_order_notional_usd)
        if abs(delta) < floor:
            return  # balanced enough (or too small to trade legally)

        try:
            if delta > 0:
                qty = pair.round_quantity_down(abs(delta) / price)
                if qty <= 0 or qty * price < pair.min_order_notional_usd:
                    return
                print(f"Rebalance[{round_}]: SELL {qty} CRO (~{qty * price:.2f} USD)")
                await acc.sell_market(pair, qty, wait_for_fill=True)
            else:
                spend = pair.round_price_down(abs(delta))
                if spend < pair.min_order_notional_usd:
                    return
                print(f"Rebalance[{round_}]: BUY {spend:.2f} USD of CRO")
                await acc.buy_market(pair, spend, wait_for_fill=True)
        except cro.exceptions.ApiError as exc:
            # Refreshed balances next round decide the follow-up.
            print(f"Rebalance[{round_}] trade failed: {exc}")


@pytest_asyncio.fixture
async def account(api: cro.RecordApiProvider) -> cro.Account:
    acc = cro.Account(from_env=True, api=api)
    await _rebalance_50_50(acc)
    yield acc

    # Cleanup: never leave resting orders behind.
    await acc.cancel_open_orders(cro.pairs.CRO_USD)
