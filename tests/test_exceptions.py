"""Tests for the typed API error taxonomy.

Pure unit tests (no network): every documented error code must map to a
specific exception class, unknown codes must stay deterministic-but-generic,
and transport-level ApiError must remain distinguishable as INDETERMINATE.
"""

import pytest

import cryptocom.exchange as cro


def test_code_to_class_mapping():
    cases = {
        40401: cro.exceptions.OrderNotFoundError,
        306: cro.exceptions.NotEnoughBalanceError,
        20002: cro.exceptions.NotEnoughBalanceError,
        316: cro.exceptions.OrderNotActiveError,
        204: cro.exceptions.DuplicateClientIdError,
        205: cro.exceptions.DuplicateOrderIdError,
        206: cro.exceptions.InvalidInstrumentError,
        318: cro.exceptions.OrderLimitExceededError,
        43003: cro.exceptions.FillOrKillRejectedError,
        43005: cro.exceptions.PostOnlyRejectedError,
        42901: cro.exceptions.RateLimitExceededError,
        40801: cro.exceptions.RequestTimeoutError,
        50001: cro.exceptions.InternalError,
        9010001: cro.exceptions.MaintenanceError,
        40102: cro.exceptions.InvalidNonceError,  # auth family (ApiAuthError), not ExchangeError
        10002: cro.exceptions.PermissionDeniedError,
        40001: cro.exceptions.BadRequestError,
        314: cro.exceptions.InvalidOrderError,
    }
    for code, cls in cases.items():
        err = cro.exceptions.api_error_from_response(code, f"msg {code}")
        assert type(err) is cls, f"code {code}: {type(err)} != {cls}"
        assert err.code == code
        assert isinstance(err, cro.exceptions.ApiError)
        if issubclass(cls, (cro.exceptions.RequestTimeoutError, cro.exceptions.InternalError)):
            # known code, unknown outcome - see dedicated test below
            assert err.is_indeterminate
        else:
            assert not err.is_indeterminate
        if not issubclass(cls, cro.exceptions.ApiAuthError):
            assert isinstance(err, cro.exceptions.ExchangeError)


def test_unknown_code_stays_deterministic_generic():
    err = cro.exceptions.api_error_from_response(999999, "weird")
    assert type(err) is cro.exceptions.ExchangeError
    assert err.code == 999999
    assert not err.is_indeterminate
    assert not cro.exceptions.is_retryable_error_code(999999)


@pytest.mark.parametrize(
    "code_klass",
    [cro.exceptions.RequestTimeoutError, cro.exceptions.InternalError],
)
def test_timeout_and_internal_are_indeterminate_despite_code(code_klass):
    """Known code != known outcome: a timeout may still have been processed."""
    err = code_klass("ambiguous", code=40801)
    assert err.code == 40801
    assert err.is_indeterminate


def test_transport_error_is_indeterminate():
    err = cro.exceptions.ApiError("Timeout or read error")
    assert err.code is None
    assert err.is_indeterminate
    assert not isinstance(err, cro.exceptions.ExchangeError)


def test_retryable_codes():
    for code in (40801, 42901, 10006, 50001, 120009, 9010001):
        assert cro.exceptions.is_retryable_error_code(code), code
    # Deterministic rejections must never be retried.
    for code in (204, 306, 316, 318, 40401, 43003):
        assert not cro.exceptions.is_retryable_error_code(code), code


def test_not_found_hierarchy_short_circuits():
    err = cro.exceptions.OrderNotFoundError("gone", code=40401)
    # catchable as generic ExchangeError/ApiError AND specifically
    assert isinstance(err, cro.exceptions.ExchangeError)
    assert isinstance(err, cro.exceptions.ApiError)


def test_auth_error_base():
    assert issubclass(cro.exceptions.ApiAuthError, cro.exceptions.ApiError)
    assert issubclass(cro.exceptions.InvalidNonceError, cro.exceptions.ApiAuthError)


def test_error_message_fallback():
    err = cro.exceptions.api_error_from_response(306)
    assert "306" in str(err)
    with pytest.raises(cro.exceptions.NotEnoughBalanceError):
        raise cro.exceptions.api_error_from_response(306)
