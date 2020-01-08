import pytest

import cryptocom.exchange as cro


@pytest.fixture
def exchange() -> cro.Exchange:
    return cro.Exchange()


@pytest.fixture
@pytest.mark.asyncio
async def account() -> cro.Account:
    acc = cro.Account(from_env=True)
    yield acc
    await acc.cancel_open_orders(cro.Symbol.CROUSDT)
