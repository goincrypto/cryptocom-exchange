import os
import pytest

import cryptocom.exchange as cro


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

    with pytest.raises(cro.ApiError):
        await api.get('somepath')

    api = cro.ApiProvider(auth_required=False)
    with pytest.raises(cro.ApiError):
        await api.post('account')
