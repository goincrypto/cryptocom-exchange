import os
import time
import pytest
import aiohttp
import asyncio

import cryptocom.exchange as cro
from cryptocom.exchange import rate_limiter


def test_timeframe():
    days_5 = cro.Timeframe.DAYS * 5
    result = cro.Timeframe.resolve(days_5)
    assert result - int(time.time()) == days_5
    assert cro.Timeframe.resolve(cro.Timeframe.NOW) == int(time.time())


def test_api_args(monkeypatch):
    with pytest.raises(ValueError):
        cro.Account()

    with pytest.raises(ValueError):
        cro.Account(api_key='123')

    with pytest.raises(ValueError):
        cro.Account(api_secret='3333')

    with pytest.raises(ValueError):
        cro.ApiProvider(api_key='123')

    with pytest.raises(ValueError):
        cro.ApiProvider(api_secret='123')

    monkeypatch.setattr(os, 'environ', {})

    with pytest.raises(ValueError):
        cro.Account(from_env=True)

    with pytest.raises(ValueError):
        cro.ApiProvider(from_env=True)

    monkeypatch.setattr(os, 'environ', {'CRYPTOCOM_API_KEY': '123'})

    with pytest.raises(ValueError):
        cro.Account(from_env=True)

    with pytest.raises(ValueError):
        cro.ApiProvider(from_env=True)


@pytest.mark.asyncio
async def test_wrong_api_response():
    api = cro.ApiProvider(from_env=True)

    with pytest.raises(cro.RateLimiterError):
        await api.get('somepath')

    api = cro.ApiProvider(auth_required=False)
    with pytest.raises(cro.RateLimiterError):
        await api.post('account')


# @pytest.mark.asyncio
# async def test_api_rate_limits():
#     api = cro.ApiProvider(from_env=True)
#     account = cro.Account(from_env=True)

#     rate_limiter = cro.RateLimiter(cro.api.limits)

#     for _ in range(0, 100):
#         print(await account.get_balance())

#     for _ in range(0, 100):
#         await account.get_orders_history(cro.pairs.CRO_USDT, page_size=50)
    
#     for _ in range(0, 100):
#         await api.get('public/get-ticker')
    
#     async with
