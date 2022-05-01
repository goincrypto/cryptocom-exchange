import asyncio

import pytest

import cryptocom.exchange as cro


@pytest.fixture
async def exchange() -> cro.Exchange:
    ex = cro.Exchange()
    await ex.sync_pairs()
    return ex


@pytest.fixture
async def account() -> cro.Account:
    acc = cro.Account(from_env=True)
    await acc.sync_pairs()
    yield acc
    await acc.cancel_open_orders(cro.pairs.CRO_USDT)


@pytest.fixture
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.events.new_event_loop()
    try:
        asyncio.events.set_event_loop(loop)
        yield loop
    finally:
        try:
            _cancel_all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
            if hasattr(loop, "shutdown_default_executor"):
                loop.run_until_complete(loop.shutdown_default_executor())
        finally:
            asyncio.events.set_event_loop(None)
            loop.close()


def _cancel_all_tasks(loop):
    to_cancel = asyncio.tasks.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        asyncio.tasks.gather(*to_cancel, return_exceptions=True)
    )

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler(
                {
                    "message": "unhandled exception during asyncio.run()",
                    "exception": task.exception(),
                    "task": task,
                }
            )
