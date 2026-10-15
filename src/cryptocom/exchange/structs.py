import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from functools import cached_property
from typing import Any, ClassVar

from typing_extensions import override

from .helpers import round_down, round_up


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

    # Identity of an instrument IS its exchange_name. Explicit eq/hash (not
    # dataclass-generated) so Instrument and its subclasses (e.g.
    # InstrumentBalance) interoperate in dicts/sets - the dataclass default
    # requires IDENTICAL classes and tuple-based hashing, which silently
    # broke dict lookups between Instrument keys and InstrumentBalance keys.
    def __eq__(self, other):
        if isinstance(other, Instrument):
            return self.exchange_name == other.exchange_name
        return NotImplemented

    def __hash__(self):
        return self.exchange_name.__hash__()

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
    inst_type: InstrumentType
    display_name: str | None = None
    base_currency: Instrument | None = None
    quote_currency: Instrument | None = None
    quantity_tick_size: float = 0.0
    price_tick_size: float = 0.0
    min_order_quantity: float = 0.0
    max_order_quantity: float = 0.0
    min_order_notional_usd: float = 1.0
    max_order_notional_usd: float = 1000000.0

    deleted: bool = field(default=False, init=True, repr=False)
    _registry: ClassVar[dict[str, "Pair"] | None] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        if not self.deleted:
            if Pair._registry is None:
                Pair._registry = {}
            Pair._registry[self.exchange_name] = self
        parts = self.exchange_name.split("_")
        if len(parts) < 2:
            raise ValueError(
                f"Invalid pair name: {self.exchange_name}, expected format BASE_QUOTE"
            )
        # Ticks are ALWAYS present: an unset tick (0.0 from sparse data or a
        # synthesized fallback pair) is derived from the precision decimal.
        # Callers can treat quantity_tick_size / price_tick_size as the
        # authoritative grid step unconditionally - a zero step could wedge
        # any decrement-to-fit loop.
        # Pair is frozen (hashable registry member): derive via the
        # documented escape hatch, inside __post_init__, exactly once.
        if self.quantity_tick_size <= 0:
            object.__setattr__(
                self, "quantity_tick_size", 10.0 ** (-self.quantity_precision)
            )
        if self.price_tick_size <= 0:
            object.__setattr__(self, "price_tick_size", 10.0 ** (-self.price_precision))

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
        symbol = data["symbol"]

        # Skip derivatives if filtering
        if filter_derivatives and ("-" in symbol or "@" in symbol):
            raise ValueError(f"Skipping derivative symbol: {symbol}")

        # Parse instrument type - will raise error if unknown
        inst_type = InstrumentType(data["inst_type"])

        return cls(
            exchange_name=symbol,
            price_precision=data["quote_decimals"],
            quantity_precision=data["quantity_decimals"],
            min_order_notional_usd=float(data["min_order_qty"]) * 100
            if data.get("min_order_qty")
            else 1.0,
            max_order_notional_usd=float(data["max_order_qty"]) * 100
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
        )

    @cached_property
    def base_instrument(self) -> Instrument:
        return Instrument(self.exchange_name.split("_")[0])

    @cached_property
    def quote_instrument(self) -> Instrument:
        return Instrument(self.exchange_name.split("_")[1])

    def round_price_down(self, price: float | str) -> float:
        """Round price down to pair's price precision (conservative)."""
        return round_down(float(price), self.price_precision)

    def round_price_up(self, price: float | str) -> float:
        """Round price up to pair's price precision."""
        return round_up(float(price), self.price_precision)

    def round_quantity_down(self, quantity: float | str) -> float:
        """Round quantity down to pair's quantity precision (conservative)."""
        return round_down(float(quantity), self.quantity_precision)

    def round_quantity_up(self, quantity: float | str) -> float:
        """Round quantity up to pair's quantity precision."""
        return round_up(float(quantity), self.quantity_precision)

    def validate_order_notional(self, notional: float) -> bool:
        """Check if order notional value is within allowed limits.

        A RELATIVE tolerance forgives binary-product noise: the exchange
        multiplies DECIMAL representations (0.29 x 100 is exactly 29.0
        there), so a product that lands within float noise (~1e-16
        relative) of a limit IS that limit and must pass. The old
        round_down-to-0 trick accepted the over-noise case but still
        rejected the sub-noise one (floor(0.9999999999999999) = 0).
        Genuine sub-minimum notionals stay rejected: noise is ~1e-16,
        the tolerance is 1e-9 relative.
        """
        tol_min = 1e-9 * max(abs(self.min_order_notional_usd), 1.0)
        min_check = notional + tol_min >= self.min_order_notional_usd
        tol_max = 1e-9 * max(abs(self.max_order_notional_usd), 1.0)
        max_check = notional <= self.max_order_notional_usd + tol_max
        return min_check and max_check

    def floor_quantity(self, quantity: float | str) -> float:
        """Largest exchange-representable quantity <= the given one.

        Snaps to the quantity grid (quantity_tick_size, always present),
        then applies the conservative precision round-down. Used to derive
        placeable remainders: a raw float leftover is never placeable as-is.
        """
        step = self.quantity_tick_size
        # +epsilon guards exact grid points eaten by binary floats (2.0000000001)
        steps = math.floor(float(quantity) / step + 1e-9)
        return self.round_quantity_down(steps * step)

    def min_order_quantity_at(self, price: float | str) -> float:
        """Smallest placeable quantity at the given price.

        Must satisfy BOTH the pair's minimum order quantity and the minimum
        order notional at this price, then snap UP to the quantity grid.
        Returns 0.0 when no positive price is given.
        """
        price = float(price)
        if price <= 0:
            return 0.0
        required = max(
            self.min_order_quantity,
            self.min_order_notional_usd / price,
        )
        step = self.quantity_tick_size
        steps = math.ceil(required / step - 1e-9)
        return self.round_quantity_up(steps * step)

    def has_quantity(self, quantity: float | str) -> bool:
        """True when the value represents at least one representable unit.

        Sub-grid dust floors to zero, so callers can ask "is there any
        quantity at all?" without epsilon comparisons - and without the
        input needing to be grid-aligned.
        """
        return self.floor_quantity(quantity) > 0.0

    def same_quantity(self, first: float | str, second: float | str) -> bool:
        """Grid-tolerant equality: snaps both values to the grid, then
        compares exactly. Two spellings of the same grid step are equal
        even when their float representations differ by an ulp.
        """
        return self.round_quantity_down(first) == self.round_quantity_down(second)

    def quantity_reaches(self, quantity: float | str, target: float | str) -> bool:
        """True when quantity has reached target on this pair's grid.

        Accumulation noise around the target snaps onto the grid, so a
        sum of 199.99999999999997 reaches 200 while a real 199.5 does
        not - the epsilon judgement is a grid fact, not a tolerance.
        """
        return self.round_quantity_down(quantity) >= self.round_quantity_down(target)

    def has_price_value(self, price: float | str) -> bool:
        """True when the value is a non-zero representable price: noise
        below one price tick rounds to zero, so "carries no value?" needs
        no epsilon.
        """
        return self.round_price_down(price) > 0.0

    def is_placeable(self, quantity: float | str, price: float | str) -> bool:
        """True if SOME representation of this quantity is placeable.

        Floors the quantity onto the grid first (raw float leftovers from
        fill arithmetic are never placeable as-is), then applies the full
        orderable contract. This is the decide-HOLD-vs-REPLACE predicate:
        a False result means no re-formatting can rescue the order.
        """
        return self.is_orderable(self.floor_quantity(quantity), price)

    def is_orderable(self, quantity: float | str, price: float | str) -> bool:
        """True if this (quantity, price) can be placed on the exchange.

        Checks the full local contract - grid alignment, minimum quantity,
        and notional limits - so callers can decide HOLD-vs-REPLACE on the
        pair's real constraints instead of re-deriving them. A quantity that
        is not grid-aligned is treated as not placeable (the exchange's own
        formatting would silently change it).
        """
        quantity = float(quantity)
        price = float(price)
        if quantity <= 0 or price <= 0:
            return False
        step = self.quantity_tick_size
        off_grid = abs(quantity - self.floor_quantity(quantity)) > 1e-9 * max(1.0, step)
        if off_grid:
            return False
        if (
            quantity + 1e-9 * max(self.min_order_quantity, 1.0)
            < self.min_order_quantity
        ):
            return False
        return self.validate_order_notional(quantity * price)


class DefaultPairDict(dict[str, Pair]):
    """Use default precision for old missing pairs."""

    @override
    def __getitem__(self, name: str) -> Pair:
        try:
            return super().__getitem__(name)
        except KeyError:
            # Create deleted pair that skips registry with default values
            return Pair(
                name,
                8,
                8,
                inst_type=InstrumentType.SPOT,
                display_name=None,
                base_currency=None,
                quote_currency=None,
                quantity_tick_size=0.0,
                price_tick_size=0.0,
                min_order_quantity=0.0,
                max_order_quantity=0.0,
                min_order_notional_usd=1.0,
                max_order_notional_usd=1000000.0,
                deleted=True,
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
    trade_price: float | None  # Latest trade price
    time: int  # Timestamp (seconds)
    volume: float  # 24h traded volume (quantity)
    high: float  # 24h highest trade price
    low: float  # 24h lowest trade price
    change: float  # 24h price change
    volume_usd: float | None = None  # 24h volume value in USD
    open_interest: float | None = None  # Open interest (derivatives only)

    @classmethod
    def from_api(cls, pair: Pair, data: dict[str, Any]) -> "MarketTicker":
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
    pair: Pair | None = None
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
        """Orderbook level volume (conservative: round down)."""
        return round_down(self.price * self.quantity, self.pair.price_precision)

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
    """Order book snapshot.

    Both sides are normalized to BEST-FIRST in ``__post_init__``, regardless
    of the order the caller (or API) provides:

    - ``buys``  sorted by price DESC (``buys[0]``  = best bid)
    - ``sells`` sorted by price ASC  (``sells[0]`` = best ask)

    Prefer the ``best_bid`` / ``best_ask`` / ``mid`` / ``spread`` properties
    over positional indexing.
    """

    buys: list[OrderInBook]
    sells: list[OrderInBook]
    pair: Pair

    def __post_init__(self):
        # A book without BOTH sides is malformed input, not a market state:
        # fail at construction so the caller of process()/pricing is the
        # one that crashes on the programming error, far from the exchange.
        if not self.buys:
            raise ValueError("Order book has no bids")
        if not self.sells:
            raise ValueError("Order book has no asks")
        self.buys.sort(key=lambda level: level.price, reverse=True)
        self.sells.sort(key=lambda level: level.price)

    @property
    def best_bid(self) -> OrderInBook:
        """Top buy level (construction guarantees non-empty books)."""
        if not self.buys:
            raise ValueError("Order book has no bids")
        return self.buys[0]

    @property
    def best_ask(self) -> OrderInBook:
        """Top sell level (construction guarantees non-empty books)."""
        if not self.sells:
            raise ValueError("Order book has no asks")
        return self.sells[0]

    @property
    def mid(self) -> float:
        """Mid price between best bid and best ask."""
        return (self.best_bid.price + self.best_ask.price) / 2

    @property
    def spread(self) -> float:
        """Relative spread (best_ask / best_bid - 1)."""
        return round_down(self.best_ask.price / self.best_bid.price - 1, 6)


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
        if isinstance(other, Instrument):
            return self.exchange_name == other.exchange_name
        return NotImplemented


@dataclass
class Balance:
    total_available: float
    total_available_instrument: Instrument
    instruments: list[InstrumentBalance]

    @staticmethod
    def _key(instrument) -> str:
        """Accept an Instrument, an InstrumentBalance, or a plain name string.

        Dataclass equality never matches (InstrumentBalance is a SUBCLASS of
        Instrument and dataclass __eq__ requires identical classes), so lookups
        must compare exchange_name explicitly.
        """
        return instrument if isinstance(instrument, str) else instrument.exchange_name

    def __contains__(self, instrument):
        key = self._key(instrument)
        return any(inst.exchange_name == key for inst in self.instruments)

    def __getitem__(self, instrument):
        key = self._key(instrument)
        return next(inst for inst in self.instruments if inst.exchange_name == key)

    def get(self, instrument, default=None):
        try:
            return self[instrument]
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
    PENDING = "PENDING"
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


TERMINAL_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
)


class OrderExecFlag(str, Enum):
    """Execution flag for orders."""

    POST_ONLY = "POST_ONLY"
    REDUCE_ONLY = "REDUCE_ONLY"
    SMART_POST_ONLY = "SMART_POST_ONLY"
    ISOLATED_MARGIN = "ISOLATED_MARGIN"
    MARGIN_ORDER = "MARGIN_ORDER"
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
    exec_flags: list[OrderExecFlag]
    limit_price: float | None
    volume: float
    quantity: float
    maker_fee_rate: float
    taker_fee_rate: float
    filled_price: float
    filled_quantity: float
    filled_volume: float
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
    def is_new(self):
        return self.status == OrderStatus.NEW

    @cached_property
    def price(self):
        """Order price (filled price preferred, otherwise limit price)."""
        # For filled orders, use filled_price; otherwise use limit_price
        return self.filled_price if self.filled_price else self.limit_price

    @cached_property
    def remain_quantity(self):
        """Remaining quantity to be filled (conservative: round down)."""
        # Calculate remaining and round down to never overstate
        remain = self.quantity - self.filled_quantity
        return round_down(remain, self.pair.quantity_precision)

    @cached_property
    def is_terminal(self) -> bool:
        """True when the order can no longer change status."""
        return self.status in TERMINAL_ORDER_STATUSES

    @classmethod
    def create_from_api(
        cls,
        pair: Pair,
        data: dict[str, Any],
        trades: list[dict[str, Any]] | None = None,
    ) -> "Order":
        # Parse exec_inst as array of OrderExecFlag
        exec_flags = [
            OrderExecFlag(inst)
            for inst in data.get("exec_inst", [])
            if inst in [e.value for e in OrderExecFlag]
        ]

        return cls(
            id=data["order_id"],
            account_id=data["account_id"],
            client_id=data["client_oid"],
            type=OrderType(data["order_type"]),
            force_type=OrderForceType(data["time_in_force"]),
            side=OrderSide(data["side"]),
            exec_flags=exec_flags,
            quantity=round_down(float(data["quantity"]), pair.quantity_precision),
            limit_price=round_down(float(data["limit_price"]), pair.price_precision)
            if "limit_price" in data
            else None,
            volume=round_down(float(data["order_value"]), pair.price_precision),
            maker_fee_rate=float(data.get("maker_fee_rate", 0)),
            taker_fee_rate=float(data.get("taker_fee_rate", 0)),
            # PARSE CONTRACT for fill fields: always >= 0.0, and either
            # EXACTLY 0.0 or exchange-representable - round-down snaps any
            # sub-precision residue (1e-16 noise, "0.000000001") to 0.0,
            # and max() clamps malformed negatives. Callers can therefore
            # test `order.filled_quantity > 0.0` outright: "has it filled"
            # is a parse guarantee, not an epsilon judgement.
            filled_price=max(
                0.0,
                round_down(float(data.get("avg_price") or 0.0), pair.price_precision),
            ),
            filled_quantity=max(
                0.0,
                round_down(
                    float(data.get("cumulative_quantity") or 0.0),
                    pair.quantity_precision,
                ),
            ),
            filled_volume=max(
                0.0,
                round_down(
                    float(data.get("cumulative_value") or 0.0), pair.price_precision
                ),
            ),
            filled_fee=max(
                0.0, round_down(float(data.get("cumulative_fee") or 0.0), 8)
            ),
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
        return {
            "id": data["id"],
            "instrument": Instrument(data["currency"]),
            "fee": float(data["fee"]),
            "create_time": datetime.fromtimestamp(int(data["create_time"]) / 1000),
            "update_time": datetime.fromtimestamp(int(data["update_time"]) / 1000),
            "amount": float(data["amount"]),
            "address": data["address"],
        }


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
