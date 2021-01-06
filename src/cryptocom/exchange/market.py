import asyncio

from typing import List, Dict

from .api import ApiProvider
from .structs import (
    Pair, MarketTicker, MarketTrade, Period, Candle,
    OrderInBook, OrderBook, OrderSide
)
from . import pairs


class Exchange:
    """Interface to base exchange methods."""
    def __init__(self, api: ApiProvider = None):
        self.api = api or ApiProvider(auth_required=False)
        self.pairs = {pair.name: pair for pair in pairs.all()}

    async def sync_pairs(self):
        """Use this method to sync pairs if you have issues with missing
        pairs in library side."""
        self.pairs = {pair.name: pair for pair in (await self.get_pairs())}

    async def get_pairs(self) -> List[Pair]:
        """List all available market pairs and store to provide pairs info."""
        data = await self.api.get('public/get-instruments')
        return [
            Pair(
                i['instrument_name'],
                price_precision=i['price_decimals'],
                quantity_precision=i['quantity_decimals']
            ) for i in data['instruments']
        ]

    async def get_ticker(self, pair: Pair) -> MarketTicker:
        """Get ticker in for provided pair."""
        data = await self.api.get(
            'public/get-ticker', {'instrument_name': pair.name})
        return MarketTicker.from_api(pair, data)

    async def get_tickers(self) -> Dict[Pair, MarketTicker]:
        """Get tickers in all available markets."""
        data = await self.api.get('public/get-ticker')
        return {
            self.pairs[ticker['i']]: MarketTicker.from_api(
                self.pairs[ticker['i']], ticker
            ) for ticker in data
            if ticker['i'] in self.pairs
        }

    async def get_price(self, pair: Pair) -> float:
        """Get latest price of pair."""
        return (await self.get_ticker(pair)).trade_price

    async def get_trades(self, pair: Pair) -> List[MarketTrade]:
        """Get last 200 trades in a specified market."""
        data = await self.api.get(
            'public/get-trades', {'instrument_name': pair.name})
        return [MarketTrade.from_api(pair, trade) for trade in reversed(data)]

    async def get_orderbook(self, pair: Pair, depth: int = 150) -> OrderBook:
        """Get the order book for a particular market."""
        data = await self.api.get('public/get-book', {
            'instrument_name': pair.name, 'depth': depth})
        buys = [
            OrderInBook(*order, pair, OrderSide.BUY)
            for order in data[0]['bids']
        ]
        sells = [
            OrderInBook(*order, pair, OrderSide.SELL)
            for order in reversed(data[0]['asks'])
        ]
        return OrderBook(buys, sells, pair)

    async def get_candles(self, pair: Pair, period: Period) -> List[Candle]:
        data = await self.api.get('public/get-candlestick', {
            'instrument_name': pair.name, 'timeframe': period.value})

        return [Candle.from_api(pair, candle) for candle in data]

    async def listen_candles(
            self, period: Period, *pairs: List[Pair]) -> Candle:
        if not isinstance(period, Period):
            raise ValueError(f'Provide Period enum not {period}')

        channels = [
            f'candlestick.{period}.{pair.name}'
            for pair in pairs
        ]
        prev_time = {}

        async for data in self.api.listen('market', *channels):
            pair = self.pairs[data['instrument_name']]
            for candle in data['data']:
                current_time = int(candle['t'] / 1000)
                if pair not in prev_time or current_time > prev_time[pair]:
                    yield Candle.from_api(pair, candle)
                    prev_time[pair] = current_time

    async def listen_trades(self, *pairs: List[Pair]) -> MarketTrade:
        channels = [f'trade.{pair.name}' for pair in pairs]
        async for data in self.api.listen('market', *channels):
            for trade in data['data']:
                pair = self.pairs[data['instrument_name']]
                yield MarketTrade.from_api(pair, trade)

    async def listen_orderbook(self, *pairs: List[Pair]) -> OrderBook:
        channels = [f'book.{pair.name}.150' for pair in pairs]
        async for data in self.api.listen('market', *channels):
            pair = self.pairs[data['instrument_name']]
            buys = [
                OrderInBook(*order, pair, OrderSide.BUY)
                for order in data['data'][0]['bids']
            ]
            sells = [
                OrderInBook(*order, pair, OrderSide.SELL)
                for order in reversed(data['data'][0]['asks'])
            ]
            yield OrderBook(buys, sells, pair)
