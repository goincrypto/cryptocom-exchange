import asyncio
from typing import Dict, List

from .api import ApiError, ApiProvider
from .market import Exchange
from .structs import (
    Balance,
    Deposit,
    DepositStatus,
    Instrument,
    Interest,
    Order,
    OrderExecType,
    OrderForceType,
    OrderSide,
    OrderStatus,
    OrderType,
    Pair,
    PrivateTrade,
    Withdrawal,
    WithdrawalStatus,
)


class Account:
    """Provides access to account actions and data. Balance, trades, orders."""

    def __init__(
        self,
        *,
        api_key: str = "",
        api_secret: str = "",
        from_env: bool = False,
        exchange: Exchange = None,
        api: ApiProvider = None,
    ):
        if not api and not (api_key and api_secret) and not from_env:
            raise ValueError(
                "Pass ApiProvider or api_key with api_secret or from_env"
            )
        self.api = api or ApiProvider(
            api_key=api_key, api_secret=api_secret, from_env=from_env
        )
        self.exchange = exchange or Exchange(api)
        self.pairs = self.exchange.pairs

    async def sync_pairs(self):
        await self.exchange.sync_pairs()
        self.pairs = self.exchange.pairs

    async def get_balance(self) -> Dict[Instrument, Balance]:
        """Return balance."""
        data = (await self.api.post("private/user-balance"))[0]
        return Balance.from_api(data)

    async def get_accounts(self) -> Dict:
        data = await self.api.post("private/get-accounts")
        return data

    async def get_subaccount_balances(self):
        return await self.api.post(
            "private/get-subaccount-balances", {"params": {}}
        )

    async def get_balance_history(self):
        return await self.api.post(
            "private/user-balance-history", {"params": {}}
        )

    async def get_deposit_history(
        self,
        instrument: Instrument = None,
        start_ts: int = None,
        end_ts: int = None,
        status: DepositStatus = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Deposit]:
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
            await self.api.post(
                "private/get-deposit-history", {"params": params}
            )
            or {}
        )
        return [
            Deposit.create_from_api(trx)
            for trx in data.get("deposit_list") or []
        ]

    async def get_withdrawal_history(
        self,
        instrument: Instrument,
        start_ts: int = None,
        end_ts: int = None,
        status: WithdrawalStatus = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Withdrawal]:
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
            await self.api.post(
                "private/get-withdrawal-history", {"params": params}
            )
            or {}
        )
        return [
            Withdrawal.create_from_api(trx)
            for trx in data.get("withdrawal_list") or []
        ]

    async def get_interest_history(
        self,
        instrument: Instrument,
        start_ts: int = None,
        end_ts: int = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Interest]:
        """Return all history interest."""
        params = {"page_size": page_size, "page": page}
        if instrument:
            params["currency"] = instrument.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000

        data = (
            await self.api.post(
                "private/margin/get-order-history", {"params": params}
            )
            or {}
        )
        return [
            Interest.create_from_api(interest)
            for interest in data.get("list") or []
        ]

    async def get_orders_history(
        self,
        pair: Pair = None,
        start_ts: int = None,
        end_ts: int = None,
        limit: int = 100,
    ) -> List[Order]:
        """Return all history orders."""
        params = {"limit": limit}
        if pair:
            params["instrument_name"] = pair.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000

        data = await self.api.post(
            "private/get-order-history", {"params": params}
        )
        return [
            Order.create_from_api(self.pairs[order["instrument_name"]], order)
            for order in data
        ]

    async def get_open_orders(
        self, pair: Pair = None, page: int = 0, page_size: int = 200
    ) -> List[Order]:
        """Return open orders."""
        params = {}
        if pair:
            params["instrument_name"] = pair.exchange_name
        data = await self.api.post(
            "private/get-open-orders", {"params": params}
        )
        return [
            Order.create_from_api(self.pairs[order["instrument_name"]], order)
            for order in data
        ]

    async def get_trades(
        self,
        pair: Pair = None,
        start_ts: int = None,
        end_ts: int = None,
        limit: int = 100,
    ) -> List[PrivateTrade]:
        """Return trades."""
        params = {"limit": limit}
        if pair:
            params["instrument_name"] = pair.exchange_name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000
        data = await self.api.post("private/get-trades", {"params": params})
        return [
            PrivateTrade.create_from_api(
                self.pairs[trade["instrument_name"]], trade
            )
            for trade in data
        ]

    async def create_order(
        self,
        pair: Pair,
        side: OrderSide,
        type_: OrderType,
        quantity: float,
        price: float = 0,
        force_type: OrderForceType = None,
        exec_type: OrderExecType = None,
        client_id: int = None,
    ) -> str:
        """Create raw order with buy or sell side."""
        data = {
            "instrument_name": pair.exchange_name,
            "side": side.value,
            "type": type_.value,
        }

        if force_type:
            data["time_in_force"] = force_type.value

        if exec_type:
            data["exec_inst"] = [exec_type.value]

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
        else:
            data["quantity"] = quantity

        if client_id:
            data["client_oid"] = str(client_id)

        if price:
            if type_ == OrderType.MARKET:
                raise ValueError(
                    "Error, MARKET execution do not support price value"
                )
            data["price"] = "{:.{}f}".format(price, pair.price_precision)

        resp = await self.api.post("private/create-order", {"params": data})
        return resp["order_id"]

    async def buy_limit(
        self,
        pair: Pair,
        quantity: float,
        price: float,
        force_type: OrderForceType = None,
        exec_type: OrderExecType = None,
        client_id: int = None,
    ) -> int:
        """Buy limit order."""
        return await self.create_order(
            pair,
            OrderSide.BUY,
            OrderType.LIMIT,
            quantity,
            price,
            force_type,
            exec_type,
            client_id,
        )

    async def sell_limit(
        self,
        pair: Pair,
        quantity: float,
        price: float,
        force_type: OrderForceType = None,
        exec_type: OrderExecType = None,
        client_id: int = None,
    ) -> int:
        """Sell limit order."""
        return await self.create_order(
            pair,
            OrderSide.SELL,
            OrderType.LIMIT,
            quantity,
            price,
            force_type,
            exec_type,
            client_id,
        )

    async def wait_for_status(
        self, order_id: int, statuses, delay: int = 0.1
    ) -> None:
        """Wait for order status."""
        order = await self.get_order(order_id)

        for _ in range(self.api.retries):
            if order.status in statuses:
                break

            await asyncio.sleep(delay)
            order = await self.get_order(order_id)

        if order.status not in statuses:
            raise ApiError(
                f"Status not changed for: {order}, must be in: {statuses}"
            )

    async def buy_market(
        self, pair: Pair, spend: float, wait_for_fill=False
    ) -> str:
        """Buy market order."""
        order_id = await self.create_order(
            pair, OrderSide.BUY, OrderType.MARKET, spend
        )
        if wait_for_fill:
            await self.wait_for_status(
                order_id,
                (
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.EXPIRED,
                    OrderStatus.REJECTED,
                ),
            )

        return order_id

    async def sell_market(
        self, pair: Pair, quantity: float, wait_for_fill=False
    ) -> str:
        """Sell market order."""
        order_id = await self.create_order(
            pair, OrderSide.SELL, OrderType.MARKET, quantity
        )

        if wait_for_fill:
            await self.wait_for_status(
                order_id,
                (
                    OrderStatus.FILLED,
                    OrderStatus.CANCELED,
                    OrderStatus.EXPIRED,
                    OrderStatus.REJECTED,
                ),
            )

        return order_id

    async def get_order(self, order_id: str) -> Order:
        """Get order info."""
        data = await self.api.post(
            "private/get-order-detail",
            {"params": {"order_id": str(order_id)}},
        )

        return Order.create_from_api(
            self.pairs[data["instrument_name"]],
            data,
            # data["trade_list"],
            [],
        )

    async def cancel_order(
        self, order_id: int, pair: Pair, check_status=False
    ) -> None:
        """Cancel order."""
        await self.api.post(
            "private/cancel-order",
            {
                "params": {
                    "order_id": order_id,
                    "instrument_name": pair.exchange_name,
                }
            },
        )

        if not check_status:
            return

        await self.wait_for_status(
            order_id,
            (OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED),
        )

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
                    self.pairs[data["instrument_name"]], order
                )
