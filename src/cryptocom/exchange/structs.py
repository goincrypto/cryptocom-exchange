import enum
import time

from typing import List, Dict
from dataclasses import dataclass

from cached_property import cached_property


class Coin(str, enum.Enum):
    BTC = 'BTC'
    CRO = 'CRO'
    MCO = 'MCO'
    ETH = 'ETH'
    XRP = 'XRP'
    LTC = 'LTC'
    EOS = 'EOS'
    XLM = 'XLM'
    ATOM = 'ATOM'
    LINK = 'LINK'
    XTZ = 'XTZ'
    BCH = 'BCH'
    VET = 'VET'
    ICX = 'ICX'
    ADA = 'ADA'
    ENJ = 'ENJ'
    ALGO = 'ALGO'
    KNC = 'KNC'
    NEO = 'NEO'
    PAXG = 'PAXG'
    BAT = 'BAT'
    COMP = 'COMP'
    MANA = 'MANA'
    OMG = 'OMG'

    ETC = 'ETC'

    USDT = 'USDT'
    USDC = 'USDC'
    DAI = 'DAI'


class Pair(str, enum.Enum):
    CRO_BTC = 'CRO_BTC'
    MCO_BTC = 'MCO_BTC'
    ETH_BTC = 'ETH_BTC'
    XRP_BTC = 'XRP_BTC'
    LTC_BTC = 'LTC_BTC'
    EOS_BTC = 'EOS_BTC'
    XLM_BTC = 'XLM_BTC'
    ATOM_BTC = 'ATOM_BTC'
    LINK_BTC = 'LINK_BTC'
    XTZ_BTC = 'XTZ_BTC'
    BCH_BTC = 'BCH_BTC'
    VET_BTC = 'VET_BTC'
    ICX_BTC = 'ICX_BTC'
    ADA_BTC = 'ADA_BTC'
    ALGO_BTC = 'ALGO_BTC'
    NEO_BTC = 'NEO_BTC'
    COMP_BTC = 'COMP_BTC'
    OMG_BTC = 'OMG_BTC'
    MANA_BTC = 'MANA_BTC'

    USDC_USDT = 'USDC_USDT'
    BTC_USDT = 'BTC_USDT'
    CRO_USDT = 'CRO_USDT'
    MCO_USDT = 'MCO_USDT'
    ETH_USDT = 'ETH_USDT'
    XRP_USDT = 'XRP_USDT'
    LTC_USDT = 'LTC_USDT'
    EOS_USDT = 'EOS_USDT'
    XLM_USDT = 'XLM_USDT'
    ATOM_USDT = 'ATOM_USDT'
    LINK_USDT = 'LINK_USDT'
    XTZ_USDT = 'XTZ_USDT'
    BCH_USDT = 'BCH_USDT'
    VET_USDT = 'VET_USDT'
    ICX_USDT = 'ICX_USDT'
    ADA_USDT = 'ADA_USDT'
    ENJ_USDT = 'ENJ_USDT'
    ALGO_USDT = 'ALGO_USDT'
    KNC_USDT = 'KNC_USDT'
    NEO_USDT = 'NEO_USDT'
    DAI_USDT = 'DAI_USDT'
    PAXG_USDT = 'PAXG_USDT'
    BAT_USDT = 'BAT_USDT'
    COMP_USDT = 'COMP_USDT'
    OMG_USDT = 'OMG_USDT'
    MANA_USDT = 'MANA_USDT'

    MCO_CRO = 'MCO_CRO'
    ETH_CRO = 'ETH_CRO'
    XRP_CRO = 'XRP_CRO'
    LTC_CRO = 'LTC_CRO'
    EOS_CRO = 'EOS_CRO'
    XLM_CRO = 'XLM_CRO'
    ATOM_CRO = 'ATOM_CRO'
    LINK_CRO = 'LINK_CRO'
    XTZ_CRO = 'XTZ_CRO'
    BCH_CRO = 'BCH_CRO'
    VET_CRO = 'VET_CRO'
    ICX_CRO = 'ICX_CRO'
    ADA_CRO = 'ADA_CRO'
    ENJ_CRO = 'ENJ_CRO'
    ALGO_CRO = 'ALGO_CRO'
    KNC_CRO = 'KNC_CRO'
    NEO_CRO = 'NEO_CRO'
    DAI_CRO = 'DAI_CRO'
    PAXG_CRO = 'PAXG_CRO'
    BAT_CRO = 'BAT_CRO'
    COMP_CRO = 'COMP_CRO'
    OMG_CRO = 'OMG_CRO'
    MANA_CRO = 'MANA_CRO'

    CRO_USDC = 'CRO_USDC'


class Period(str, enum.Enum):
    MINS = '1m'
    MINS_5 = '5m'
    MINS_15 = '15m'
    MINS_30 = '30m'
    HOURS = '1h'
    HOURS_4 = '4h'
    HOURS_6 = '6h'
    HOURS_12 = '12h'
    DAY = '1D'
    WEEK = '7D'
    WEEK_2 = '14D'
    MONTH_1 = '1M'


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    pair: Pair


class OrderSide(str, enum.Enum):
    BUY = 'BUY'
    SELL = 'SELL'


@dataclass
class MarketTrade:
    id: int
    time: int
    price: float
    quantity: float
    side: OrderSide
    pair: Pair


@dataclass
class OrderInBook:
    price: float
    quantity: float
    count: int
    side: OrderSide

    @property
    def volume(self) -> float:
        return self.price * self.quantity


@dataclass
class OrderBook:
    buys: List[OrderInBook]
    sells: List[OrderInBook]
    pair: Pair

    @property
    def spread(self) -> float:
        return (self.sells[0].price / self.buys[0].price - 1) * 100


@dataclass
class Balance:
    total: float
    available: float
    in_orders: float
    in_stake: float
    coin: Coin


class OrderType(str, enum.Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'


class OrderStatus(str, enum.Enum):
    ACTIVE = 'ACTIVE'
    FILLED = 'FILLED'
    CANCELED = 'CANCELED'
    REJECTED = 'REJECTED'
    EXPIRED = 'EXPIRED'


class OrderExecType(str, enum.Enum):
    POST_ONLY = 'POST_ONLY'


class OrderForceType(str, enum.Enum):
    GOOD_TILL_CANCEL = 'GOOD_TILL_CANCEL'
    FILL_OR_KILL = 'FILL_OR_KILL'
    IMMEDIATE_OR_CANCEL = 'IMMEDIATE_OR_CANCEL'


@dataclass
class Order:
    id: int
    status: OrderStatus
    side: OrderSide
    price: float
    quantity: float
    client_id: str
    created_at: int
    updated_at: int
    type: OrderType
    pair: Pair
    filled_quantity: float
    filled_price: float
    fees_coin: Coin
    force_type: OrderForceType

    @cached_property
    def is_buy(self):
        return self.side == OrderSide.BUY

    @cached_property
    def is_sell(self):
        return self.side == OrderSide.SELL

    @cached_property
    def is_active(self):
        return self.side == OrderStatus.ACTIVE

    @cached_property
    def is_canceled(self):
        return self.status == OrderStatus.CANCELED

    @cached_property
    def is_rejected(self):
        return self.status == OrderStatus.REJECTED

    @cached_property
    def is_expired(self):
        return self.status == OrderStatus.EXPIRED

    @cached_property
    def is_filled(self):
        return self.status == OrderStatus.FILLED

    @cached_property
    def volume(self):
        return self.price * self.quantity

    @cached_property
    def filled_volume(self):
        return self.filled_price * self.filled_quantity

    @cached_property
    def remain_volume(self):
        return self.filled_volume - self.volume

    @cached_property
    def remain_quantity(self):
        return self.quantity - self.filled_quantity

    @classmethod
    def create_from_api(cls, data: dict) -> 'Order':
        fees_coin = None
        if data['fee_currency']:
            fees_coin = Coin(data['fee_currency'])

        return cls(
            id=int(data['order_id']),
            status=OrderStatus(data['status']),
            side=OrderSide(data['side']),
            price=data['price'],
            quantity=data['quantity'],
            client_id=data['client_oid'],
            created_at=int(data['create_time'] / 1000),
            updated_at=int(data['update_time'] / 1000),
            type=OrderType(data['type']),
            pair=Pair(data['instrument_name']),
            filled_quantity=data['cumulative_quantity'],
            filled_price=data['avg_price'],
            fees_coin=fees_coin,
            force_type=OrderForceType(data['time_in_force'])
        )


@dataclass
class PrivateTrade:
    id: int
    side: OrderSide
    pair: Pair
    fees: float
    fees_coin: Coin
    created_at: int
    filled_price: float
    filled_quantity: float
    order_id: int

    @cached_property
    def is_buy(self):
        return self.side == OrderSide.BUY

    @cached_property
    def is_sell(self):
        return self.side == OrderSide.SELL

    @classmethod
    def create_from_api(cls, data: dict) -> 'PrivateTrade':
        return cls(
            id=int(data['trade_id']),
            side=OrderSide(data['side']),
            pair=Pair(data['instrument_name']),
            fees=data['fee'],
            fees_coin=Coin(data['fee_currency']),
            created_at=int(data['create_time'] / 1000),
            filled_price=data['traded_price'],
            filled_quantity=data['traded_quantity'],
            order_id=int(data['order_id'])
        )
