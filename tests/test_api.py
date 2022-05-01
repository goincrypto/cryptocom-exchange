import asyncio
import os
import time

import pytest

import cryptocom.exchange as cro


def test_timeframe():
    days_5 = cro.Timeframe.DAYS * 5
    result = cro.Timeframe.resolve(days_5)
    assert result - int(time.time()) == days_5
    assert cro.Timeframe.resolve(cro.Timeframe.NOW) == int(time.time())


def test_api_args(monkeypatch):
    with pytest.raises(ValueError):
        cro.Account()

    with pytest.raises(ValueError):
        cro.Account(api_key="123")

    with pytest.raises(ValueError):
        cro.Account(api_secret="3333")

    with pytest.raises(ValueError):
        cro.ApiProvider(api_key="123")

    with pytest.raises(ValueError):
        cro.ApiProvider(api_secret="123")

    monkeypatch.setattr(os, "environ", {})

    with pytest.raises(ValueError):
        cro.Account(from_env=True)

    with pytest.raises(ValueError):
        cro.ApiProvider(from_env=True)

    monkeypatch.setattr(os, "environ", {"CRYPTOCOM_API_KEY": "123"})

    with pytest.raises(ValueError):
        cro.Account(from_env=True)

    with pytest.raises(ValueError):
        cro.ApiProvider(from_env=True)


@pytest.mark.asyncio
async def test_wrong_api_response():
    api = cro.ApiProvider(from_env=True)

    with pytest.raises(cro.ApiError):
        await api.get("somepath")

    api = cro.ApiProvider(auth_required=False)
    with pytest.raises(cro.ApiError):
        await api.post("account")


@pytest.mark.asyncio
async def test_api_rate_limits():
    api = cro.ApiProvider(from_env=True)
    pair = cro.pairs.CRO_USDT

    page = 0
    page_size = 50

    params = {"page_size": page_size, "page": page}

    if pair:
        params["instrument_name"] = pair.name

    start_time = time.time()
    tasks = [
        api.post("private/get-order-history", {"params": params})
        for _ in range(2)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 1

    start_time = time.time()
    tasks = [
        api.post("private/get-order-history", {"params": params})
        for _ in range(5)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 4

    start_time = time.time()
    tasks = [api.get("public/get-instruments") for _ in range(200)]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 1

    start_time = time.time()
    tasks = [
        api.post("private/get-order-history", {"params": params})
        for _ in range(4)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 3
