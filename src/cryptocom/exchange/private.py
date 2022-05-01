import asyncio
from typing import Dict, List

from .api import ApiError, ApiProvider
from .market import Exchange
from .structs import (
    Balance,
    Coin,
    Deposit,
    DepositStatus,
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

    async def get_balance(self) -> Dict[Coin, Balance]:
        """Return balance."""
        data = await self.api.post("private/get-account-summary")
        return {
            Coin(bal["currency"]): Balance.from_api(bal)
            for bal in data["accounts"]
        }

    async def get_deposit_history(
        self,
        coin: Coin,
        start_ts: int = None,
        end_ts: int = None,
        status: DepositStatus = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Deposit]:
        """Return all history withdrawals."""
        params = {"page_size": page_size, "page": page}
        if coin:
            params["currency"] = coin.name
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
        coin: Coin,
        start_ts: int = None,
        end_ts: int = None,
        status: WithdrawalStatus = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Withdrawal]:
        """Return all history for withdrawal transactions."""
        params = {"page_size": page_size, "page": page}
        if coin:
            params["currency"] = coin.name
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
        coin: Coin,
        start_ts: int = None,
        end_ts: int = None,
        page: int = 0,
        page_size: int = 20,
    ) -> List[Interest]:
        """Return all history interest."""
        params = {"page_size": page_size, "page": page}
        if coin:
            params["currency"] = coin.name
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
        page: int = 0,
        page_size: int = 200,
    ) -> List[Order]:
        """Return all history orders."""
        params = {"page_size": page_size, "page": page}
        if pair:
            params["instrument_name"] = pair.name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000

        data = (
            await self.api.post(
                "private/get-order-history", {"params": params}
            )
            or {}
        )
        return [
            Order.create_from_api(self.pairs[order["instrument_name"]], order)
            for order in data.get("order_list") or []
        ]

    async def get_open_orders(
        self, pair: Pair = None, page: int = 0, page_size: int = 200
    ) -> List[Order]:
        """Return open orders."""
        params = {"page_size": page_size, "page": page}
        if pair:
            params["instrument_name"] = pair.name
        data = await self.api.post(
            "private/get-open-orders", {"params": params}
        )
        return [
            Order.create_from_api(self.pairs[order["instrument_name"]], order)
            for order in data.get("order_list") or []
        ]

    async def get_trades(
        self,
        pair: Pair = None,
        start_ts: int = None,
        end_ts: int = None,
        page: int = 0,
        page_size: int = 200,
    ) -> List[PrivateTrade]:
        """Return trades."""
        params = {"page_size": page_size, "page": page}
        if pair:
            params["instrument_name"] = pair.name
        if start_ts:
            params["start_ts"] = int(start_ts) * 1000
        if end_ts:
            params["end_ts"] = int(end_ts) * 1000
        data = await self.api.post("private/get-trades", {"params": params})
        return [
            PrivateTrade.create_from_api(
                self.pairs[trade["instrument_name"]], trade
            )
            for trade in data.get("trade_list") or []
        ]

    async def create_order(
        self,
        pair: Pair,
        side: OrderSide,
        type_: OrderType,
        quantity: float,
        price: float = 0,
        force_type: OrderForceType = OrderForceType.GOOD_TILL_CANCEL,
        exec_type: OrderExecType = OrderExecType.MARKET,
        client_id: int = None,
    ) -> int:
        """Create raw order with buy or sell side."""
        data = {
            "instrument_name": pair.name,
            "side": side.value,
            "type": type_.value,
        }
        data["time_in_force"] = force_type.value
        data["exec_inst"] = exec_type.value

        quantity = "{:.{}f}".format(quantity, pair.quantity_precision)
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
        return int(resp["order_id"])

    async def buy_limit(
        self,
        pair: Pair,
        quantity: float,
        price: float,
        force_type: OrderForceType = OrderForceType.GOOD_TILL_CANCEL,
        exec_type: OrderExecType = OrderExecType.MARKET,
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
        )

    async def sell_limit(
        self,
        pair: Pair,
        quantity: float,
        price: float,
        force_type: OrderForceType = OrderForceType.GOOD_TILL_CANCEL,
        exec_type: OrderExecType = OrderExecType.MARKET,
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
    ) -> int:
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
    ) -> int:
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

    async def get_order(self, order_id: int) -> Order:
        """Get order info."""
        order_info = {}
        retries = 0

        while True:
            data = await self.api.post(
                "private/get-order-detail",
                {"params": {"order_id": str(order_id)}},
            )
            order_info = data.get("order_info", {})
            if not order_info:
                if retries < 10:
                    await asyncio.sleep(0.5)
                    retries += 1
                else:
                    raise ApiError(f"No order info found for id: {order_id}")
            else:
                break

        return Order.create_from_api(
            self.pairs[order_info["instrument_name"]],
            order_info,
            data["trade_list"],
        )

    async def cancel_order(
        self, order_id: int, pair: Pair, check_status=False
    ) -> None:
        """Cancel order."""
        await self.api.post(
            "private/cancel-order",
            {"params": {"order_id": order_id, "instrument_name": pair.name}},
        )

        if not check_status:
            return

        await self.wait_for_status(
            order_id,
            (OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED),
        )

    async def cancel_open_orders(self, pair: Pair) -> None:
        """Cancel all open orders."""
        await self.api.post(
            "private/cancel-all-orders",
            {"params": {"instrument_name": pair.name}},
        )

    async def listen_balance(self) -> Balance:
        async for data in self.api.listen("user", "user.balance", sign=True):
            for bal in data.get("data", []):
                yield Balance(
                    total=bal["balance"],
                    available=bal["available"],
                    in_orders=bal["order"],
                    in_stake=bal["stake"],
                    coin=Coin(bal["currency"]),
                )

    async def listen_orders(self, pair: Pair) -> Order:
        async for data in self.api.listen(
            "user", f"user.order.{pair.name}", sign=True
        ):
            for order in data.get("data", []):
                yield Order.create_from_api(
                    self.pairs[data["instrument_name"]], order
                )
