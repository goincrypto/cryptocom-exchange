import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum
from typing import Dict, List

from cached_property import cached_property

from .helpers import round_down, round_up


@dataclass
class Coin:
    exchange_name: str

    @property
    def name(self):
        return self.exchange_name.replace("1", "ONE")

    def __hash__(self):
        return self.name.__hash__()


@dataclass
class Pair:
    exchange_name: str
    price_precision: int
    quantity_precision: int

    @property
    def name(self):
        return self.exchange_name.replace("1", "ONE")

    @cached_property
    def base_coin(self) -> Coin:
        return Coin(self.name.split("_")[0])

    @cached_property
    def quote_coin(self) -> Coin:
        return Coin(self.name.split("_")[1])

    def round_price(self, price):
        return round_down(price, self.price_precision)

    def round_quantity(self, quantity):
        return round_down(quantity, self.quantity_precision)

    def __hash__(self):
        return self.name.__hash__()


@dataclass
class MarketTicker:
    pair: Pair
    buy_price: float
    sell_price: float
    trade_price: float
    time: int
    volume: float
    high: float
    low: float
    change: float

    @classmethod
    def from_api(cls, pair, data):
        return cls(
            pair=pair,
            buy_price=pair.round_price(data["b"]),
            sell_price=pair.round_price(data["k"]),
            trade_price=pair.round_price(data["a"]),
            time=int(data["t"] / 1000),
            volume=pair.round_quantity(data["v"]),
            high=pair.round_price(data["h"]),
            low=pair.round_price(data["l"]),
            change=round_down(data["c"], 3),
        )


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class MarketTrade:
    id: int
    time: int
    price: float
    quantity: float
    side: OrderSide
    pair: Pair

    @classmethod
    def from_api(cls, pair: Pair, data: Dict):
        return cls(
            id=data["d"],
            time=int(data["t"] / 1000),
            price=pair.round_price(data["p"]),
            quantity=pair.round_quantity(data["q"]),
            side=OrderSide(data["s"].upper()),
            pair=pair,
        )


class Period(str, Enum):
    MINS = "1m"
    MINS_5 = "5m"
    MINS_15 = "15m"
    MINS_30 = "30m"
    HOURS = "1h"
    HOURS_4 = "4h"
    HOURS_6 = "6h"
    HOURS_12 = "12h"
    DAY = "1D"
    WEEK = "7D"
    WEEK_2 = "14D"
    MONTH_1 = "1M"


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    pair: Pair

    @classmethod
    def from_api(cls, pair: Pair, data: Dict):
        return cls(
            time=int(data["t"] / 1000),
            open=pair.round_price(data["o"]),
            high=pair.round_price(data["h"]),
            low=pair.round_price(data["l"]),
            close=pair.round_price(data["c"]),
            volume=pair.round_quantity(data["v"]),
            pair=pair,
        )


@dataclass
class OrderInBook:
    price: float
    quantity: float
    count: int
    pair: Pair
    side: OrderSide

    @property
    def volume(self) -> float:
        return self.pair.round_quantity(self.price * self.quantity)


@dataclass
class OrderBook:
    buys: List[OrderInBook]
    sells: List[OrderInBook]
    pair: Pair

    @property
    def spread(self) -> float:
        return round_down(self.sells[-1].price / self.buys[0].price - 1, 6)


@dataclass
class Balance:
    total: float
    available: float
    in_orders: float
    in_stake: float
    coin: Coin

    @classmethod
    def from_api(cls, data):
        return cls(
            total=data["balance"],
            available=data["available"],
            in_orders=data["order"],
            in_stake=data["stake"],
            coin=Coin(data["currency"]),
        )


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"


class OrderStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"


class OrderExecType(str, Enum):
    MARKET = ""
    POST_ONLY = "POST_ONLY"


class OrderForceType(str, Enum):
    GOOD_TILL_CANCEL = "GOOD_TILL_CANCEL"
    FILL_OR_KILL = "FILL_OR_KILL"
    IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"


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
    def create_from_api(cls, pair: Pair, data: Dict) -> "PrivateTrade":
        return cls(
            id=int(data["trade_id"]),
            side=OrderSide(data["side"]),
            pair=pair,
            fees=round_up(data["fee"], 8),
            fees_coin=Coin(data["fee_currency"]),
            created_at=int(data["create_time"] / 1000),
            filled_price=pair.round_price(data["traded_price"]),
            filled_quantity=pair.round_quantity(data["traded_quantity"]),
            order_id=int(data["order_id"]),
        )


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
    trigger_price: float
    trades: List[PrivateTrade]

    @cached_property
    def is_buy(self):
        return self.side == OrderSide.BUY

    @cached_property
    def is_sell(self):
        return self.side == OrderSide.SELL

    @cached_property
    def is_active(self):
        return self.status == OrderStatus.ACTIVE

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
    def is_pending(self):
        return self.status == OrderStatus.PENDING

    @cached_property
    def volume(self):
        return self.pair.round_quantity(self.price * self.quantity)

    @cached_property
    def filled_volume(self):
        return self.pair.round_quantity(
            self.filled_price * self.filled_quantity
        )

    @cached_property
    def remain_volume(self):
        return self.pair.round_quantity(self.filled_volume - self.volume)

    @cached_property
    def remain_quantity(self):
        return self.pair.round_quantity(self.quantity - self.filled_quantity)

    @classmethod
    def create_from_api(
        cls, pair: Pair, data: Dict, trades: List[Dict] = None
    ) -> "Order":
        fees_coin, trigger_price = None, None
        if data["fee_currency"]:
            fees_coin = Coin(data["fee_currency"])
        if data.get("trigger_price") is not None:
            trigger_price = pair.round_price(data["trigger_price"])

        trades = [
            PrivateTrade.create_from_api(pair, trade) for trade in trades or []
        ]

        return cls(
            id=int(data["order_id"]),
            status=OrderStatus(data["status"]),
            side=OrderSide(data["side"]),
            price=pair.round_price(data["avg_price"] or data["price"]),
            quantity=pair.round_quantity(data["quantity"]),
            client_id=data["client_oid"],
            created_at=int(data["create_time"] / 1000),
            updated_at=int(data["update_time"] / 1000),
            type=OrderType(data["type"]),
            pair=pair,
            filled_price=pair.round_price(data["avg_price"]),
            filled_quantity=pair.round_quantity(data["cumulative_quantity"]),
            fees_coin=fees_coin,
            force_type=OrderForceType(data["time_in_force"]),
            trigger_price=trigger_price,
            trades=trades,
        )


@dataclass
class Interest:
    loan_id: int
    coin: Coin
    interest: float
    stake_amount: float
    interest_rate: float

    @classmethod
    def create_from_api(cls, data: Dict) -> "Interest":
        return cls(
            loan_id=int(data["loan_id"]),
            coin=Coin(data["currency"]),
            interest=float(data["interest"]),
            stake_amount=float(data["stake_amount"]),
            interest_rate=float(data["interest_rate"]),
        )


class WithdrawalStatus(str, Enum):
    PENDING = "0"
    PROCESSING = "1"
    REJECTED = "2"
    PAYMENT_IN_PROGRESS = "3"
    PAYMENT_FAILED = "4"
    COMPLETED = "5"
    CANCELLED = "6"


class DepositStatus(str, Enum):
    NOT_ARRIVED = "0"
    ARRIVED = "1"
    FAILED = "2"
    PENDING = "3"


class TransactionType(IntEnum):
    WITHDRAWAL = 0
    DEPOSIT = 1


@dataclass
class Transaction:
    coin: Coin
    fee: float
    create_time: int
    id: str
    update_time: int
    amount: float
    address: str

    @staticmethod
    def _prepare(data):
        return dict(
            id=data["id"],
            coin=Coin(data["currency"]),
            fee=float(data["fee"]),
            create_time=datetime.fromtimestamp(
                int(data["create_time"]) / 1000
            ),
            update_time=datetime.fromtimestamp(
                int(data["update_time"]) / 1000
            ),
            amount=float(data["amount"]),
            address=data["address"],
        )


@dataclass
class Deposit(Transaction):
    status: DepositStatus

    @classmethod
    def create_from_api(cls, data: Dict) -> "Deposit":
        params = cls._prepare(data)
        params["status"] = DepositStatus(data["status"])
        return cls(**params)


@dataclass
class Withdrawal(Transaction):
    client_wid: str
    status: WithdrawalStatus
    txid: str

    @classmethod
    def create_from_api(cls, data: Dict) -> "Withdrawal":
        params = cls._prepare(data)
        params["client_wid"] = data.get("client_wid", "")
        params["status"] = WithdrawalStatus(data["status"])
        params["txid"] = data["txid"]
        return cls(**params)


class Timeframe(IntEnum):
    NOW = 0
    MINUTES = 60
    HOURS = 60 * MINUTES
    DAYS = 24 * HOURS
    WEEKS = 7 * DAYS
    MONTHS = 30 * DAYS

    @classmethod
    def resolve(cls, seconds: int) -> int:
        return seconds + int(time.time())
