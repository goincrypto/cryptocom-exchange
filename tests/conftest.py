import os
import pathlib

import pytest
import pytest_asyncio

import cryptocom.exchange as cro


@pytest.fixture
def api(request):
    pathlib.Path(__file__).parent
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
    yield provider
    provider.save()


@pytest_asyncio.fixture
async def market(api: cro.RecordApiProvider) -> cro.Market:
    mkt = cro.Market(api=api)
    return mkt


@pytest_asyncio.fixture
async def account(api: cro.RecordApiProvider) -> cro.Account:
    acc = cro.Account(from_env=True, api=api)

    # Get initial balance
    balance = await acc.get_balance()
    cro_bal = balance.get(cro.instruments.CRO)
    usd_bal = balance.get(cro.instruments.USD)
    available_cro = cro_bal.available if cro_bal else 0
    available_usd = usd_bal.available if usd_bal else 0

    # Get current price
    market = cro.Market(api=api)
    price = await market.get_price(cro.pairs.CRO_USD)

    # Rebalance to ~50/50 if we have enough total value
    total_value = available_usd + (available_cro * price)
    if total_value > 10:  # Only rebalance if we have significant balance
        target_cro_qty = (total_value * 0.5) / price if price > 0 else 0
        cro_diff = available_cro - target_cro_qty

        if abs(cro_diff) > 5:  # Only trade if difference is significant
            if cro_diff > 0:
                # Sell excess CRO
                sell_qty = int(cro_diff)
                print(f"Rebalancing: Selling {sell_qty} CRO")
                try:
                    await acc.sell_market(cro.pairs.CRO_USD, sell_qty)
                except Exception as e:
                    print(f"Sell failed: {e}")
            elif cro_diff < 0:
                # Buy more CRO
                buy_spend = abs(cro_diff) * price
                if buy_spend > cro.pairs.CRO_USD.min_order_notional_usd:
                    print(f"Rebalancing: Buying CRO with {buy_spend} USD")
                    try:
                        await acc.buy_market(cro.pairs.CRO_USD, buy_spend)
                    except Exception as e:
                        print(f"Buy failed: {e}")

    yield acc

    # Cleanup: cancel open orders
    await acc.cancel_open_orders(cro.pairs.CRO_USD)
