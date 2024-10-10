import time
import typing as TP
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum
from typing import Dict, List

from cached_property import cached_property

from .helpers import round_down, round_up


@dataclass
class Instrument:
    exchange_name: str

    @property
    def name(self):
        return self.exchange_name.replace("1", "ONE_")

    def __hash__(self):
        return self.exchange_name.__hash__()

    def __eq__(self, other):
        return self.exchange_name == other.exchange_name


@dataclass
class Pair(Instrument):
    price_precision: int
    quantity_precision: int

    @cached_property
    def _split_instrument(self):
        return self.exchange_name.split("_")

    @cached_property
    def base_instrument(self) -> Instrument:
        return Instrument(self._split_instrument[0])

    @cached_property
    def quote_instrument(self) -> Instrument:
        return Instrument(self._split_instrument[1])

    def round_price(self, price):
        return round_down(float(price), self.price_precision)

    def round_quantity(self, quantity):
        return round_down(float(quantity), self.quantity_precision)

    def __hash__(self):
        return self.exchange_name.__hash__()

    def __eq__(self, other):
        return self.exchange_name == other.exchange_name


class DefaultPairDict(dict):
    """Use default precision for old missing pairs."""

    def __getitem__(self, name: str) -> Pair:
        try:
            return super().__getitem__(name)
        except KeyError:
            return Pair(name, 8, 8)


@dataclass
class MarketTicker:
    pair: Pair
    buy_price: TP.Union[float, None]
    sell_price: TP.Union[float, None]
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
            buy_price=pair.round_price(data["b"]) if data["b"] else None,
            sell_price=pair.round_price(data["k"]) if data["k"] else None,
            trade_price=pair.round_price(data["a"]) if data["a"] else None,
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
    HOURS_2 = "2h"
    HOURS_4 = "4h"
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

    @classmethod
    def from_api(cls, order, pair, side):
        order[0] = pair.round_price(order[0])
        order[1] = pair.round_quantity(order[1])
        return cls(*order, pair, side)


@dataclass
class OrderBook:
    buys: List[OrderInBook]
    sells: List[OrderInBook]
    pair: Pair

    @property
    def spread(self) -> float:
        return round_down(self.sells[-1].price / self.buys[0].price - 1, 6)


@dataclass
class InstrumentBalance(Instrument):
    total: float
    reserved: float
    market_value: float
    haircut: float
    collateral_amount: float
    collateral_eligible: bool
    max_withdrawal_balance: float

    @property
    def available(self) -> float:
        return self.total - self.reserved

    @classmethod
    def from_api(cls, data):
        return cls(
            total=float(data["quantity"]),
            reserved=float(data["reserved_qty"]),
            market_value=float(data["market_value"]),
            exchange_name=data["instrument_name"],
            collateral_eligible="true" == data["collateral_eligible"],
            collateral_amount=float(data["collateral_amount"]),
            haircut=float(data["haircut"]),
            max_withdrawal_balance=float(data["max_withdrawal_balance"]),
        )

    def __hash__(self):
        return self.exchange_name.__hash__()

    def __eq__(self, other):
        return self.exchange_name == other.exchange_name


@dataclass
class Balance:
    total_available: float
    total_available_instrument: Instrument
    instruments: list[InstrumentBalance]

    def __contains__(self, instrument):
        print("check", instrument)
        return instrument in [inst for inst in self.instruments]

    def __getitem__(self, instrument):
        return next(inst for inst in self.instruments if inst == instrument)

    def __iter__(self):
        return iter(self.instruments)

    @classmethod
    def from_api(cls, data):
        return cls(
            total_available=float(data["total_available_balance"]),
            total_available_instrument=Instrument(data["instrument_name"]),
            instruments=[
                InstrumentBalance.from_api(bal)
                for bal in data["position_balances"]
            ],
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
    POST_ONLY = "POST_ONLY"
    LIQUIDATION = "LIQUIDATION"
    NOTIONAL_ORDER = "NOTIONAL_ORDER"


class OrderForceType(str, Enum):
    GOOD_TILL_CANCEL = "GOOD_TILL_CANCEL"
    FILL_OR_KILL = "FILL_OR_KILL"
    IMMEDIATE_OR_CANCEL = "IMMEDIATE_OR_CANCEL"


class TradeType(str, Enum):
    MAKER = "MAKER"
    TAKER = "TAKER"


@dataclass
class PrivateTrade:
    id: str
    account_id: str
    client_oid: str
    event_date: str
    quantity: float
    price: float
    fees: float
    fees_instrument: Instrument
    pair: Pair
    side: OrderSide
    type: TradeType
    created_at: int
    created_at_ns: int
    order_id: str

    @cached_property
    def is_buy(self):
        return self.side == OrderSide.BUY

    @cached_property
    def is_sell(self):
        return self.side == OrderSide.SELL

    @classmethod
    def create_from_api(cls, pair: Pair, data: Dict) -> "PrivateTrade":
        return cls(
            id=data["trade_id"],
            client_oid=data["client_oid"],
            account_id=data["account_id"],
            event_date=data["event_date"],
            quantity=pair.round_quantity(data["traded_quantity"]),
            price=pair.round_price(data["traded_price"]),
            fees=round_up(float(data["fees"]), 8),
            fees_instrument=Instrument(data["fee_instrument_name"]),
            pair=pair,
            side=OrderSide(data["side"]),
            type=TradeType(data["taker_side"]),
            created_at=int(data["create_time"] / 1000),
            created_at_ns=int(data["create_time_ns"]),
            order_id=data["order_id"],
        )


@dataclass
class Order:
    id: str
    client_id: str
    account_id: str
    type: OrderType
    status: OrderStatus
    side: OrderSide
    exec_type: OrderExecType
    limit_price: TP.Union[float, None]
    value: float
    quantity: float
    maker_fee_rate: float
    taker_fee_rate: float
    filled_price: float
    filled_quantity: float
    filled_value: float
    filled_fee: float
    update_user_id: str
    order_date: str
    pair: Pair
    fees_instrument: Instrument
    force_type: OrderForceType
    created_at: int
    updated_at: int
    create_time_ns: int

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
        return not self.remain_quantity

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
        return cls(
            id=data["order_id"],
            account_id=data["account_id"],
            client_id=data["client_oid"],
            type=OrderType(data["order_type"]),
            force_type=OrderForceType(data["time_in_force"]),
            side=OrderSide(data["side"]),
            exec_type=OrderExecType(data["exec_inst"][0])
            if data["exec_inst"]
            else None,
            quantity=pair.round_quantity(data["quantity"]),
            limit_price=pair.round_price(data["limit_price"])
            if "limit_price" in data
            else None,
            value=pair.round_price(data["order_value"]),
            maker_fee_rate=round(float(data.get("maker_fee_rate", 0)), 6),
            taker_fee_rate=round(float(data.get("taker_fee_rate", 0)), 6),
            filled_price=pair.round_price(data["avg_price"]),
            filled_quantity=pair.round_quantity(data["cumulative_quantity"]),
            filled_value=pair.round_price(data["cumulative_value"]),
            filled_fee=round(float(data["cumulative_fee"]), 6),
            status=OrderStatus(data["status"]),
            update_user_id=data["update_user_id"],
            order_date=data["order_date"],
            pair=pair,
            fees_instrument=Instrument(data["fee_instrument_name"]),
            created_at=int(data["create_time"] / 1000),
            create_time_ns=int(data["create_time_ns"]),
            updated_at=int(data["update_time"] / 1000),
        )


@dataclass
class Interest:
    loan_id: int
    instrument: Instrument
    interest: float
    stake_amount: float
    interest_rate: float

    @classmethod
    def create_from_api(cls, data: Dict) -> "Interest":
        return cls(
            loan_id=int(data["loan_id"]),
            instrument=Instrument(data["currency"]),
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
    instrument: Instrument
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
            instrument=Instrument(data["currency"]),
            fee=float(data["fee"]),
            create_time=datetime.fromtimestamp(int(data["create_time"]) / 1000),
            update_time=datetime.fromtimestamp(int(data["update_time"]) / 1000),
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
        return int((time.time() + seconds) * 1000)

    # @classmethod
    # def ago(cls, seconds: int) -> tuple[int, int]:
    #     return cls.resolve(-seconds)
