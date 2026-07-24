import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from functools import cached_property
from typing import Any, ClassVar

from typing_extensions import override

from .helpers import round_down


@dataclass(frozen=True)
class Instrument:
    exchange_name: str
    _registry: ClassVar[dict[str, "Instrument"] | None] = field(
        default=None, init=False
    )

    def __post_init__(self):
        if Instrument._registry is None:
            Instrument._registry = {}
        Instrument._registry[self.exchange_name] = self

    @property
    def name(self) -> str:
        return self.exchange_name.replace("1", "ONE_").replace("2", "TWO_")

    @classmethod
    def all(cls) -> list["Instrument"]:
        return list(Instrument._registry.values()) if Instrument._registry else []


class InstrumentType(str, Enum):
    """Type of trading instrument.

    Clean names that also work as the actual API values.
    Access SPOT.value to get the API string if needed.
    """

    SPOT = "CCY_PAIR"  # Spot trading pairs
    PERPETUAL = "DERIVATIVES"  # Perpetual futures
    FUTURES = "FUTURES"  # Expiring futures contracts


@dataclass(frozen=True)
class Pair:
    """Trading pair with precision and order limits."""

    exchange_name: str
    price_precision: int
    quantity_precision: int
    # Additional instrument metadata from public/get-instruments
    inst_type: InstrumentType  # Required - will raise if API returns unknown type
    display_name: str | None = None
    base_currency: Instrument | None = None
    quote_currency: Instrument | None = None
    quantity_tick_size: float | None = None  # Min quantity increment
    price_tick_size: float | None = None  # Min price increment
    min_order_quantity: float | None = None  # Min order quantity
    max_order_quantity: float | None = None  # Max order quantity
    maker_fee_rate: float | None = None  # Maker fee rate
    taker_fee_rate: float | None = None  # Taker fee rate
    min_order_notional_usd: float = 1.0
    max_order_notional_usd: float = 1000000.0
    _registry: ClassVar[dict[str, "Pair"] | None] = field(default=None, init=False)

    def __post_init__(self):
        if Pair._registry is None:
            Pair._registry = {}
        Pair._registry[self.exchange_name] = self
        parts = self.exchange_name.split("_")
        if len(parts) < 2:
            raise ValueError(
                f"Invalid pair name: {self.exchange_name}, expected format BASE_QUOTE"
            )

    @property
    def name(self) -> str:
        return self.exchange_name.replace("1", "ONE_").replace("2", "TWO_")

    @classmethod
    def all(cls) -> list["Pair"]:
        return list(Pair._registry.values()) if Pair._registry else []

    @classmethod
    def from_api(cls, data: dict[str, Any], filter_derivatives: bool = True) -> "Pair":
        """Create Pair from API instrument data.

        Args:
            data: Instrument data from public/get-instruments
            filter_derivatives: If True, skip derivative instruments (skip if symbol contains '-' or '@')

        Returns:
            Pair with full instrument metadata

        Raises:
            ValueError: If symbol contains '-' or '@' when filter_derivatives=True
        """
        symbol = data.get("symbol", "")

        # Skip derivatives if filtering
        if filter_derivatives and ("-" in symbol or "@" in symbol):
            raise ValueError(f"Skipping derivative symbol: {symbol}")

        # Parse instrument type - will raise error if unknown
        inst_type_str = data.get("inst_type", "")
        inst_type = InstrumentType(inst_type_str)

        return cls(
            exchange_name=symbol,
            price_precision=data.get("quote_decimals", 8),
            quantity_precision=data.get("quantity_decimals", 8),
            min_order_notional_usd=float(data.get("min_order_qty", 1.0)) * 100
            if data.get("min_order_qty")
            else 1.0,
            max_order_notional_usd=float(data.get("max_order_qty", 1000000.0)) * 100
            if data.get("max_order_qty")
            else 1000000.0,
            inst_type=inst_type,
            display_name=data.get("display_name", symbol),
            base_currency=Instrument(data["base_ccy"])
            if data.get("base_ccy")
            else None,
            quote_currency=Instrument(data["quote_ccy"])
            if data.get("quote_ccy")
            else None,
            quantity_tick_size=float(data.get("qty_tick_size", 0)),
            price_tick_size=float(data.get("price_tick_size", 0)),
            min_order_quantity=float(data.get("min_order_qty", 0)),
            max_order_quantity=float(data.get("max_order_qty", 0)),
            maker_fee_rate=float(data.get("maker_fee_rate", 0)),
            taker_fee_rate=float(data.get("taker_fee_rate", 0)),
        )

    @cached_property
    def base_instrument(self) -> Instrument:
        return Instrument(self.exchange_name.split("_")[0])

    @cached_property
    def quote_instrument(self) -> Instrument:
        return Instrument(self.exchange_name.split("_")[1])

    def round_price(self, price: float | str) -> float:
        return round_down(float(price), self.price_precision)

    def round_quantity(self, quantity: float | str) -> float:
        return round_down(float(quantity), self.quantity_precision)

    def validate_order_notional(self, notional: float) -> bool:
        """Check if order notional value is within allowed limits."""
        return self.min_order_notional_usd <= notional <= self.max_order_notional_usd


class DefaultPairDict(dict[str, Pair]):
    """Use default precision for old missing pairs."""

    @override
    def __getitem__(self, name: str) -> Pair:
        try:
            return super().__getitem__(name)
        except KeyError:
            return Pair(
                name,
                8,
                8,
                min_order_notional_usd=1.0,
                max_order_notional_usd=1000000.0,
            )


@dataclass
class BaseCurrencyConfig:
    """Risk parameters for a specific instrument."""

    instrument_name: str
    min_order_notional_usd: float = 1.0
    max_order_notional_usd: float = 1000000.0
    order_limit: float = 1000000.0
    minimum_haircut: float = 0.0
    unit_margin_rate: float = 0.0

    # Optional fields
    collateral_cap_notional: float | None = None
    max_product_leverage_for_spot: float | None = None
    max_product_leverage_for_perps: float | None = None
    max_product_leverage_for_futures: float | None = None
    max_short_sell_limit: float | None = None
    long_pos_limit_perps: float | None = None
    short_pos_limit_perps: float | None = None
    long_pos_limit_futures: float | None = None
    short_pos_limit_futures: float | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "BaseCurrencyConfig":
        return cls(
            instrument_name=data["instrument_name"],
            min_order_notional_usd=float(data.get("min_order_notional_usd", 1.0)),
            max_order_notional_usd=float(data.get("max_order_notional_usd", 1000000.0)),
            order_limit=float(data.get("order_limit", 1000000.0)),
            minimum_haircut=float(data.get("minimum_haircut", 0)),
            unit_margin_rate=float(data.get("unit_margin_rate", 0)),
            collateral_cap_notional=float(data["collateral_cap_notional"])
            if data.get("collateral_cap_notional")
            else None,
            max_product_leverage_for_spot=float(data["max_product_leverage_for_spot"])
            if data.get("max_product_leverage_for_spot")
            else None,
            max_product_leverage_for_perps=float(data["max_product_leverage_for_perps"])
            if data.get("max_product_leverage_for_perps")
            else None,
            max_product_leverage_for_futures=float(
                data["max_product_leverage_for_futures"]
            )
            if data.get("max_product_leverage_for_futures")
            else None,
            max_short_sell_limit=float(data["max_short_sell_limit"])
            if data.get("max_short_sell_limit")
            else None,
            long_pos_limit_perps=float(data["long_pos_limit_perps"])
            if data.get("long_pos_limit_perps")
            else None,
            short_pos_limit_perps=float(data["short_pos_limit_perps"])
            if data.get("short_pos_limit_perps")
            else None,
            long_pos_limit_futures=float(data["long_pos_limit_futures"])
            if data.get("long_pos_limit_futures")
            else None,
            short_pos_limit_futures=float(data["short_pos_limit_futures"])
            if data.get("short_pos_limit_futures")
            else None,
        )


@dataclass
class RiskParameters:
    """Complete risk parameters from API."""

    default_max_product_leverage_for_spot: float
    default_max_product_leverage_for_perps: float
    default_max_product_leverage_for_futures: float
    default_umr_multiplier_for_spot: float
    default_umr_multiplier_for_perps: float
    default_umr_multiplier_for_futures: float
    default_long_pos_limit_perps: float
    default_short_pos_limit_perps: float
    default_long_pos_limit_futures: float
    default_short_pos_limit_futures: float
    default_unit_margin_rate: float
    default_collateral_cap: float
    update_timestamp_ms: int
    base_currency_config: list[BaseCurrencyConfig]
    perpetual_swap_config: dict[str, Any] | None = None
    futures_config: dict[str, Any] | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "RiskParameters":
        return cls(
            default_max_product_leverage_for_spot=float(
                data.get("default_max_product_leverage_for_spot", 1.0)
            ),
            default_max_product_leverage_for_perps=float(
                data.get("default_max_product_leverage_for_perps", 50.0)
            ),
            default_max_product_leverage_for_futures=float(
                data.get("default_max_product_leverage_for_futures", 20.0)
            ),
            default_umr_multiplier_for_spot=float(
                data.get("default_umr_multiplier_for_spot", 0)
            ),
            default_umr_multiplier_for_perps=float(
                data.get("default_umr_multiplier_for_perps", 0)
            ),
            default_umr_multiplier_for_futures=float(
                data.get("default_umr_multiplier_for_futures", 0)
            ),
            default_long_pos_limit_perps=float(
                data.get("default_long_pos_limit_perps", -1)
            ),
            default_short_pos_limit_perps=float(
                data.get("default_short_pos_limit_perps", -1)
            ),
            default_long_pos_limit_futures=float(
                data.get("default_long_pos_limit_futures", -1)
            ),
            default_short_pos_limit_futures=float(
                data.get("default_short_pos_limit_futures", -1)
            ),
            default_unit_margin_rate=float(data.get("default_unit_margin_rate", 0)),
            default_collateral_cap=float(data.get("default_collateral_cap", 0)),
            update_timestamp_ms=int(data.get("update_timestamp_ms", 0)),
            base_currency_config=[
                BaseCurrencyConfig.from_api(config)
                for config in data.get("base_currency_config", [])
            ],
            perpetual_swap_config=data.get("perpetual_swap_config"),
            futures_config=data.get("futures_config"),
        )


@dataclass
class MarketTicker:
    """Market ticker with 24h statistics and optional derivatives data."""

    pair: Pair
    buy_price: float | None  # Best bid price
    sell_price: float | None  # Best ask price
    trade_price: float  # Latest trade price
    time: int  # Timestamp (seconds)
    volume: float  # 24h traded volume (quantity)
    high: float  # 24h highest trade price
    low: float  # 24h lowest trade price
    change: float  # 24h price change
    volume_usd: float | None = None  # 24h volume value in USD
    open_interest: float | None = None  # Open interest (derivatives only)

    @classmethod
    def from_api(cls, pair, data):
        """Parse ticker from API response.

        API fields:
        - a: latest trade price
        - b: best bid price
        - k: best ask price
        - c: 24h change
        - h: 24h high
        - l: 24h low
        - t: timestamp (ms)
        - v: 24h volume
        - vv: 24h volume value in USD
        - oi: open interest (derivatives)
        """
        return cls(
            pair=pair,
            buy_price=float(data["b"]) if data.get("b") else None,
            sell_price=float(data["k"]) if data.get("k") else None,
            trade_price=float(data["a"]) if data.get("a") else None,
            time=int(float(data["t"]) / 1000) if data.get("t") else 0,
            volume=float(data.get("v", 0)),
            high=float(data.get("h", 0)),
            low=float(data.get("l", 0)),
            change=float(data.get("c", 0)),
            volume_usd=float(data["vv"]) if data.get("vv") else None,
            open_interest=float(data["oi"]) if data.get("oi") else None,
        )


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class MarketTrade:
    """Public market trade with optional nanosecond precision and match ID."""

    id: str
    time: int  # Timestamp (seconds)
    price: float
    quantity: float
    side: OrderSide
    pair: Pair
    timestamp_ns: int | None = None  # Nanosecond timestamp (REST only)
    instrument_name: str | None = None  # Original instrument name
    match_id: str | None = None  # Trade match ID for WebSocket sync

    @classmethod
    def from_api(cls, pair: Pair, data: dict[str, Any]):
        """Parse trade from API response.

        API fields:
        - d: trade ID
        - t: timestamp (ms)
        - tn: timestamp (ns) - REST only
        - p: price
        - q: quantity
        - s: side (BUY/SELL)
        - i: instrument name
        - m: match ID
        """
        time_ms = float(data.get("t", 0))
        time_ns = float(data.get("tn", 0)) or (time_ms * 1_000_000 if time_ms else 0)

        return cls(
            id=data["d"],
            time=int(time_ns / 1_000_000_000) if time_ns else int(time_ms / 1000),
            timestamp_ns=int(time_ns) if time_ns else None,
            price=float(data["p"]),
            quantity=float(data["q"]),
            side=OrderSide(data["s"].upper()),
            pair=pair,
            instrument_name=data.get("i"),
            match_id=data.get("m"),
        )


class Timeframe(str, Enum):
    MIN = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_12 = "12h"
    DAY = "1D"
    WEEK = "7D"
    WEEK_2 = "14D"
    MONTH = "1M"


@dataclass(frozen=True)
class Candle:
    """Candlestick with OHLCV data."""

    time: int  # Timestamp (seconds)
    open: float
    high: float
    low: float
    close: float
    quantity: float  # Volume
    pair: Pair = None
    interval: str | None = None  # Optional timeframe (M1, M5, H1, etc.)

    @classmethod
    def from_api(cls, data: dict[str, Any], pair: Pair | None = None):
        """Parse candle from API response.

        API fields:
        - t: timestamp (ms)
        - o: open
        - h: high
        - l: low
        - c: close
        - v: volume
        """
        return cls(
            time=int(float(data["t"]) / 1000) if data.get("t") else 0,
            open=float(data["o"]),
            high=float(data["h"]),
            low=float(data["l"]),
            close=float(data["c"]),
            quantity=float(data["v"]),
            pair=pair,
            interval=data.get("interval"),
        )


@dataclass
class OrderInBook:
    """Order book level.

    Note: count field often returns 0 due to API limitation.
    """

    price: float
    quantity: float
    count: int
    pair: Pair
    side: OrderSide

    @property
    def volume(self) -> float:
        return self.pair.round_price(self.price * self.quantity)

    @classmethod
    def from_api(cls, order, pair, side):
        """Parse orderbook level from API response.

        Format: [price, quantity, count(optional)]
        Known issue: count often returns 0.
        """
        price = float(order[0])
        quantity = float(order[1])
        # Handle variable-length arrays - count may be missing or unreliable
        count = int(order[2]) if len(order) > 2 else 0
        return cls(price, quantity, count, pair, side)


@dataclass
class OrderBook:
    buys: list[OrderInBook]
    sells: list[OrderInBook]
    pair: Pair

    @property
    def spread(self) -> float:
        return round_down(self.sells[-1].price / self.buys[0].price - 1, 6)


@dataclass(frozen=True)
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
        return instrument in [inst for inst in self.instruments]

    def __getitem__(self, instrument):
        return next(inst for inst in self.instruments if inst == instrument)

    def get(self, instrument, default=None):
        try:
            return next(inst for inst in self.instruments if inst == instrument)
        except StopIteration:
            return default

    def __iter__(self):
        return iter(self.instruments)

    @classmethod
    def from_api(cls, data):
        return cls(
            total_available=float(data["total_available_balance"]),
            total_available_instrument=Instrument(data["instrument_name"]),
            instruments=[
                InstrumentBalance.from_api(bal) for bal in data["position_balances"]
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
    def create_from_api(cls, pair: Pair, data: dict[str, Any]) -> "PrivateTrade":
        return cls(
            id=data["trade_id"],
            client_oid=data["client_oid"],
            account_id=data["account_id"],
            event_date=data["event_date"],
            quantity=float(data["traded_quantity"]),
            price=float(data["traded_price"]),
            fees=float(data["fees"]),
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
    limit_price: float | None
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
        return self.status == OrderStatus.FILLED and self.remain_quantity <= 0

    @cached_property
    def is_pending(self):
        return self.status == OrderStatus.PENDING

    @cached_property
    def volume(self):
        return self.pair.round_price(self.price * self.quantity)

    @cached_property
    def filled_volume(self):
        return self.pair.round_price(self.filled_price * self.filled_quantity)

    @cached_property
    def remain_volume(self):
        return self.pair.round_price(self.filled_volume - self.volume)

    @cached_property
    def remain_quantity(self):
        # TODO: fix bug with round quantity
        return self.pair.round_quantity(self.quantity - self.filled_quantity)

    @classmethod
    def create_from_api(
        cls,
        pair: Pair,
        data: dict[str, Any],
        trades: list[dict[str, Any]] | None = None,
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
            quantity=float(data["quantity"]),
            limit_price=float(data["limit_price"]) if "limit_price" in data else None,
            value=float(data["order_value"]),
            maker_fee_rate=float(data.get("maker_fee_rate", 0)),
            taker_fee_rate=float(data.get("taker_fee_rate", 0)),
            filled_price=float(data["avg_price"]),
            filled_quantity=float(data["cumulative_quantity"]),
            filled_value=float(data["cumulative_value"]),
            filled_fee=float(data["cumulative_fee"]),
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
    def create_from_api(cls, data: dict[str, Any]) -> "Interest":
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
    def create_from_api(cls, data: dict[str, Any]) -> "Deposit":
        params = cls._prepare(data)
        params["status"] = DepositStatus(data["status"])
        return cls(**params)


@dataclass
class Withdrawal(Transaction):
    client_wid: str
    status: WithdrawalStatus
    txid: str

    @classmethod
    def create_from_api(cls, data: dict[str, Any]) -> "Withdrawal":
        params = cls._prepare(data)
        params["client_wid"] = data.get("client_wid", "")
        params["status"] = WithdrawalStatus(data["status"])
        params["txid"] = data["txid"]
        return cls(**params)


class TimeDelta(IntEnum):
    NOW = 0
    MINUTES = 60
    HOUR = 60 * MINUTES
    DAYS = 24 * HOUR
    WEEKS = 7 * DAYS
    MONTHS = 30 * DAYS

    @classmethod
    def resolve(cls, seconds: int) -> int:
        return int((time.time() + seconds) * 1000)

    # @classmethod
    # def ago(cls, seconds: int) -> tuple[int, int]:
    #     return cls.resolve(-seconds)
