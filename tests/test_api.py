import asyncio
import hmac
import hashlib
import os
import time

import pytest

import cryptocom.exchange as cro
from cryptocom.exchange.api import params_to_str as our_params_to_str


# ==============================================================================
# Documentation Reference Implementation
# ==============================================================================
# Exact copy from Crypto.com API documentation
# https://exchange-docs.crypto.com/exchange/v1/rest-ws/index.html#authentication


def doc_params_to_str(obj, level):
    """Documentation example implementation of params_to_str."""
    MAX_LEVEL = 3
    if level >= MAX_LEVEL:
        return str(obj)

    return_str = ""
    for key in sorted(obj):
        return_str += key
        if obj[key] is None:
            return_str += "null"
        elif isinstance(obj[key], list):
            for subObj in obj[key]:
                return_str += doc_params_to_str(subObj, level + 1)
        else:
            return_str += str(obj[key])
    return return_str


def doc_sign(req, SECRET_KEY):
    """Documentation example signature generation."""
    param_str = ""
    if "params" in req:
        param_str = doc_params_to_str(req["params"], 0)

    payload_str = (
        req["method"] + str(req["id"]) + req["api_key"] + param_str + str(req["nonce"])
    )

    return hmac.new(
        bytes(str(SECRET_KEY), "utf-8"),
        msg=bytes(payload_str, "utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


# ==============================================================================
# Signature Tests
# ==============================================================================


@pytest.mark.parametrize(
    "test_name,api_key,secret_key,req",
    [
        (
            "simple_request",
            "API_KEY",
            "SECRET_KEY",
            {
                "id": "1",
                "method": "private/get-open-orders",
                "api_key": "API_KEY",
                "params": {"page_size": 10, "page": 0},
                "nonce": "1234567890123",
            },
        ),
        (
            "order_list_request",
            "API_KEY",
            "SECRET_KEY",
            {
                "id": "14",
                "method": "private/create-order-list",
                "api_key": "API_KEY",
                "params": {
                    "contingency_type": "LIST",
                    "order_list": [
                        {
                            "instrument_name": "ONE_USDT",
                            "side": "BUY",
                            "type": "LIMIT",
                            "price": "0.24",
                            "quantity": "1.0",
                        },
                        {
                            "instrument_name": "ONE_USDT",
                            "side": "BUY",
                            "type": "STOP_LIMIT",
                            "price": "0.27",
                            "quantity": "1.0",
                            "trigger_price": "0.26",
                        },
                    ],
                },
                "nonce": "1234567890123",
            },
        ),
        (
            "create_order_request",
            "API_KEY",
            "SECRET_KEY",
            {
                "id": "42",
                "method": "private/create-order",
                "api_key": "API_KEY",
                "params": {
                    "instrument_name": "BTC_USDT",
                    "side": "BUY",
                    "type": "LIMIT",
                    "price": "50000.00",
                    "quantity": "0.001",
                },
                "nonce": "9876543210987",
            },
        ),
        (
            "get_order_history_request",
            "API_KEY",
            "SECRET_KEY",
            {
                "id": "100",
                "method": "private/get-order-history",
                "api_key": "API_KEY",
                "params": {
                    "page_size": 50,
                    "page": 0,
                    "instrument_name": "CRO_USDT",
                },
                "nonce": "1111111111111",
            },
        ),
    ],
)
def test_signature_matches_documentation(test_name, api_key, secret_key, req):
    """Test that our signature generation matches Crypto.com documentation."""
    doc_sig = doc_sign(req, secret_key)

    doc_param_str = doc_params_to_str(req["params"], 0)
    doc_payload = (
        req["method"]
        + str(req["id"])
        + req["api_key"]
        + doc_param_str
        + str(req["nonce"])
    )

    our_param_str = our_params_to_str(req["params"], 0)
    our_payload = (
        req["method"]
        + str(req["id"])
        + req["api_key"]
        + our_param_str
        + str(req["nonce"])
    )

    our_sig = hmac.new(
        bytes(str(secret_key), "utf-8"),
        msg=bytes(our_payload, "utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    assert (
        doc_param_str == our_param_str
    ), f"[{test_name}] param_str differs!\nDoc: {doc_param_str}\nOur: {our_param_str}"
    assert (
        doc_payload == our_payload
    ), f"[{test_name}] Payloads differ!\nDoc: {doc_payload}\nOur: {our_payload}"
    assert (
        doc_sig == our_sig
    ), f"[{test_name}] Signatures differ!\nDoc: {doc_sig}\nOur: {our_sig}"


@pytest.mark.parametrize(
    "test_name,params,expected_substrings",
    [
        ("empty_dict", {}, [""]),
        ("simple_flat", {"b": "2", "a": "1", "c": "3"}, ["a1b2c3"]),
        ("none_values", {"a": "1", "b": None, "c": "3"}, ["a1bnullc3"]),
        (
            "numeric_values",
            {"count": 42, "price": 123.45},
            ["count42", "price123.45"],
        ),
        (
            "list_of_dicts_single",
            {"items": [{"name": "test", "value": "123"}]},
            ["itemsname", "testvalue123"],
        ),
        (
            "list_of_dicts_multiple",
            {
                "contingency_type": "LIST",
                "order_list": [
                    {"instrument_name": "ONE_USDT", "side": "BUY"},
                    {"instrument_name": "ONE_USDT", "side": "SELL"},
                ],
            },
            [
                "contingency_typeLIST",
                "instrument_nameONE_USDT",
                "sideBUY",
                "sideSELL",
            ],
        ),
        (
            "real_api_params",
            {"page_size": 50, "page": 0, "instrument_name": "CRO_USDT"},
            ["instrument_nameCRO_USDT", "page0", "page_size50"],
        ),
    ],
)
def test_params_to_str_matches_documentation(test_name, params, expected_substrings):
    """Test that our params_to_str matches Crypto.com documentation."""
    doc_result = doc_params_to_str(params, 0)
    our_result = our_params_to_str(params, 0)

    assert (
        doc_result == our_result
    ), f"[{test_name}] Results differ!\nDoc: {doc_result}\nOur: {our_result}"

    for substring in expected_substrings:
        assert (
            substring in our_result
        ), f"[{test_name}] Expected '{substring}' not found in result: {our_result}"


def test_actual_api_sign_method():
    """Test the actual ApiProvider.sign() method produces valid signatures."""
    api = cro.ApiProvider(
        api_key="test_key",
        api_secret="test_secret",
        auth_required=True,
    )

    path = "private/create-order"
    data = {
        "params": {
            "instrument_name": "BTC_USDT",
            "side": "BUY",
            "type": "LIMIT",
            "price": "50000",
            "quantity": "1.0",
        }
    }

    signed_data = api.sign(path, data)

    assert "sig" in signed_data
    assert "nonce" in signed_data
    assert "id" in signed_data
    assert "api_key" in signed_data
    assert "method" in signed_data
    assert signed_data["api_key"] == "test_key"
    assert signed_data["method"] == path
    assert signed_data["sig"] is not None
    assert len(signed_data["sig"]) == 64  # SHA256 hex is 64 chars
    int(signed_data["sig"], 16)  # Should not raise


def test_actual_api_sign_with_real_credentials():
    """Test ApiProvider.sign() with real API credentials."""
    api_key = os.environ.get("CRYPTOCOM_API_KEY", "")
    api_secret = os.environ.get("CRYPTOCOM_API_SECRET", "")

    if not api_key or not api_secret:
        pytest.skip("API credentials not set in environment")

    api = cro.ApiProvider(api_key=api_key, api_secret=api_secret)

    path = "private/get-open-orders"
    data = {"params": {"page_size": 10}}

    signed_data = api.sign(path, data)

    assert "sig" in signed_data
    assert signed_data["api_key"] == api_key
    assert signed_data["method"] == path


@pytest.mark.asyncio
async def test_timedelta():
    days_5 = cro.TimeDelta.DAYS * 5
    result = cro.TimeDelta.resolve(days_5)
    assert result - int(time.time() * 1000) == days_5 * 1000
    assert cro.TimeDelta.resolve(cro.TimeDelta.NOW) == int(time.time() * 1000)


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
async def test_wrong_api_response(api):
    with pytest.raises(cro.ApiError):
        await api.get("somepath")

    api = cro.ApiProvider(auth_required=False)
    with pytest.raises(cro.ApiError):
        await api.post("account")


@pytest.mark.asyncio
async def test_api_rate_limits(api):
    api.divide_delay = 1
    pair = cro.pairs.CRO_USDT

    page = 0
    page_size = 50

    params = {"page_size": page_size, "page": page}

    if pair:
        params["instrument_name"] = pair.name

    start_time = time.time()
    tasks = [
        api.post("private/get-order-history", {"params": params}) for _ in range(2)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 1

    start_time = time.time()
    tasks = [
        api.post("private/get-order-history", {"params": params}) for _ in range(10)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 4

    start_time = time.time()
    tasks = [
        api.get("public/get-tickers", params={"instrument_name": "CRO_USD"})
        for _ in range(200)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 1

    start_time = time.time()
    tasks = [
        api.post("private/get-order-history", {"params": params}) for _ in range(10)
    ]
    await asyncio.gather(*tasks)

    finish_time = time.time() - start_time
    assert finish_time > 3
