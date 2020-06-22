import enum


class OrderSide(enum.Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class OrderType(enum.Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'


class OrderStatus(enum.Enum):
    ACTIVE = 'ACTIVE'
    FILLED = 'FILLED'
    CANCELED = 'CANCELED'
    REJECTED = 'REJECTED'
    EXPIRED = 'EXPIRED'


class Coin(enum.Enum):
    BTC = 'BTC'
    CRO = 'CRO'
    MCO = 'MCO'
    ETH = 'ETH'
    XRP = 'XRP'
    LTC = 'LTC'
    EOS = 'EOS'
    XLM = 'XLM'
    ATO = 'ATOM'
    LINK = 'LINK'
    XTZ = 'XTZ'
    BCH = 'BCH'
    VET = 'VET'
    ICX = 'ICX'
    ADA = 'ADA'
    ENJ = 'ENJ'

    USDT = 'USDT'
    USDC = 'USDC'


class Pair(enum.Enum):
    CROBTC = 'CRO_BTC'
    MCOBTC = 'MCO_BTC'
    ETHBTC = 'ETH_BTC'
    XRPBTC = 'XRP_BTC'
    LTCBTC = 'LTC_BTC'
    EOSBTC = 'EOS_BTC'
    XLMBTC = 'XLM_BTC'
    ATOMBTC = 'ATOM_BTC'
    LINKBTC = 'LINK_BTC'
    XTZBTC = 'XTZ_BTC'
    BCHBTC = 'BCH_BTC'
    VETBTC = 'VET_BTC'
    ICXBTC = 'ICX_BTC'
    ADABTC = 'ADA_BTC'
    ENJBTC = 'ENJ_BTC'

    USDCUSDT = 'USDC_USDT'
    BTCUSDT = 'BTC_USDT'
    CROUSDT = 'CRO_USDT'
    MCOUSDT = 'MCO_USDT'
    ETHUSDT = 'ETH_USDT'
    XRPUSDT = 'XRP_USDT'
    LTCUSDT = 'LTC_USDT'
    EOSUSDT = 'EOS_USDT'
    XLMUSDT = 'XLM_USDT'
    ATOMUSDT = 'ATOM_USDT'
    LINKUSDT = 'LINK_USDT'
    XTZUSDT = 'XTZ_USDT'
    BCHUSDT = 'BCH_USDT'
    VETUSDT = 'VET_USDT'
    ICXUSDT = 'ICX_USDT'
    ADAUSDT = 'ADA_USDT'
    ENJUSDT = 'ENJ_USDT'

    MCOCRO = 'MCO_CRO'
    ETHCRO = 'ETH_CRO'
    XRPCRO = 'XRP_CRO'
    LTCCRO = 'LTC_CRO'
    EOSCRO = 'EOS_CRO'
    XLMCRO = 'XLM_CRO'
    ATOMCRO = 'ATOM_CRO'
    LINKCRO = 'LINK_CRO'
    XTZCRO = 'XTZ_CRO'
    BCHCRO = 'BCH_CRO'
    VETCRO = 'VET_CRO'
    ICXCRO = 'ICX_CRO'
    ADACRO = 'ADA_CRO'
    ENJCRO = 'ENJ_CRO'

    CROUSDC = 'CRO_USDC'
