import asyncio
import logging
from dataclasses import dataclass
from uuid import uuid4
from typing import Any

from .api import ApiError, ApiProvider
from .market import Market
from .structs import (
    Balance,
    DefaultPairDict,
    Deposit,
    DepositStatus,
    Instrument,
    InstrumentBalance,
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

    def _validate_client_id(
        self, client_id: str | None, param_name: str = "client_id"
    ) -> None:
        """Validate client ID against API constraints.

        Args:
            client_id: The client ID to validate
            param_name: Name of the parameter for error messages

        Raises:
            TypeError: If client_id is not a string
            ValueError: If client_id is empty or exceeds 36 characters
        """
        if client_id is None:
            return

        if not isinstance(client_id, str):
            raise TypeError(f"{param_name} must be a string")
        if len(client_id) == 0:
            raise ValueError(f"{param_name} cannot be empty")
        if len(client_id) > 36:
            raise ValueError(
                f"{param_name} must be <= 36 characters, got {len(client_id)}"
            )

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        from_env: bool = False,
        market: Market | None = None,
        api: ApiProvider | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if not api and not (api_key and api_secret) and not from_env:
            raise ValueError("Pass ApiProvider or api_key with api_secret or from_env")
        self.api = api or ApiProvider(
            api_key=api_key, api_secret=api_secret, from_env=from_env
        )
        self.logger = logger or logging.getLogger(__name__)
        self.market = market or Market(api)
        self.pairs = self.market.pairs

    async def sync_pairs(self):
        await self.market.sync_pairs()
        self.pairs = self.market.pairs

    async def get_balance(self) -> dict[Instrument, InstrumentBalance]:
        """Return balance."""
        data = (await self.api.post("private/user-balance")) or []
        if not data:
            return {}
        balance = Balance.from_api(data[0])
        # Return dict mapping instrument to its balance
        # InstrumentBalance inherits from Instrument, so we can use it directly as key
        return {inst: inst for inst in balance}

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
            self._validate_client_id(client_id, "client_id")

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
        quantity = "{:.{}f}".format(quantity, precision)
        if old_quantity and not float(quantity):
            raise ValueError(
                f"Your quantity: {old_quantity} is less then "
                f"accepted precision: {quantity} "
                f"for pair: {pair} {type_}, {side}"
            )
        if type_ == OrderType.MARKET and side == OrderSide.BUY:
            data["notional"] = quantity
            notional_value = float(quantity)
        else:
            data["quantity"] = quantity
            if type_ == OrderType.MARKET:
                # Fetch price for market sell orders (for notional validation only)
                market_price = await self.market.get_price(pair)
                notional_value = float(quantity) * market_price
            else:
                notional_value = float(quantity) * price

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

    async def wait_for_status(
        self, order_id: str, statuses: tuple[OrderStatus, ...], delay: int = 0.1
    ) -> None:
        """Wait for order status."""
        order = await self.get_order(order_id)

        for _ in range(self.api.retries):
            if order.status in statuses:
                break

            await asyncio.sleep(delay)
            order = await self.get_order(order_id)

        if order.status not in statuses:
            raise ApiError(f"Status not changed for: {order}, must be in: {statuses}")

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
            await self.wait_for_status(
                result.id,
                (
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.EXPIRED,
                    OrderStatus.REJECTED,
                ),
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
            await self.wait_for_status(
                result.id,
                (
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.EXPIRED,
                    OrderStatus.REJECTED,
                ),
            )

        return result

    async def get_order(
        self, order_id: str | None = None, client_order_id: str | None = None
    ) -> Order:
        """Get order info by order_id or client_order_id.

        Args:
            order_id: Exchange order ID
            client_order_id: Client order ID (client_oid)

        Raises:
            ValueError: If neither order_id nor client_order_id is provided
            ApiError: If order not found
        """
        if not order_id and not client_order_id:
            raise ValueError("Must provide either order_id or client_order_id")

        params = {}
        if order_id:
            params["order_id"] = str(order_id)
        if client_order_id:
            params["client_oid"] = client_order_id

        data = await self.api.post(
            "private/get-order-detail",
            {"params": params},
        )
        if not data:
            raise ApiError("No order data")

        return Order.create_from_api(
            self.pairs[data["instrument_name"]],
            data,
            # data["trade_list"],
            [],
        )

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

        # API response has order_id and client_oid at top level in result
        returned_order_id = resp.get("result", {}).get(
            "order_id", resp.get("order_id", client_order_id or "")
        )
        returned_client_oid = resp.get("result", {}).get(
            "client_oid", resp.get("client_oid")
        )

        if not check_status:
            return returned_order_id, returned_client_oid

        await self.wait_for_status(
            returned_order_id,
            (OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED),
        )
        return returned_order_id, returned_client_oid

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
            self._validate_client_id(new_client_id, "new_client_id")

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

        # API response has order_id and client_oid in result
        returned_order_id = resp.get("result", {}).get(
            "order_id", resp.get("order_id", "")
        )
        returned_client_oid = resp.get("result", {}).get(
            "client_oid", resp.get("client_oid", "")
        )

        return OrderKeys(id=returned_order_id, client_id=returned_client_oid)

    async def cancel_open_orders(self, pair: Pair = None) -> None:
        """Cancel all open orders."""
        data = {}
        if pair:
            data = {"params": {"instrument_name": pair.exchange_name}}
        await self.api.post(
            "private/cancel-all-orders",
            data,
        )

    async def listen_balances(self) -> Balance:
        async for data in self.api.listen("user", "user.balance", sign=True):
            data = data["data"][0]
            yield Balance.from_api(data)

    async def listen_orders(self, pair: Pair) -> Order:
        async for data in self.api.listen(
            "user", f"user.order.{pair.exchange_name}", sign=True
        ):
            for order in data.get("data", []):
                yield Order.create_from_api(
                    self.pairs[order["instrument_name"]],
                    order,
                )
