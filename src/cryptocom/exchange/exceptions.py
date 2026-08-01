"""
Crypto.com Exchange API Exception Codes

Official documentation:
https://exchange-developer.crypto.com/exchange/v1/docs/api/rest/introduction

All error codes from the Common API Reference.
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
