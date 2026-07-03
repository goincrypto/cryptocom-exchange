import asyncio
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
async def exchange(api: cro.RecordApiProvider) -> cro.Exchange:
    ex = cro.Exchange(api=api)
    return ex


@pytest_asyncio.fixture
async def account(api: cro.RecordApiProvider) -> cro.Account:
    acc = cro.Account(from_env=True, api=api)
    yield acc
    await acc.cancel_open_orders(cro.pairs.CRO_USD)


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

    loop.run_until_complete(asyncio.tasks.gather(*to_cancel, return_exceptions=True))

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
