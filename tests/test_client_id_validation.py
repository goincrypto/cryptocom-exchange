"""helpers.validate_client_id: the client_oid contract in one place.

The exchange accepts client order ids of 1-36 characters. The check lives
in the plain-function helpers module (exch.helpers.validate_client_id) -
detached from any class, used by Account before placing or amending, and
callable by anyone validating a DERIVED id scheme (e.g.
"<prefix>-buy-<counter>") before the first request is ever sent.
"""

import pytest

from cryptocom.exchange.exceptions import ClientIdError
from cryptocom.exchange.helpers import CLIENT_ID_MAX_LENGTH, validate_client_id


def test_accepts_max_length_id():
    assert validate_client_id("a" * CLIENT_ID_MAX_LENGTH) == ("a" * 36)


def test_accepts_short_id():
    assert validate_client_id("b1-buy-1") == "b1-buy-1"


def test_rejects_empty_id():
    with pytest.raises(ClientIdError, match="must not be empty"):
        validate_client_id("")


def test_rejects_too_long_id_and_names_the_id():
    too_long = "x" * 37
    with pytest.raises(ClientIdError, match="<= 36 characters") as exc_info:
        validate_client_id(too_long)
    assert repr(too_long) in str(exc_info.value)


def test_rejects_non_string():
    with pytest.raises(TypeError, match="must be a string"):
        validate_client_id(12345)  # type: ignore[arg-type]


def test_param_name_appears_in_error():
    with pytest.raises(ClientIdError, match="bucket id 'toolongbucketname'"):
        validate_client_id(
            "toolongbucketname-buy-999999999999999",
            "bucket id 'toolongbucketname' (counter-based client ids)",
        )


def test_validates_derived_counter_schemes_at_their_largest_id():
    """The bucket pattern: f"{id}-buy-<n>" must fit for EVERY counter."""
    prefix = "b" * (CLIENT_ID_MAX_LENGTH - len("-sell-999999999"))
    validate_client_id(f"{prefix}-sell-999999999")  # fits exactly
    with pytest.raises(ClientIdError):
        validate_client_id(f"{prefix}x-sell-999999999")


def test_client_id_error_is_a_value_error():
    """Back-compat: existing `except ValueError` sites keep working."""
    assert issubclass(ClientIdError, ValueError)
