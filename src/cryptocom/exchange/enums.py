import enum


class Period(enum.IntEnum):
    """
    Candles time period.

    MIN - minutes H - hours D - days M - month W - weeks

    .. data:: MIN1
    .. data:: MIN5
    .. data:: MIN15
    .. data:: MIN30
    .. data:: H1
    .. data:: D1
    .. data:: W1
    .. data:: M1
    """

    MIN1 = 1
    MIN5 = MIN1 * 5
    MIN15 = MIN5 * 3
    MIN30 = MIN15 * 2
    H1 = MIN30 * 2
    D1 = H1 * 24
    W1 = D1 * 7
    M1 = W1 * 4


class PeriodWebSocket(enum.Enum):
    MIN1 = '1min'
    MIN5 = '5min'
    MIN15 = '15min'
    MIN30 = '30min'
    H1 = '60min'
    D1 = '1day'
    W1 = '1week'
    M1 = '1month'


class OrderSide(enum.Enum):
    """
    .. data:: BUY
    .. data:: SELL
    """
    BUY = 'BUY'
    SELL = 'SELL'


class OrderType(enum.IntEnum):
    """
    .. data:: LIMIT
    .. data:: MARKET
    """
    LIMIT = 1
    MARKET = 2


class OrderStatus(enum.IntEnum):
    """
    .. data:: INIT
    .. data:: NEW
    .. data:: FILLED
    .. data:: PART_FILLED
    .. data:: CANCELED
    .. data:: PENDING_CANCEL
    .. data:: EXPIRED
    """

    INIT = 0
    NEW = 1
    FILLED = 2
    PART_FILLED = 3
    CANCELED = 4
    PENDING_CANCEL = 5
    EXPIRED = 6


class Symbol(enum.Enum):
    """
    .. data:: CROBTC
    .. data:: MCOBTC
    .. data:: ETHBTC
    .. data:: XRPBTC
    .. data:: LTCBTC
    .. data:: EOSBTC
    .. data:: XLMBTC
    .. data:: ATOMBTC
    .. data:: LINKBTC
    .. data:: XTZBTC
    .. data:: BCHBTC
    .. data:: VETBTC
    .. data:: ICXBTC

    .. data:: USDCUSDT
    .. data:: BTCUSDT
    .. data:: CROUSDT
    .. data:: MCOUSDT
    .. data:: ETHUSDT
    .. data:: XRPUSDT
    .. data:: LTCUSDT
    .. data:: EOSUSDT
    .. data:: XLMUSDT
    .. data:: ATOMUSDT
    .. data:: LINKUSDT
    .. data:: XTZUSDT
    .. data:: BCHUSDT
    .. data:: VETUSDT
    .. data:: ICXUSDT

    .. data:: MCOCRO
    .. data:: ETHCRO
    .. data:: XRPCRO
    .. data:: LTCCRO
    .. data:: EOSCRO
    .. data:: XLMCRO
    .. data:: ATOMCRO
    .. data:: LINKCRO
    .. data:: XTZCRO
    .. data:: BCHCRO
    .. data:: VETCRO
    .. data:: ICXCRO

    .. data:: CROUSDC
    """

    CROBTC = 'crobtc'
    MCOBTC = 'mcobtc'
    ETHBTC = 'ethbtc'
    XRPBTC = 'xrpbtc'
    LTCBTC = 'ltcbtc'
    EOSBTC = 'eosbtc'
    XLMBTC = 'xlmbtc'
    ATOMBTC = 'atombtc'
    LINKBTC = 'linkbtc'
    XTZBTC = 'xtzbtc'
    BCHBTC = 'bchbtc'
    VETBTC = 'vetbtc'
    ICXBTC = 'icxbtc'

    USDCUSDT = 'usdcusdt'
    BTCUSDT = 'btcusdt'
    CROUSDT = 'crousdt'
    MCOUSDT = 'mcousdt'
    ETHUSDT = 'ethusdt'
    XRPUSDT = 'xrpusdt'
    LTCUSDT = 'ltcusdt'
    EOSUSDT = 'eosusdt'
    XLMUSDT = 'xlmusdt'
    ATOMUSDT = 'atomusdt'
    LINKUSDT = 'linkusdt'
    XTZUSDT = 'xtzusdt'
    BCHUSDT = 'bchusdt'
    VETUSDT = 'vetusdt'
    ICXUSDT = 'icxusdt'

    MCOCRO = 'mcocro'
    ETHCRO = 'ethcro'
    XRPCRO = 'xrpcro'
    LTCCRO = 'ltccro'
    EOSCRO = 'eoscro'
    XLMCRO = 'xlmcro'
    ATOMCRO = 'atomcro'
    LINKCRO = 'linkcro'
    XTZCRO = 'xtzcro'
    BCHCRO = 'bchcro'
    VETCRO = 'vetcro'
    ICXCRO = 'icxcro'

    CROUSDC = 'crousdc'


class Depth(enum.Enum):
    """
    Order-book depth, for example 2, 4, 6 decimals - [low, medium, high].

    .. data:: HIGH
    .. data:: MEDIUM
    .. data:: LOW
    """

    HIGH = 'step0'
    MEDIUM = 'step1'
    LOW = 'step2'
