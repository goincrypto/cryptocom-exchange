from typing import AsyncGenerator, Dict, List

from . import pairs
from .api import ApiProvider
from .structs import (
    Candle,
    DefaultPairDict,
    MarketTicker,
    MarketTrade,
    OrderBook,
    OrderInBook,
    OrderSide,
    Pair,
    Period,
)


class Exchange:
    """Interface to base exchange methods."""

    def __init__(self, api: ApiProvider = None):
        self.api = api or ApiProvider(auth_required=False)
        self.pairs = DefaultPairDict(
            **{pair.name: pair for pair in pairs.all()}
        )

    async def sync_pairs(self):
        """Use this method to sync pairs if you have issues with missing
        pairs in library side."""
        self.pairs = DefaultPairDict(
            **{pair.name: pair for pair in (await self.get_pairs())}
        )

    async def get_pairs(self) -> List[Pair]:
        """List all available market pairs and store to provide pairs info."""
        data = await self.api.get("public/get-instruments")
        return [
            Pair(
                i["symbol"],
                price_precision=i["quote_decimals"],
                quantity_precision=i["quantity_decimals"],
            )
            for i in data
            if "-" not in i["symbol"] and "@" not in i["symbol"]
        ]

    async def get_orderbook(self, pair: Pair, depth: int = 150) -> OrderBook:
        """Get the order book for a particular market."""
        data = await self.api.get(
            "public/get-book",
            {"instrument_name": pair.exchange_name, "depth": depth},
        )
        buys = [
            OrderInBook.from_api(order, pair, OrderSide.BUY)
            for order in data[0]["bids"]
        ]
        sells = [
            OrderInBook.from_api(order, pair, OrderSide.SELL)
            for order in reversed(data[0]["asks"])
        ]
        return OrderBook(buys, sells, pair)

    async def get_candles(
        self,
        pair: Pair,
        period: Period,
        start_ts: int = None,
        end_ts: int = None,
        count: int = 300,
    ) -> List[Candle]:
        data = []
        while not data:
            data = await self.api.get(
                "public/get-candlestick",
                {
                    "instrument_name": pair.exchange_name,
                    "timeframe": period.value,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "count": count,
                },
            )
            data = [Candle.from_api(pair, candle) for candle in data]
            # print(datetime.datetime.fromtimestamp(next_data[0].time), datetime.datetime.fromtimestamp(next_data[-1].time))
            # if not data or data[-1].time != next_data[-1].time:
            #     data += next_data
            #     start_ts = next_data[-1].time
            #     end_ts = next_data[-1].time + (next_data[-1].time - next_data[-2].time) * count
            #     next_data = []
        return data

    async def get_trades(self, pair: Pair) -> List[MarketTrade]:
        """Get last 200 trades in a specified market."""
        data = await self.api.get(
            "public/get-trades", {"instrument_name": pair.exchange_name}
        )
        return [MarketTrade.from_api(pair, trade) for trade in reversed(data)]

    async def get_ticker(self, pair: Pair) -> MarketTicker:
        """Get ticker in for provided pair."""
        data = await self.api.get(
            "public/get-tickers", {"instrument_name": pair.exchange_name}
        )
        return MarketTicker.from_api(pair, data[0])

    async def get_tickers(self) -> Dict[Pair, MarketTicker]:
        """Get tickers in all available markets."""
        data = await self.api.get("public/get-tickers")
        return {
            self.pairs[ticker["i"]]: MarketTicker.from_api(
                self.pairs[ticker["i"]], ticker
            )
            for ticker in data
            if ticker["i"] in self.pairs
        }

    async def get_price(self, pair: Pair) -> float:
        """Get latest price of pair."""
        return (await self.get_ticker(pair)).trade_price

    async def listen_candles(
        self, period: Period, *pairs: List[Pair]
    ) -> AsyncGenerator[Candle, None]:
        if not isinstance(period, Period):
            raise ValueError(f"Provide Period enum not {period}")

        channels = [
            f"candlestick.{period.value}.{pair.exchange_name}" for pair in pairs
        ]

        async for data in self.api.listen("market", *channels):
            pair = self.pairs[data["instrument_name"]]
            for candle in data["data"]:
                yield Candle.from_api(pair, candle)

    async def listen_trades(self, *pairs: List[Pair]) -> MarketTrade:
        channels = [f"trade.{pair.exchange_name}" for pair in pairs]
        async for data in self.api.listen("market", *channels):
            for trade in data["data"]:
                pair = self.pairs[data["instrument_name"]]
                yield MarketTrade.from_api(pair, trade)

    async def listen_orderbook(self, *pairs: List[Pair]) -> OrderBook:
        channels = [f"book.{pair.exchange_name}.50" for pair in pairs]
        async for data in self.api.listen("market", *channels):
            pair = self.pairs[data["instrument_name"]]
            buys = [
                OrderInBook.from_api(order, pair, OrderSide.BUY)
                for order in data["data"][0]["bids"]
            ]
            sells = [
                OrderInBook.from_api(order, pair, OrderSide.SELL)
                for order in reversed(data["data"][0]["asks"])
            ]
            yield OrderBook(buys, sells, pair)
