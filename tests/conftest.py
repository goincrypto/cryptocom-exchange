import pytest

import cryptocom.exchange as cro


@pytest.fixture
async def exchange() -> cro.Exchange:
    ex = cro.Exchange()
    await ex.sync_pairs()
    return ex


@pytest.fixture
@pytest.mark.asyncio
async def account() -> cro.Account:
    acc = cro.Account(from_env=True)
    await acc.sync_pairs()
    yield acc
    await acc.cancel_open_orders(cro.pairs.CRO_USDT)
