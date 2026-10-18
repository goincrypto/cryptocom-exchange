import asyncio
import logging
import time
import typing as tp
import warnings
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .api import ApiError, ApiProvider
from .exceptions import (
    OrderNotActiveError,
    OrderNotFoundError,
    WaitNotConfirmedError,
)
from .market import Market
from .helpers import validate_client_id
from .structs import (
    Balance,
    DefaultPairDict,
    Deposit,
    DepositStatus,
    FeeCredit,
    FeeRate,
    Instrument,
    InstrumentBalance,
    InstrumentFeeRate,
    Interest,
    Order,
    OrderExecFlag,
    OrderForceType,
    OrderSide,
    OrderStatus,
    OrderType,
    Pair,
    PrivateTrade,
    Withdrawal,
    WithdrawalStatus,
)

# Order limits (from Crypto.com Exchange official documentation)
# Per Trading Pair: Maximum 200 open orders for a single trading pair (e.g., BTC/USDT)
# Overall Account: Maximum 1,000 open orders across all trading pairs combined
MAX_OPEN_ORDERS_PER_PAIR = 200
MAX_OPEN_ORDERS_PER_ACCOUNT = 1000


@dataclass
class OrderKeys:
    """Order identifiers returned from order operations."""

    id: str  # Exchange order ID
    client_id: str  # Client order ID


class Account:
    """Provides access to account actions and data. Balance, trades, orders."""

    api: ApiProvider
    market: Market
    pairs: DefaultPairDict
    logger: logging.Logger

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        from_env: bool = False,
        market: Market | None = None,
        api: ApiProvider | None = None,
        logger: logging.Logger | None = None,
        orders_ttl: float = 5.0,
    ) -> None:
        if not api and not (api_key and api_secret) and not from_env:
            raise ValueError("Pass ApiProvider or api_key with api_secret or from_env")
        self.api = api or ApiProvider(
            api_key=api_key, api_secret=api_secret, from_env=from_env
        )
        self.logger = logger or logging.getLogger(__name__)
        self.market = market or Market(api)
        self.pairs = self.market.pairs
        # Order state cache, keyed by client_oid. Terminal orders are kept
        # forever (they can never change); live orders expire after orders_ttl
        # seconds. Set orders_ttl=0 to disable caching (tests).
        self.order_cache: dict[str, Order] = {}
        self.orders_ttl: float = orders_ttl
        self._orders_seen: dict[str, float] = {}
        # Recently created client_oids: a just-created order that momentarily
        # reads back as absent is a create race, NOT proof of absence.
        self._recently_created: dict[str, float] = {}
        self.create_race_guard: float = 2.0

    async def sync_pairs(self):
        await self.market.sync_pairs()
        self.pairs = self.market.pairs

    async def get_balance(self) -> dict[Instrument, InstrumentBalance]:
        """Return balance keyed by Instrument.

        Keys are plain Instrument objects: dataclass __eq__/__hash__ require
        identical classes, so InstrumentBalance keys would never match a
        lookup by Instrument("USD").
        """
        data = (await self.api.post("private/user-balance")) or []
        if not data:
            return {}
        balance = Balance.from_api(data[0])
        return {Instrument(inst.exchange_name): inst for inst in balance}

    async def get_accounts(self) -> dict[str, Any]:
        data = await self.api.post("private/get-accounts")
        return data

    async def get_subaccount_balances(self) -> Any:
        return await self.api.post("private/get-subaccount-balances", {"params": {}})

    async def get_balance_history(self) -> Any:
        return await self.api.post("private/user-balance-history", {"params": {}})

    async def get_deposit_history(
        self,
        instrument: Instrument | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        status: DepositStatus | None = None,
        page: int = 0,
        page_size: int = 20,
    ) -> list[Deposit]:
        """Return all history withdrawals."""
        params = {"page_size": page_size, "page": page}
        if instrument:
            params["currency"] = instrument.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000
        if status:
            params["status"] = status

        data = (
            await self.api.post("private/get-deposit-history", {"params": params}) or {}
        )
        return [Deposit.create_from_api(trx) for trx in data.get("deposit_list") or []]

    async def get_withdrawal_history(
        self,
        instrument: Instrument | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        status: WithdrawalStatus | None = None,
        page: int = 0,
        page_size: int = 20,
    ) -> list[Withdrawal]:
        """Return all history for withdrawal transactions."""
        params = {"page_size": page_size, "page": page}
        if instrument:
            params["currency"] = instrument.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000
        if status:
            params["status"] = status

        data = (
            await self.api.post("private/get-withdrawal-history", {"params": params})
            or {}
        )
        return [
            Withdrawal.create_from_api(trx) for trx in data.get("withdrawal_list") or []
        ]

    async def get_interest_history(
        self,
        instrument: Instrument | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        page: int = 0,
        page_size: int = 20,
    ) -> list[Interest]:
        """Return all history interest."""
        params = {"page_size": page_size, "page": page}
        if instrument:
            params["currency"] = instrument.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000

        data = (
            await self.api.post("private/margin/get-order-history", {"params": params})
            or {}
        )
        return [
            Interest.create_from_api(interest) for interest in data.get("list") or []
        ]

    async def get_orders_history(
        self,
        pair: Pair | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Return all history orders."""
        params = {"limit": limit}
        if pair:
            params["instrument_name"] = pair.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000

        data = (
            await self.api.post("private/get-order-history", {"params": params}) or []
        )
        return [
            Order.create_from_api(self.pairs[order["instrument_name"]], order)
            for order in data
        ]

    async def get_open_orders(
        self, pair: Pair | None = None, page: int = 0, page_size: int = 200
    ) -> list[Order]:
        """Return open orders."""
        params = {}
        if pair:
            params["instrument_name"] = pair.exchange_name
        data = await self.api.post("private/get-open-orders", {"params": params}) or []
        return [
            Order.create_from_api(self.pairs[order["instrument_name"]], order)
            for order in data
        ]

    async def get_trades(
        self,
        pair: Pair | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int = 100,
    ) -> list[PrivateTrade]:
        """Return trades."""
        params = {"limit": limit}
        if pair:
            params["instrument_name"] = pair.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000
        data = await self.api.post("private/get-trades", {"params": params}) or []
        return [
            PrivateTrade.create_from_api(self.pairs[trade["instrument_name"]], trade)
            for trade in data
        ]

    async def get_fee_rate(self) -> FeeRate:
        """Account-wide fee tier and effective maker/taker rates.

        UNITS: rates are BASIS POINTS as the venue sends them (1 bp = 0.01%
        = 0.0001); ``FeeRate`` also exposes ``*_fraction`` = bps/10_000, the
        multiplier to apply to a notional. "24.2500000000" -> 24.25 bp ->
        0.002425. Measured live: spot maker 24.25 bp / taker 48.5 bp, which
        agrees with the rates this project's bot measures from its own
        fills - if those ever disagree, one of the two is wrong.

        These are the ACCOUNT TIER rates, not per-instrument rates: a
        per-instrument promo is invisible here. Measured on the same account
        in the same minute, this says 24.25 bp maker while
        ``get_instrument_fee_rate("CRO_USD")`` says 0 bp maker / 4 bp taker.
        To decide whether ONE pair is tradeable, use that one.

        Returns:
            FeeRate with both tiers and the four effective rates.

        Raises:
            ApiError: The call failed, or the payload is missing/absurd in
                any fee field. ``is_indeterminate`` is True - the fee is
                UNKNOWN, never 0. A fee decides whether a trade is allowed
                to make money, so an unreadable answer must stop the
                decision rather than silently price it at free.
        """
        data = await self.api.post("private/get-fee-rate", {"params": {}})
        return FeeRate.from_api(data)

    async def get_instrument_fee_rate(
        self, instrument: Pair | str
    ) -> InstrumentFeeRate:
        """Fee rate the venue actually charges for ONE instrument.

        Works for SPOT and DERIVATIVES alike (verified live with CRO_USD,
        BTC_USD and BTCUSD-PERP) - the endpoint is not restricted to one
        product type. Accepts a ``Pair`` or a raw venue instrument name such
        as ``"BTCUSD-PERP"``; perpetuals are not in ``Account.pairs``, so
        the string form is how you reach them.

        This is where promotional rates show up: CRO_USD measures 0 bp
        maker / 4 bp taker here while the account tier says 24.25/48.5, and
        BTC_USD measures 25/50 - ABOVE the discounted account rate. Neither
        endpoint is a proxy for the other; ask the one you need.

        Args:
            instrument: Pair, or the venue's instrument_name verbatim. The
                name is NOT case-folded or otherwise rewritten: an unknown
                name is a deterministic ``InvalidInstrumentError`` (code
                209) from the venue, and guessing a variant silently queries
                the fee of a different product.

        Returns:
            InstrumentFeeRate (maker/taker in bp, plus *_fraction).

        Raises:
            ValueError: Empty instrument name (local programming error).
            InvalidInstrumentError: Unknown instrument - code 209, NOT
                indeterminate: the venue confirmed there is no such thing.
            ApiError: Call failed, or the payload is missing a field or
                prices an instrument other than the one asked for
                (indeterminate - the fee is UNKNOWN).
        """
        name = instrument.exchange_name if isinstance(instrument, Pair) else instrument
        if not name:
            raise ValueError("instrument must be a Pair or a non-empty name")
        # The venue's contract is params.instrument_name. Send it under
        # `params` explicitly: with no `params` key at all the venue answers
        # 10004 BAD_REQUEST, and with an empty `params` it answers 209
        # INVALID_INSTRUMENT - both measured live. "10004 BAD_REQUEST on a
        # real instrument name" means the envelope is wrong, not the name.
        data = await self.api.post(
            "private/get-instrument-fee-rate", {"params": {"instrument_name": name}}
        )
        return InstrumentFeeRate.from_api(name, data)

    async def get_fee_credit_balances(
        self, page: int = 0, page_size: int = 200
    ) -> list[FeeCredit]:
        """Fee credit balances (promotional fee money), newest expiry first.

        Grouped by expiry date, sorted ascending by the venue. Amount units
        are the venue's own credit denomination - the published spec does
        not name a currency, so none is claimed here (see ``FeeCredit``).

        ``page``/``page_size`` are passed through (venue default 200, max
        200); the reply carries no total/next-page token, so paging is the
        caller's loop.

        Returns:
            list[FeeCredit]. AN EMPTY LIST IS A CONFIRMED ANSWER: the venue
            said this account holds no fee credits. (Measured live: an
            account paying 0 bp maker on CRO_USD returns [] here, which
            proves the 0 bp is an instrument-level promo and NOT a credit
            being consumed - so do not go looking for the explanation of a
            zero fee in this endpoint alone.)

        Raises:
            ApiError: Call failed, or ``fee_credits`` was absent/malformed.
                Absent is NOT read as empty: unknown is never absent.
        """
        data = await self.api.post(
            "private/get-fee-credit-balances",
            {"params": {"page": page, "page_size": page_size}},
        )
        method = "private/get-fee-credit-balances"
        if not isinstance(data, dict):
            raise ApiError(
                f"{method}: expected an object, got {type(data).__name__}",
                method=method,
            )
        credits = data.get("fee_credits")
        if credits is None:
            # Spec marks fee_credits required. Absent means the reply is not
            # the reply, so "no credits" would be a guess.
            raise ApiError(
                f"{method}: response has no 'fee_credits' - cannot tell "
                "whether the account holds credits",  # unknown != empty
                method=method,
            )
        if not isinstance(credits, list):
            raise ApiError(
                f"{method}: fee_credits={credits!r} is not a list", method=method
            )
        return [FeeCredit.from_api(credit) for credit in credits]

    async def create_order(
        self,
        pair: Pair,
        side: OrderSide,
        type_: OrderType,
        quantity: float,
        price: float = 0,
        force_type: OrderForceType | None = None,
        exec_flags: list[OrderExecFlag] | None = None,
        client_id: str | None = None,
        fee_instrument: Instrument | None = None,
    ) -> OrderKeys:
        """Create raw order with buy or sell side.

        Args:
            pair: Trading pair
            side: Order side (BUY/SELL)
            type_: Order type
            quantity: Order quantity
            price: Order price (for limit orders)
            force_type: Time in force
            exec_flags: Execution flags
            client_id: Client order ID (auto-generated if not provided)
            fee_instrument: Fee instrument (defaults to quote currency)

        Returns:
            OrderKeys with order_id and client_id
        """
        # Auto-generate client_id if not provided
        if client_id is None:
            client_id = uuid4().hex
        else:
            validate_client_id(client_id, "client_id")

        data = {
            "instrument_name": pair.exchange_name,
            "side": side.value,
            "type": type_.value,
            "client_oid": client_id,
        }

        if force_type:
            data["time_in_force"] = force_type.value

        if exec_flags:
            data["exec_inst"] = [flag.value for flag in exec_flags]

        # Use provided fee_instrument or default to pair's quote currency
        if fee_instrument:
            data["fee_instrument_name"] = fee_instrument.exchange_name
        else:
            # Default to quote currency (e.g., USD for CRO_USD)
            data["fee_instrument_name"] = pair.quote_instrument.exchange_name

        old_quantity = quantity
        precision = pair.quantity_precision
        if type_ == OrderType.MARKET and side == OrderSide.BUY:
            precision = pair.price_precision
        qty_str = "{:.{}f}".format(quantity, precision)
        if old_quantity and not float(qty_str):
            raise ValueError(
                f"Your quantity: {old_quantity} is less then "
                f"accepted precision: {qty_str} "
                f"for pair: {pair} {type_}, {side}"
            )
        if type_ == OrderType.MARKET and side == OrderSide.BUY:
            data["notional"] = qty_str
            notional_value = float(qty_str)
        else:
            data["quantity"] = qty_str
            if type_ == OrderType.MARKET:
                # Fetch price for market sell orders (for notional validation
                # only). No price => cannot size the order: fail locally,
                # deterministically, BEFORE anything reaches the exchange.
                market_price = await self.market.get_price(pair)
                if market_price is None:
                    raise ValueError(
                        f"No market price for {pair} - cannot validate "
                        "market order notional"
                    )
                notional_value = float(qty_str) * market_price
            else:
                notional_value = float(qty_str) * price

        # Validate order notional against pair limits
        if not pair.validate_order_notional(notional_value):
            raise ValueError(
                f"Order notional ${notional_value:.2f} outside limits "
                f"[${pair.min_order_notional_usd}, ${pair.max_order_notional_usd}] "
                f"for pair {pair.name}"
            )

        if client_id:
            data["client_oid"] = client_id

        if price:
            if type_ == OrderType.MARKET:
                raise ValueError("Error, MARKET execution do not support price value")
            data["price"] = "{:.{}f}".format(price, pair.price_precision)

        resp = await self.api.post("private/create-order", {"params": data})
        self._recently_created[client_id] = time.monotonic()
        return OrderKeys(id=resp["order_id"], client_id=client_id)

    async def buy_limit(
        self,
        pair: Pair,
        quantity: float,
        price: float,
        force_type: OrderForceType | None = None,
        exec_flags: list[OrderExecFlag] | None = None,
        client_id: str | None = None,
        fee_instrument: Instrument | None = None,
    ) -> OrderKeys:
        """Buy limit order with optional fee instrument.

        Returns:
            OrderKeys with order_id and client_id
        """
        return await self.create_order(
            pair,
            OrderSide.BUY,
            OrderType.LIMIT,
            quantity,
            price,
            force_type,
            exec_flags,
            client_id,
            fee_instrument,
        )

    async def sell_limit(
        self,
        pair: Pair,
        quantity: float,
        price: float,
        force_type: OrderForceType | None = None,
        exec_flags: list[OrderExecFlag] | None = None,
        client_id: str | None = None,
        fee_instrument: Instrument | None = None,
    ) -> OrderKeys:
        """Sell limit order with optional fee instrument.

        Returns:
            OrderKeys with order_id and client_id
        """
        return await self.create_order(
            pair,
            OrderSide.SELL,
            OrderType.LIMIT,
            quantity,
            price,
            force_type,
            exec_flags,
            client_id,
            fee_instrument,
        )

    async def wait_for_order(
        self,
        statuses: tuple[OrderStatus, ...],
        *,
        order_id: str | None = None,
        client_order_id: str | None = None,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> Order:
        """Poll an order until it reaches one of the required statuses.

        Confirmed-absent answers keep the wait going (a just-created order
        may briefly be unreadable); only the deadline ends it.

        Args:
            statuses: Accepted terminal (or other) statuses
            order_id: Exchange order ID (one of the ids is required)
            client_order_id: Client order ID
            timeout: Max seconds to wait
            poll_interval: Seconds between polls

        Returns:
            The order once its status is in `statuses`.

        Raises:
            WaitNotConfirmedError: Timeout - INDETERMINATE, reconcile later.
        """
        if not order_id and not client_order_id:
            raise ValueError("Must provide either order_id or client_order_id")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        last = "unknown"
        while True:
            order = await self.get_order(
                order_id=order_id,
                client_order_id=client_order_id,
                ignore_cache=True,
            )
            if order is None:
                last = "absent"
            else:
                last = str(order.status)
                if order.status in statuses:
                    return order
            if loop.time() >= deadline:
                raise WaitNotConfirmedError(
                    f"Order {client_order_id or order_id!r} not in "
                    f"{[s.name for s in statuses]} within {timeout}s "
                    f"(last: {last})"
                )
            await asyncio.sleep(poll_interval)

    async def wait_for_status(
        self, order_id: str, statuses: tuple[OrderStatus, ...], delay: float = 0.1
    ) -> None:
        """Wait for order status.

        Deprecated: use ``wait_for_order`` (explicit timeout, typed
        indeterminate error, absent-tolerant polling).
        """
        warnings.warn(
            "wait_for_status is deprecated; use wait_for_order()",
            DeprecationWarning,
            stacklevel=2,
        )
        await self.wait_for_order(
            statuses,
            order_id=order_id,
            timeout=30.0,
            poll_interval=delay,
        )

    async def buy_market(
        self,
        pair: Pair,
        spend: float,
        wait_for_fill: bool = False,
        fee_instrument: Instrument | None = None,
    ) -> OrderKeys:
        """Buy market order with optional fee instrument.

        Returns:
            OrderKeys with order_id and client_id
        """
        result = await self.create_order(
            pair, OrderSide.BUY, OrderType.MARKET, spend, fee_instrument=fee_instrument
        )

        if wait_for_fill:
            await self.wait_for_order(
                (
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.EXPIRED,
                    OrderStatus.REJECTED,
                ),
                order_id=result.id,
            )

        return result

    async def sell_market(
        self,
        pair: Pair,
        quantity: float,
        wait_for_fill: bool = False,
        fee_instrument: Instrument | None = None,
    ) -> OrderKeys:
        """Sell market order with optional fee instrument.

        Returns:
            OrderKeys with order_id and client_id
        """
        result = await self.create_order(
            pair,
            OrderSide.SELL,
            OrderType.MARKET,
            quantity,
            fee_instrument=fee_instrument,
        )

        if wait_for_fill:
            await self.wait_for_order(
                (
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.EXPIRED,
                    OrderStatus.REJECTED,
                ),
                order_id=result.id,
            )

        return result

    def _cache_order(self, order: Order) -> None:
        """Upsert an observed order. Terminal entries are final and immortal."""
        existing = self.order_cache.get(order.client_id)
        if existing is not None and existing.is_terminal and not order.is_terminal:
            return  # a live snapshot never overwrites a terminal truth
        self.order_cache[order.client_id] = order
        if order.is_terminal:
            self._orders_seen.pop(order.client_id, None)
        else:
            self._orders_seen[order.client_id] = time.monotonic()

    def _cached_order(self, client_order_id: str) -> Order | None:
        """Fresh cached order, or None (expired entries are dropped)."""
        order = self.order_cache.get(client_order_id)
        if order is None:
            return None
        seen = self._orders_seen.get(client_order_id)
        if seen is None:  # terminal: immortal
            return order
        if time.monotonic() - seen <= self.orders_ttl:
            return order
        del self.order_cache[client_order_id]
        self._orders_seen.pop(client_order_id, None)
        return None

    async def get_order(
        self,
        order_id: str | None = None,
        client_order_id: str | None = None,
        updates: dict[str, Order] | None = None,
        ignore_cache: bool = False,
    ) -> Order | None:
        """Get order info by order_id or client_order_id.

        Cache-backed for client_order_id lookups. Resolution priority:
        caller-provided ``updates`` (e.g. from a websocket feed) > fresh
        cache > API. Terminal orders are cached forever; live orders for
        ``orders_ttl`` seconds (0 disables caching).

        Returns:
            The Order, or None if the exchange CONFIRMS the order is absent
            (empty result / code 40401). None is a definite answer; unknown
            outcomes raise. Endpoints where "not found" is an error reply
            (cancel, amend) still raise OrderNotFoundError.

        Raises:
            ValueError: If neither order_id nor client_order_id is provided
            ApiError: Just-created order unreadable, or lookup failed -
                outcome UNKNOWN, must be reconciled later (indeterminate)
        """
        if not order_id and not client_order_id:
            raise ValueError("Must provide either order_id or client_order_id")

        if updates and client_order_id and client_order_id in updates:
            order = updates[client_order_id]
            self._cache_order(order)
            return order

        if client_order_id and not ignore_cache:
            cached = self._cached_order(client_order_id)
            if cached is not None:
                return cached

        params = {}
        if order_id:
            params["order_id"] = str(order_id)
        if client_order_id:
            params["client_oid"] = client_order_id

        try:
            data = await self.api.post(
                "private/get-order-detail",
                {"params": params},
            )
        except OrderNotFoundError:
            # Coded 40401 is the same confirmed-absent answer as an empty
            # result; get_order reports absence as None.
            data = None
        if not data:
            # Structured success with empty result - normally "not there".
            # Exception: an order created moments ago may not be readable
            # yet. Treating that race as absence would orphan a live order.
            if client_order_id:
                self.order_cache.pop(client_order_id, None)
                self._orders_seen.pop(client_order_id, None)
                created = self._recently_created.get(client_order_id)
                if (
                    created is not None
                    and time.monotonic() - created < self.create_race_guard
                ):
                    raise ApiError(
                        f"Order {client_order_id!r} unreadable right after "
                        "creation - state unknown, reconcile later",
                        method="private/get-order-detail",
                    )
            return None

        order = Order.create_from_api(
            self.pairs[data["instrument_name"]],
            data,
            # data["trade_list"],
            [],
        )
        self._cache_order(order)
        return order

    async def cancel_order(
        self,
        pair: Pair,
        client_order_id: str | None = None,
        check_status: bool = False,
    ) -> tuple[str, str | None]:
        """Cancel order by client_order_id.

        Args:
            pair: Trading pair
            client_order_id: Client order ID (client_oid) - auto-generated if not provided
            check_status: If True, wait for order to be canceled

        Returns:
            Tuple of (order_id, client_oid) from API response

        Raises:
            ValueError: If client_order_id is not provided
        """
        if not client_order_id:
            raise ValueError("Must provide client_order_id")

        params = {
            "instrument_name": pair.exchange_name,
            "client_oid": client_order_id,
        }

        resp = await self.api.post(
            "private/cancel-order",
            {"params": params},
        )
        # Invalidate only - cancel confirms the request, not the final
        # status. The terminal transition must be observed, never assumed.
        self.order_cache.pop(client_order_id, None)
        self._orders_seen.pop(client_order_id, None)
        # A cancel proves the order existed - later absence is expected truth,
        # not a create race. Release the guard.
        self._recently_created.pop(client_order_id, None)

        # API response has order_id and client_oid at top level in result
        returned_order_id = resp.get("result", {}).get(
            "order_id", resp.get("order_id", client_order_id or "")
        )
        returned_client_oid = resp.get("result", {}).get(
            "client_oid", resp.get("client_oid")
        )

        if not check_status:
            return returned_order_id, returned_client_oid

        await self.wait_for_order(
            (OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED),
            order_id=returned_order_id,
        )
        return returned_order_id, returned_client_oid

    async def cancel_order_and_wait(
        self,
        pair: Pair,
        client_order_id: str,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Cancel an order and confirm it is no longer live.

        All exchange-side races are resolved here: an already-terminal or
        confirmed-absent order needs no cancel; a cancel rejected as
        not-active (316) re-queries once, because racing into
        FILLED/CANCELED/absent is a confirmed outcome, not an error.

        Returns:
            True: CONFIRMED not live - cancel reached terminal status, the
                order was already terminal, or the exchange confirmed it
                absent. Safe to treat as cancelled.
            False: cancellation NOT confirmed - cancel timed out (it may
                still have landed after the last poll) or the order is
                confirmed still live. Never read False as "cancelled".

        Raises:
            ApiError: Cancel or lookup failed indeterminately - outcome
                unknown, reconcile later.
        """
        order = await self.get_order(client_order_id=client_order_id, ignore_cache=True)
        if order is None or order.is_terminal:
            return True

        try:
            await self.cancel_order(pair, client_order_id=client_order_id)
        except OrderNotActiveError:
            # Cancel raced a status change - re-query to learn the outcome.
            order = await self.get_order(
                client_order_id=client_order_id, ignore_cache=True
            )
            return order is None or order.is_terminal
        except OrderNotFoundError:
            return True

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            order = await self.get_order(
                client_order_id=client_order_id, ignore_cache=True
            )
            if order is None or order.is_terminal:
                return True
            await asyncio.sleep(poll_interval)
        return False

    async def resolve_stuck_order(
        self,
        pair: Pair,
        order: Order,
        stuck_after: float = 300.0,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Resolve a possibly-stuck resting order (shadow-order mechanic).

        An order is stuck when it sits in NEW (never activated) for longer
        than ``stuck_after`` seconds AND cancel-and-wait cannot confirm its
        removal. Anything else (healthy, terminal, NEW but still fresh, or
        successfully cancelled) is clear to proceed.

        Returns:
            True: the order is STUCK (cancel attempted, not confirmed).
            False: clear to proceed - no cancellation was needed or the
                stuck order was successfully removed.

        Raises:
            ApiError: cancel or lookup failed indeterminately - unknown is
                never reported as stuck or clear; reconcile later.
        """
        if order.status != OrderStatus.NEW:
            return False
        if time.time() - order.created_at <= stuck_after:
            return False
        return not await self.cancel_order_and_wait(
            pair, order.client_id, timeout, poll_interval
        )

    async def update_order(
        self,
        pair: Pair,
        order_id: str | None = None,
        client_id: str | None = None,
        new_price: float | None = None,
        new_quantity: float | None = None,
        new_client_id: str | None = None,
    ) -> OrderKeys:
        """Amend/update an existing order.

        Note: Amend order performs cancel and then create behind the scene.
        The new order will lose queue priority, except if the amend is only
        to amend down order quantity.

        API requires BOTH new_price and new_quantity to be provided.
        Both values must meet the pair's minimum order notional requirement.

        Args:
            pair: Trading pair
            order_id: Exchange order ID to update
            client_id: Client order ID to find the order (orig_client_oid)
            new_price: New price for the order (required)
            new_quantity: New quantity for the order (required)
            new_client_id: New client order ID for the amended order (optional, auto-generated if not provided)

        Returns:
            OrderKeys with order_id and client_oid from API response

        Raises:
            ValueError: If neither order_id nor client_id is provided
            ValueError: If new_price or new_quantity is not provided
            ValueError: If new_price or new_quantity doesn't meet pair minimums
        """
        if not order_id and not client_id:
            raise ValueError("Must provide either order_id or client_id")
        if new_price is None or new_quantity is None:
            raise ValueError("Must provide both new_price and new_quantity")

        # Validate that new values meet pair minimums
        new_notional = new_price * new_quantity
        if new_notional < pair.min_order_notional_usd:
            raise ValueError(
                f"New order notional ${new_notional:.2f} below minimum "
                f"${pair.min_order_notional_usd:.2f} for pair {pair.name}"
            )

        # Auto-generate new_client_id if not provided
        if new_client_id is None:
            new_client_id = uuid4().hex
        else:
            validate_client_id(new_client_id, "new_client_id")

        params = {
            "instrument_name": pair.exchange_name,
            "client_oid": new_client_id,  # New client OID for the amended order
        }

        if order_id:
            params["order_id"] = str(order_id)
        elif client_id:
            params["orig_client_oid"] = client_id

        if new_price is not None:
            params["new_price"] = "{:.{}f}".format(new_price, pair.price_precision)
        if new_quantity is not None:
            params["new_quantity"] = "{:.{}f}".format(
                new_quantity, pair.quantity_precision
            )

        resp = await self.api.post(
            "private/amend-order",
            {"params": params},
        )
        # Amend = cancel + create: the old order goes terminal and the
        # successor exists in an unknown state. Invalidate both, guess neither.
        if client_id:
            self.order_cache.pop(client_id, None)
            self._orders_seen.pop(client_id, None)
            # Amend resolves the predecessor: it existed and is now replaced.
            self._recently_created.pop(client_id, None)
        self.order_cache.pop(new_client_id, None)
        self._orders_seen.pop(new_client_id, None)

        # API response has order_id and client_oid in result
        returned_order_id = resp.get("result", {}).get(
            "order_id", resp.get("order_id", "")
        )
        returned_client_oid = resp.get("result", {}).get(
            "client_oid", resp.get("client_oid", "")
        )

        return OrderKeys(id=returned_order_id, client_id=returned_client_oid)

    async def cancel_open_orders(self, pair: Pair | None = None) -> None:
        """Cancel all open orders."""
        data = {}
        if pair:
            data = {"params": {"instrument_name": pair.exchange_name}}
        await self.api.post(
            "private/cancel-all-orders",
            data,
        )

    async def listen_balances(self) -> tp.AsyncIterator[Balance]:
        async for data in self.api.listen("user", "user.balance", sign=True):
            data = data["data"][0]
            yield Balance.from_api(data)

    async def listen_orders(self, pair: Pair) -> tp.AsyncIterator[Order]:
        async for data in self.api.listen(
            "user", f"user.order.{pair.exchange_name}", sign=True
        ):
            for order in data.get("data", []):
                yield Order.create_from_api(
                    self.pairs[order["instrument_name"]],
                    order,
                )
