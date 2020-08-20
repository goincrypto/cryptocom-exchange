import asyncio

from typing import List

from .api import ApiProvider, ApiError
from .structs import (
    Pair, OrderSide, OrderStatus, OrderType, Period, Candle, Trade,
    OrderInBook, OrderBook
)


class Exchange:
    """Interface to base exchange methods."""
    def __init__(self, api: ApiProvider = None):
        self.api = api or ApiProvider(auth_required=False)

    async def get_pairs(self):
        """List all available market pairs."""
        data = await self.api.get('public/get-instruments')
        return {Pair(i.pop('instrument_name')): i for i in data['instruments']}

    async def get_tickers(self, pair: Pair = None):
        """Get tickers in all available markets."""
        params = {'instrument_name': pair.value} if pair else None
        data = await self.api.get('public/get-ticker', params)
        if pair:
            data.pop('i')
            return data
        return {Pair(ticker.pop('i')): ticker for ticker in data}

    async def get_trades(self, pair: Pair):
        """Get last 200 trades in a specified market."""
        data = await self.api.get(
            'public/get-trades', {'instrument_name': pair.value})
        for trade in data:
            trade.pop('i')
            trade.pop('dataTime')
        return data

    async def get_price(self, pair: Pair):
        """Get latest price of pair."""
        data = await self.api.get('public/get-ticker', {
            'instrument_name': pair.value
        })
        return float(data['a'])

    async def get_orderbook(self, pair: Pair, depth: int = 150):
        """Get the order book for a particular market."""
        data = await self.api.get('public/get-book', {
            'instrument_name': pair.value,
            'depth': depth
        })
        return data[0]

    async def listen_candles(self, period: Period, *pairs: List[Pair]):
        if not isinstance(period, Period):
            raise ValueError(f'Provide Period enum not {period}')

        channels = [
            f'candlestick.{period.value}.{pair.value}'
            for pair in pairs
        ]
        prev_time = {}

        async for data in self.api.listen('market', *channels):
            pair = Pair(data['instrument_name'])
            for candle in data['data']:
                current_time = int(candle['t'] / 1000)
                if pair not in prev_time or current_time > prev_time[pair]:
                    yield Candle(
                        current_time,
                        candle['o'], candle['h'], candle['l'],
                        candle['c'], candle['v'],
                        Pair(data['instrument_name'])
                    )
                    prev_time[pair] = current_time

    async def listen_trades(self, *pairs: List[Pair]):
        channels = [f'trade.{pair}' for pair in pairs]
        async for data in self.api.listen('market', *channels):
            for trade in data['data']:
                trade.pop('dataTime')
                yield Trade(
                    trade['d'], int(trade['t'] / 100),
                    trade['p'], trade['q'],
                    OrderSide(trade['s'].upper()),
                    Pair(data['instrument_name'])
                )

    async def listen_orderbook(
            self, *pairs: List[Pair], depth: int = 150) -> OrderBook:
        channels = [f'book.{pair}.{depth}' for pair in pairs]
        async for data in self.api.listen('market', *channels):
            pair = Pair(data['instrument_name'])
            buys = [
                OrderInBook(*order, OrderSide.BUY)
                for order in data['data'][0]['bids']
            ]
            sells = [
                OrderInBook(*order, OrderSide.SELL)
                for order in reversed(data['data'][0]['asks'])
            ]
            yield OrderBook(buys, sells, pair)


class Account:
    """Provides access to account actions and data. Balance, trades, orders."""
    def __init__(
            self, *, api_key: str = '', api_secret: str = '',
            from_env: bool = False, api: ApiProvider = None):
        if not api and not (api_key and api_secret) and not from_env:
            raise ValueError(
                'Pass ApiProvider or api_key with api_secret or from_env')
        self.api = api or ApiProvider(
            api_key=api_key, api_secret=api_secret, from_env=from_env)

    async def get_balance(self):
        """Return balance."""
        data = await self.api.post(
            'private/get-account-summary', {'params': {}})
        return {acc['currency']: acc for acc in data['accounts']}

    async def get_orders(
            self, pair: Pair, page: int = 0, page_size: int = 200):
        """Return all orders."""
        data = await self.api.post('private/get-order-history', {
            'params': {
                'instrument_name': pair.value,
                'page_size': page_size,
                'page': page
            }
        })
        orders = data.get('order_list') or []
        for order in orders:
            order['id'] = int(order.pop('order_id'))
        return orders

    async def get_open_orders(
            self, pair: Pair, page: int = 0, page_size: int = 200):
        """Return open orders."""
        data = await self.api.post('private/get-open-orders', {
            'params': {
                'instrument_name': pair.value,
                'page_size': page_size,
                'page': page
            }
        })
        orders = data.get('order_list') or []
        for order in orders:
            order['id'] = int(order.pop('order_id'))
        return orders

    async def get_trades(
            self, pair: Pair, page: int = 0, page_size: int = 200):
        """Return trades."""
        data = await self.api.post('private/get-trades', {
            'params': {
                'instrument_name': pair.value,
                'page_size': page_size,
                'page': page
            }
        })
        trades = data.get('trade_list') or []
        for trade in trades:
            trade['order_id'] = int(trade['order_id'])
            trade['id'] = int(trade.pop('trade_id'))
        return trades

    async def create_order(
            self, pair: Pair, side: OrderSide, type_: OrderType,
            quantity: float, price: float = 0, client_id: int = None) -> int:
        """Create raw order with buy or sell side."""
        data = {
            'instrument_name': pair.value, 'side': side.value,
            'type': type_.value
        }

        if type_ == OrderType.MARKET and side == OrderSide.BUY:
            data['notional'] = quantity
        else:
            data['quantity'] = quantity

        if client_id:
            data['client_oid'] = str(client_id)

        if price:
            if type_ == OrderType.MARKET:
                raise ValueError(
                    "Error, MARKET execution do not support price value")
            data['price'] = price

        resp = await self.api.post('private/create-order', {'params': data})
        return int(resp['order_id'])

    async def buy_limit(self, pair: Pair, quantity: float, price: float):
        """Buy limit order."""
        return await self.create_order(
            pair, OrderSide.BUY, OrderType.LIMIT, quantity, price
        )

    async def sell_limit(self, pair: Pair, quantity: float, price: float):
        """Sell limit order."""
        return await self.create_order(
            pair, OrderSide.SELL, OrderType.LIMIT, quantity, price
        )

    async def wait_for_status(
            self, order_id: int, pair: Pair, statuses, delay: int = 0.5):
        """Wait for order status."""
        order = await self.get_order(order_id)

        for _ in range(self.api.retries):
            if OrderStatus(order['status']) in statuses:
                break

            await asyncio.sleep(delay)
            order = await self.get_order(order_id)

        if OrderStatus(order['status']) not in statuses:
            raise ApiError(
                f"Status not changed for: {order}, must be in: {statuses}")

    async def buy_market(
            self, pair: Pair, spend: float, wait_for_fill=False):
        """Buy market order."""
        order_id = await self.create_order(
            pair, OrderSide.BUY, OrderType.MARKET, spend
        )
        if wait_for_fill:
            await self.wait_for_status(order_id, pair, (
                OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED,
                OrderStatus.REJECTED
            ))

        return order_id

    async def sell_market(
            self, pair: Pair, quantity: float, wait_for_fill=False):
        """Sell market order."""
        order_id = await self.create_order(
            pair, OrderSide.SELL, OrderType.MARKET, quantity
        )

        if wait_for_fill:
            await self.wait_for_status(order_id, pair, (
                OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED,
                OrderStatus.REJECTED
            ))

        return order_id

    async def get_order(self, order_id: int):
        """Get order info."""
        data = await self.api.post('private/get-order-detail', {
            'params': {'order_id': str(order_id)}
        })
        data['order_info']['trade_list'] = data.pop('trade_list', [])
        data['order_info']['id'] = int(data['order_info'].pop('order_id'))
        return data['order_info']

    async def cancel_order(
            self, order_id: int, pair: Pair, wait_for_cancel=False):
        """Cancel order."""
        await self.api.post('private/cancel-order', {
            'params': {'order_id': order_id, 'instrument_name': pair.value}
        })

        if not wait_for_cancel:
            return

        await self.wait_for_status(order_id, pair, (
            OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED
        ))

    async def cancel_open_orders(self, pair: Pair):
        """Cancel all open orders."""
        return await self.api.post('private/cancel-all-orders', {
            'params': {'instrument_name': pair.value}
        })

    async def listen_balance(self):
        async for data in self.api.listen(
                'user', 'user.balance', sign=True):
            for balance in data.get('data', []):
                yield balance

    async def listen_orders(self, pair: Pair):
        async for data in self.api.listen(
                'user', f'user.order.{pair.value}', sign=True):
            for order in data.get('data', []):
                order['id'] = int(order.pop('order_id'))
                yield order
