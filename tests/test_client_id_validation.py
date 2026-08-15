"""Test client_id validation."""

import pytest
from cryptocom.exchange.account import Account


def test_validate_client_id_empty_string():
    """Test that empty string raises ValueError."""
    account = Account(api_key="test", api_secret="test")
    with pytest.raises(ValueError, match="cannot be empty"):
        account._validate_client_id("", "client_id")


def test_validate_client_id_too_long():
    """Test that client_id > 36 chars raises ValueError."""
    account = Account(api_key="test", api_secret="test")
    with pytest.raises(ValueError, match="<= 36 characters"):
        account._validate_client_id("a" * 37, "client_id")


def test_validate_client_id_non_string():
    """Test that non-string raises TypeError."""
    account = Account(api_key="test", api_secret="test")
    with pytest.raises(TypeError, match="must be a string"):
        account._validate_client_id(12345, "client_id")  # type: ignore


def test_validate_client_id_max_length():
    """Test that 36 char client_id is valid."""
    account = Account(api_key="test", api_secret="test")
    # Should not raise
    account._validate_client_id("a" * 36, "client_id")


def test_validate_client_id_short():
    """Test that short client_id is valid."""
    account = Account(api_key="test", api_secret="test")
    # Should not raise
    account._validate_client_id("short", "client_id")


def test_validate_client_id_none():
    """Test that None is valid (triggers auto-generation)."""
    account = Account(api_key="test", api_secret="test")
    # Should not raise
    account._validate_client_id(None, "client_id")


def test_validate_client_id_custom_param_name():
    """Test that custom param name appears in error messages."""
    account = Account(api_key="test", api_secret="test")
    
    with pytest.raises(ValueError, match="new_client_id cannot be empty"):
        account._validate_client_id("", "new_client_id")
    
    with pytest.raises(ValueError, match="orig_client_oid must be <= 36 characters"):
        account._validate_client_id("a" * 37, "orig_client_oid")
