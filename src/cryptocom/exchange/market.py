import asyncio

from typing import List

from .api import ApiProvider
from .structs import (
    Pair, Period, Candle, MarketTrade, OrderInBook, OrderBook, OrderSide
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

    async def get_trades(self, pair: Pair) -> List[MarketTrade]:
        """Get last 200 trades in a specified market."""
        data = await self.api.get(
            'public/get-trades', {'instrument_name': pair.value})
        for trade in data:
            trade.pop('i')
            trade.pop('dataTime')
        return data

    async def get_price(self, pair: Pair) -> float:
        """Get latest price of pair."""
        data = await self.api.get('public/get-ticker', {
            'instrument_name': pair.value
        })
        return float(data['a'])

    async def get_orderbook(self, pair: Pair, depth: int = 150) -> OrderBook:
        """Get the order book for a particular market."""
        data = await self.api.get('public/get-book', {
            'instrument_name': pair.value,
            'depth': depth
        })
        return data[0]

    async def listen_candles(
            self, period: Period, *pairs: List[Pair]) -> Candle:
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

    async def listen_trades(self, *pairs: List[Pair]) -> MarketTrade:
        channels = [f'trade.{pair}' for pair in pairs]
        async for data in self.api.listen('market', *channels):
            for trade in data['data']:
                trade.pop('dataTime')
                yield MarketTrade(
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
