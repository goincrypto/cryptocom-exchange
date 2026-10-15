import math

from .exceptions import ClientIdError

# Exchange contract for the client_oid field of an order.
CLIENT_ID_MAX_LENGTH = 36


def validate_client_id(client_id: str, param_name: str = "client_id") -> str:
    """Check *client_id* against the exchange client_oid contract.

    A client id must be a non-empty str of at most CLIENT_ID_MAX_LENGTH
    characters. Also validates IDs derived from a template: pass the
    LARGEST id the scheme can produce (e.g. ``f"{prefix}-buy-999999999"``)
    to prove the whole scheme fits before ever placing an order.

    Returns:
        The client_id unchanged, so it can be used inline.

    Raises:
        TypeError: If client_id is not a string.
        ClientIdError: If empty or longer than CLIENT_ID_MAX_LENGTH.
    """
    if not isinstance(client_id, str):
        raise TypeError(
            f"{param_name} must be a string, got {type(client_id).__name__}"
        )
    if not client_id:
        raise ClientIdError(f"{param_name} must not be empty")
    if len(client_id) > CLIENT_ID_MAX_LENGTH:
        raise ClientIdError(
            f"{param_name} must be <= {CLIENT_ID_MAX_LENGTH} characters, "
            f"got {len(client_id)}: {client_id!r}"
        )
    return client_id


def round_up(value: float | str, precision: int) -> float:
    """Rounds number to upper precision 0.13 -> 0.2

    A relative tolerance forgives scaling noise BEFORE ceiling: 0.29 * 100
    is 28.999999999999996 in IEEE-754, and a naked ceil-to-grid formatter
    can land a full step off on either side depending on the product.
    Genuine off-grid values are untouched: real fractions are
    >=1e-9-relative away from integers, noise is ~1e-16 relative.
    """
    value = float(value)
    pwr = math.pow(10, precision)
    scaled = value * pwr
    tol = 1e-9 * max(abs(scaled), 1.0)
    return math.ceil(scaled - tol) / pwr


def round_down(value: float | str, precision: int) -> float:
    """Rounds number to lower precision 0.13 -> 0.1

    Same relative tolerance as round_up, mirrored: round_down(0.29*100, 2)
    must return 29.0, not 28.99 (the scaled product is 2899.9999999999995
    naked). A value truly below the grid point stays below: the tolerance
    is ~1e-9 relative, real sub-grid amounts are far larger.
    """
    value = float(value)
    pwr = math.pow(10, precision)
    scaled = value * pwr
    tol = 1e-9 * max(abs(scaled), 1.0)
    return math.floor(scaled + tol) / pwr
