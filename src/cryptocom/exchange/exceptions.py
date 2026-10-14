"""
Crypto.com Exchange API Exception Codes and Typed Exceptions

Official documentation:
https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction

All error codes from the Common API Reference.

Exception design
----------------
- ``ApiError`` is the base for everything. ``code is None`` means the
  outcome is INDETERMINATE (transport error, timeout, malformed reply):
  the caller must NOT assume the operation did or did not happen and
  should reconcile against persisted state + a fresh query.
- ``ExchangeError`` and subclasses are DETERMINISTIC business errors:
  the API explicitly rejected the request with a known code, so the
  outcome is known (order was not found, balance insufficient, ...).
- Each class maps one-to-one to a documented ``ApiErrorCode`` family.
  Unknown codes raise the generic ``ExchangeError`` with the code set.
"""

from enum import Enum


class ApiErrorCode(Enum):
    """
    API error codes from Crypto.com Exchange.

    Source: https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction
    """

    # === SUCCESS ===
    SUCCESS = 0  # Success

    # === 200 OK (Success responses with error codes) ===
    NOT_FOUND = 40401  # Not found
    SELF_TRADE_PREVENTION = 43012  # Canceled due to Self Trade Prevention

    # === 400 Bad Request ===
    ACCOUNT_IS_SUSPENDED = 202  # Account is suspended
    DUPLICATE_CLORDID = 204  # Duplicate client order id
    NO_MARK_PRICE = 207  # No mark price
    INSTRUMENT_NOT_TRADABLE = 208  # Instrument is not tradable
    INVALID_INSTRUMENT = 209  # Instrument is invalid
    INVALID_ORDERQTY = 213  # Invalid order quantity
    INVALID_ORDTYPE = 218  # Invalid order_type
    INVALID_SIDE = 220  # Invalid side
    INVALID_TIF = 221  # Invalid time_in_force
    STALE_MARK_PRICE = 222  # Stale mark price
    NO_CLORDID = 223  # No client order id
    REJ_BY_MATCHING_ENGINE = 224  # Rejected by matching engine
    EXCEED_MAXIMUM_ENTRY_LEVERAGE = 225  # Exceeds maximum entry leverage
    INVALID_LEVERAGE = 226  # Invalid leverage
    INVALID_SLIPPAGE = 227  # Invalid slippage
    INVALID_FLOOR_PRICE = 228  # Invalid floor price
    INVALID_REF_PRICE = 229  # Invalid ref price
    INVALID_REF_PRICE_TYPE = 230  # Invalid ref price type
    INVALID_PRICE = 308  # Invalid price
    EXCEEDS_MAX_ORDER_SIZE = 314  # Exceeds max order size
    FAR_AWAY_LIMIT_PRICE = 315  # Far away limit price
    EXCEEDS_MAX_ALLOWED_ORDERS = 318  # Exceeds max allowed orders
    EXCEEDS_MAX_POSITION_SIZE = 319  # Exceeds max position size
    ACCOUNT_DOES_NOT_EXIST = 401  # Account does not exist
    MARGIN_UNIT_IS_SUSPENDED = 408  # Margin unit is suspended
    MAX_AMOUNT_VIOLATED = (
        30024  # If create-withdrawal call quantity > max_withdrawal_balance
    )
    BAD_REQUEST = 40001  # Bad request
    METHOD_NOT_FOUND = 40002  # Method not found
    INVALID_REQUEST = 40003  # Invalid request
    MISSING_OR_INVALID_ARGUMENT = 40004  # Required argument is blank or missing
    INVALID_DATE = 40005  # Invalid date
    DUPLICATE_REQUEST = 40006  # Duplicate request received
    INVALID_NONCE = 40102  # Nonce value differs by more than 60 seconds
    EXCEED_MAX_SUBSCRIPTIONS = 40107  # Session subscription limit has been exceeded
    ERR_INTERNAL = 50001  # Internal error
    DW_CREDIT_LINE_NOT_MAINTAINED = (
        50002  # If create-withdrawal call breaches credit line check
    )
    REDUCE_ONLY_REJECTED = 1110  # Rejected REDUCE_ONLY create-order request
    MAINTENANCE = 9010001  # Crypto.com Exchange is under maintenance
    INSUFFICIENT_FUNDS = 20002  # Insufficient funds (fiat/withdraw flows)
    EXCEED_DAILY_VOL_LIMIT = 325  # Exceeds daily volume limit

    # === 401 Unauthorized ===
    UNAUTHORIZED = 40101  # Not authenticated, or key/signature incorrect
    IP_ILLEGAL = 40103  # IP address not whitelisted
    USER_TIER_INVALID = 40104  # Disallowed based on user tier

    # === 408 Request Timeout ===
    REQUEST_TIMEOUT = 40801  # Request has timed out

    # === 429 Too Many Requests ===
    TOO_MANY_REQUESTS = 42901  # Requests have exceeded rate limits

    # === 500 Internal Server Error ===
    NO_POSITION = 201  # No position
    ACCOUNTS_DO_NOT_MATCH = 203  # Accounts do not match
    DUPLICATE_ORDERID = 205  # Duplicate order id
    INSTRUMENT_EXPIRED = 206  # Instrument has expired
    INVALID_ACCOUNT = 210  # Account is invalid
    INVALID_CURRENCY = 211  # Currency is invalid
    INVALID_ORDERID = 212  # Invalid order id
    INVALID_SETTLE_CURRENCY = 214  # Invalid settlement currency
    INVALID_FEE_CURRENCY = 215  # Invalid fee currency
    INVALID_POSITION_QTY = 216  # Invalid position quantity
    INVALID_OPEN_QTY = 217  # Invalid open quantity
    INVALID_EXECINST = 219  # Invalid exec_inst
    ACCOUNT_IS_IN_MARGIN_CALL = 301  # Account is in margin call
    EXCEEDS_ACCOUNT_RISK_LIMIT = 302  # Exceeds account risk limit
    EXCEEDS_POSITION_RISK_LIMIT = 303  # Exceeds position risk limit
    ORDER_WILL_LEAD_TO_IMMEDIATE_LIQUIDATION = (
        304  # Order will lead to immediate liquidation
    )
    ORDER_WILL_TRIGGER_MARGIN_CALL = 305  # Order will trigger margin call
    INSUFFICIENT_AVAILABLE_BALANCE = 306  # Insufficient available balance
    INVALID_ORDSTATUS = 307  # Invalid order status
    MARKET_IS_NOT_OPEN = 309  # Market is not open
    ORDER_PRICE_BEYOND_LIQUIDATION_PRICE = 310  # Order price beyond liquidation price
    POSITION_IS_IN_LIQUIDATION = 311  # Position is in liquidation
    ORDER_PRICE_GREATER_THAN_LIMITUPPRICE = (
        312  # Order price is greater than the limit up price
    )
    ORDER_PRICE_LESS_THAN_LIMITDOWNPRICE = (
        313  # Order price is less than the limit down price
    )
    NO_ACTIVE_ORDER = 316  # No active order
    POSITION_NO_EXIST = 317  # Position does not exist
    EXCEEDS_INITIAL_MARGIN = 320  # Exceeds initial margin
    EXCEEDS_MAX_AVAILABLE_BALANCE = 321  # Exceeds maximum available balance
    ACCOUNT_IS_NOT_ACTIVE = 406  # Account is not active
    MARGIN_UNIT_DOES_NOT_EXIST = 407  # Margin unit does not exist
    INVALID_USER = 409  # Invalid user
    USER_IS_NOT_ACTIVE = 410  # User is not active
    USER_NO_DERIV_ACCESS = 411  # User does not have derivative access
    ACCOUNT_NO_DERIV_ACCESS = 412  # Account does not have derivative access
    BELOW_MIN_ORDER_SIZE = 415  # Below Min. Order Size
    EXCEED_MAXIMUM_EFFECTIVE_LEVERAGE = 501  # Exceeds maximum effective leverage
    INVALID_COLLATERAL_PRICE = 604  # Invalid collateral price
    INVALID_MARGIN_CALC = 605  # Invalid margin calculation
    EXCEED_ALLOWED_SLIPPAGE = 606  # Exceed allowed slippage
    INVALID_ISOLATION_ID = 613  # Invalid isolation ID
    EXCEEDS_ISOLATED_POSITION_LIMIT = (
        614  # Exceeds maximum allowed number of isolated position
    )
    ACCOUNT_DOES_NOT_SUPPORT_ISOLATED_POSITION = (
        615  # Account does not support isolated position
    )
    CREATE_ISOLATED_POSITION_FAILED = 616  # Failed to create isolated position
    DUPLICATED_INSTRUMENT_ORDER_FOR_ISOLATED_MARGIN = (
        617  # Account already have isolated position with same instrument
    )
    TOO_MANY_PENDING_ISOLATED_MARGIN_REQUESTS = (
        618  # Exceeds request limit for isolated margin order
    )
    UNSUPPORTED_OPERATION_ON_ISOLATED_POSITION = (
        619  # Unsupported operation on isolated position
    )
    CREATE_ISOLATED_POSITION_TIMEOUT = (
        620  # Request for create isolated position has timed out
    )
    FILL_OR_KILL = 43003  # FOK order has not been filled and cancelled
    IMMEDIATE_OR_CANCEL = 43004  # IOC order has not been filled and cancelled
    POST_ONLY_REJ = 43005  # Rejected POST_ONLY create-order request
    REJECTED = 120009  # Request rejected by upstream service
    NON_APPLICABLE = 130008  # Operation not applicable for current state


# HTTP Status Code mappings
HTTP_STATUS_CODES = {
    200: "OK",
    400: "Bad Request",
    401: "Unauthorized",
    408: "Request Timeout",
    429: "Too Many Requests",
    500: "Internal Server Error",
}

# WebSocket termination codes
WS_TERMINATION_CODES = {
    1000: "Normal disconnection by server (heartbeat not handled properly)",
    1006: "Abnormal disconnection",
    1013: "Server restarting -- try again later",
}


# =============================================================================
# Typed exceptions
# =============================================================================


class ApiError(Exception):
    """Base API error.

    ``code`` is the Crypto.com API error code when the exchange responded
    with a structured error. ``code is None`` marks an INDETERMINATE
    outcome (transport failure, timeout, protocol error): the caller must
    re-query to learn whether the operation actually happened.

    ``method`` is the API method (e.g. ``private/create-order``) when known.
    """

    code: int | None = None

    def __init__(self, *args, code: int | None = None, method: str | None = None):
        super().__init__(*args)
        if code is not None:
            self.code = code
        self.method = method

    @property
    def is_indeterminate(self) -> bool:
        """True when the outcome of the operation is unknown."""
        return self.code is None


class ApiAuthError(ApiError):
    """Authentication/authorization failure (HTTP 401/400, codes 401xx)."""


class ExchangeError(ApiError):
    """Deterministic business error returned by the API (known code)."""


class BadRequestError(ExchangeError):
    """Malformed or invalid request (40001-40007 and friends)."""


class PermissionDeniedError(ExchangeError):
    """Operation not allowed for this account/tier/IP."""


class InvalidNonceError(ApiAuthError):
    """Nonce too old or reused (codes 40102, 10007)."""


class OrderNotFoundError(ExchangeError):
    """The referenced order does not exist (code 40401 / invalid order id).

    CONFIRMED absence - safe to treat the order as gone (as opposed to an
    indeterminate ApiError, which only means the answer is unknown).
    """


class NotEnoughBalanceError(ExchangeError):
    """Insufficient available balance for the requested operation."""


class InvalidOrderError(ExchangeError):
    """Order rejected for a parameter/limit reason (size, price, side, ...)."""


class FillOrKillRejectedError(InvalidOrderError):
    """FOK order did not fill completely and was cancelled (code 43003)."""


class ImmediateOrCancelRejectedError(InvalidOrderError):
    """IOC order residual was cancelled (code 43004)."""


class PostOnlyRejectedError(InvalidOrderError):
    """POST_ONLY order would have crossed (code 43005)."""


class OrderNotActiveError(ExchangeError):
    """Target order is not active (already filled/canceled/expired), code 316.

    Typical when amending/cancelling based on a stale cached status - the
    caller must re-query the order to learn its real terminal status.
    """


class DuplicateClientIdError(ExchangeError):
    """client_oid already used (code 204) - an order with that id EXISTS."""


class DuplicateOrderIdError(ExchangeError):
    """order_id already exists (code 205)."""


class InvalidInstrumentError(ExchangeError):
    """Instrument unknown, expired, or not tradable."""


class OrderLimitExceededError(ExchangeError):
    """Too many open orders / position size limits (codes 318, 319)."""


class AccountSuspendedError(ExchangeError):
    """Account is suspended or not active (codes 202, 406)."""


class SelfTradePreventionError(ExchangeError):
    """Order cancelled by self-trade prevention (code 43012)."""


class RateLimitExceededError(ExchangeError):
    """Rate limit hit (codes 42901, 10006). Transient."""


class RequestTimeoutError(ExchangeError):
    """API reported request timeout (code 40801). Transient.

    INDETERMINATE despite the known code: a timeout means the exchange
    may have processed the request - the caller must reconcile, never
    assume "did not happen".
    """

    @property
    def is_indeterminate(self) -> bool:
        return True


class InternalError(ExchangeError):
    """Exchange-side internal/system error (codes 50001, 120009). Transient.

    INDETERMINATE: the backend may have partially processed the request.
    """

    @property
    def is_indeterminate(self) -> bool:
        return True


class MaintenanceError(ExchangeError):
    """Exchange under maintenance (code 9010001). Transient."""


class WaitNotConfirmedError(ApiError):
    """An order did not reach a required status before the timeout.

    Indeterminate (code is None): the transition may happen after the
    last poll - reconcile later, never assume the negative.
    """


# Code -> exception class. Deterministic codes not listed here fall back to
# the generic ExchangeError (still NOT retried - unknown code != transient).
# Auth-family codes (InvalidNonceError) ride along: they are ApiErrors whose
# indeterminate status is the SAFE reading of an auth-time rejection.
_ERROR_CODE_CLASSES: dict[int, type[ApiError]] = {
    40401: OrderNotFoundError,
    212: OrderNotFoundError,
    306: NotEnoughBalanceError,
    321: NotEnoughBalanceError,
    20002: NotEnoughBalanceError,
    316: OrderNotActiveError,
    204: DuplicateClientIdError,
    205: DuplicateOrderIdError,
    206: InvalidInstrumentError,
    208: InvalidInstrumentError,
    209: InvalidInstrumentError,
    30003: InvalidInstrumentError,
    318: OrderLimitExceededError,
    319: OrderLimitExceededError,
    202: AccountSuspendedError,
    406: AccountSuspendedError,
    43003: FillOrKillRejectedError,
    43004: ImmediateOrCancelRejectedError,
    43005: PostOnlyRejectedError,
    43012: SelfTradePreventionError,
    42901: RateLimitExceededError,
    10006: RateLimitExceededError,
    40801: RequestTimeoutError,
    50001: InternalError,
    120009: InternalError,
    9010001: MaintenanceError,
    40102: InvalidNonceError,
    10007: InvalidNonceError,
    10002: PermissionDeniedError,
    10003: PermissionDeniedError,
    10005: PermissionDeniedError,
    40104: PermissionDeniedError,
    40001: BadRequestError,
    40002: BadRequestError,
    40003: BadRequestError,
    40004: BadRequestError,
    40005: BadRequestError,
    40006: BadRequestError,
    40007: BadRequestError,
    10004: BadRequestError,
    213: InvalidOrderError,
    217: InvalidOrderError,
    218: InvalidOrderError,
    219: InvalidOrderError,
    220: InvalidOrderError,
    221: InvalidOrderError,
    223: InvalidOrderError,
    224: InvalidOrderError,
    308: InvalidOrderError,
    310: InvalidOrderError,
    312: InvalidOrderError,
    313: InvalidOrderError,
    314: InvalidOrderError,
    315: InvalidOrderError,
    325: InvalidOrderError,
    415: InvalidOrderError,
    1110: InvalidOrderError,
    30006: InvalidOrderError,
    30007: InvalidOrderError,
    30008: InvalidOrderError,
    30009: InvalidOrderError,
    30013: InvalidOrderError,
    30014: InvalidOrderError,
    30016: InvalidOrderError,
    30017: InvalidOrderError,
    30023: InvalidOrderError,
    30024: InvalidOrderError,
    30025: InvalidOrderError,
}

# Codes worth retrying (transient by nature). Everything else raises at once
# - retrying a deterministic rejection wastes rate-limit and hides bugs.
RETRYABLE_ERROR_CODES = frozenset(
    {
        40801,  # request timeout
        42901,  # rate limit
        10006,  # ddos protection
        50001,  # internal error
        120009,  # rejected by upstream service
        9010001,  # maintenance
    }
)


def is_retryable_error_code(code: int) -> bool:
    """Whether an API error code is transient and worth retrying."""
    return code in RETRYABLE_ERROR_CODES


def api_error_from_response(
    code: int, message: str | None = None, method: str | None = None
) -> ApiError:
    """Build the typed exception for an API error code + message."""
    message = str(message or f"API error {code}")
    cls = _ERROR_CODE_CLASSES.get(code, ExchangeError)
    return cls(message, code=code, method=method)
