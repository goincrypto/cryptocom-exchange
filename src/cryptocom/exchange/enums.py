import enum


class Period(enum.IntEnum):
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
    BUY = 'BUY'
    SELL = 'SELL'


class OrderType(enum.IntEnum):
    LIMIT = 1
    MARKET = 2


class OrderStatus(enum.IntEnum):
    INIT = 0
    NEW = 1
    FILLED = 2
    PART_FILLED = 3
    CANCELED = 4
    PENDING_CANCEL = 5
    EXPIRED = 6


class Symbol(enum.Enum):
    CROBTC = 'crobtc'
    MCOBTC = 'mcobtc'
    ETHBTC = 'ethbtc'
    XRPBTC = 'xrpbtc'
    LTCBTC = 'ltcbtc'
    EOSBTC = 'eosbtc'
    XLMBTC = 'xlmbtc'
    BTCUSDT = 'btcusdt'
    CROUSDT = 'crousdt'
    MCOUSDT = 'mcousdt'
    ETHUSDT = 'ethusdt'
    XRPUSDT = 'xrpusdt'
    LTCUSDT = 'ltcusdt'
    EOSUSDT = 'eosusdt'
    XLMUSDT = 'xlmusdt'
    MCOCRO = 'mcocro'
    ETHCRO = 'ethcro'
    XRPCRO = 'xrpcro'
    LTCCRO = 'ltccro'
    EOSCRO = 'eoscro'
    XLMCRO = 'xlmcro'


class Depth(enum.Enum):
    HIGH = 'step0'
    MEDIUM = 'step1'
    LOW = 'step2'
