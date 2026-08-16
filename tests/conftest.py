import os
import pathlib
from unittest.mock import patch

import pytest
import pytest_asyncio
import uuid

import cryptocom.exchange as cro

# Fixed UUIDs for testing (extracted from captured fixtures)
FIXED_UUIDS = [
    "01a00c67b723703b9889b98434128471",
    "01a00c67b72571b7a1d2c2e3eebba429",
    "01a00c67b726759e8b4539a2eef5df2f",
    "01a00c67c3267525ae17b132ed9fd73f",
    "01a00c67c328701c82c70874d4472fd4",
    "01a00c67c3297335883fb3dec47a378e",
    "01a00c67c32a7098b7bd07f8cdf9ce19",
    "01a00c6806bf707c9275e84084f43f0a",
    "01a00c6a190774a9b51076922629761e",
    "01a00c6a190977ecbe3d16a461988ec4",
    "01a00c6a190a769f9296815a9126b847",
    "01a00c700d2b74548f3d72a32191707c",
    "01a00c700d2c7654808024100fb77ca2",
    "01a00c700d2d75dabe3bd3066ddad476",
    "01a00c701e5e758ba84164074f42e363",
    "01a00c701e5f73bcb70d9be11e589619",
    "01a00c701e6076c8afdab6b57c04da84",
    "01a00c701e6173d9a7dc38d5abc1242c",
    "01a00c70612c766da571b79fed43afc5",
    "0d9d4e8eb4a044da8aa91605b2c99579",
    "221446e45bfa4d4ba208a933e9c24f1f",
    "363d2420bb874305a8c87a9610ecf97a",
    "42803a788dc042f599cf8ee13976d246",
    "8c291611f3c8422a8ca2049fb13acf4d",
    "9c62558c81a04922bf1078fe867d3133",
    "a929d11adcb7420897d8ebf945e3cf76",
    "eefa5d232cd6472b82dae48ed2fa9bed",
]


@pytest.fixture(autouse=True)
def mock_uuid4():
    """Mock uuid4 to return fixed UUIDs for consistent test results."""
    uuid_iter = iter(FIXED_UUIDS)

    def mock_uuid4():
        class MockUUID:
            def __init__(self, hex):
                self.hex = hex

        try:
            return MockUUID(next(uuid_iter))
        except StopIteration:
            # Fallback to real uuid4 if we run out
            import uuid as real_uuid

            return MockUUID(real_uuid.uuid4().hex)

    with patch.object(uuid, "uuid4", mock_uuid4):
        yield


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
