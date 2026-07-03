import time
from typing import AsyncGenerator, Dict, List, Optional

from . import pairs
from .api import ApiProvider
from .structs import (
    BaseCurrencyConfig,
    Candle,
    DefaultPairDict,
    MarketTicker,
    MarketTrade,
    OrderBook,
    OrderInBook,
    OrderSide,
    Pair,
    RiskParameters,
    Timeframe,
)


class Exchange:
    """Interface to base exchange methods."""

    def __init__(self, api: ApiProvider = None):
        self.api = api or ApiProvider(auth_required=False)
        self.pairs = DefaultPairDict(**{pair.name: pair for pair in pairs.all()})

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
        timeframe: Timeframe,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        count: int = 300,
        include_all: bool = False,
    ) -> AsyncGenerator[Candle, None]:
        """
        Yield candles iteratively with adaptive window sizing.

        Candles are yielded in descending order (newest first), matching the
        API response order.

        Args:
            pair: Trading pair
            timeframe: Candle timeframe
            start_ts: Start timestamp (unix seconds)
            end_ts: End timestamp (unix seconds)
            count: Max candles to yield (default 300)
            include_all: Yield ALL available data, ignoring count

        Raises:
            ValueError: If include_all=True with start_ts or end_ts
        """
        # Validation: include_all cannot be used with time boundaries
        if include_all and (start_ts is not None or end_ts is not None):
            raise ValueError("include_all cannot be used with start_ts or end_ts")

        # Defaults
        end_ts = end_ts or int(time.time())
        start_ts = start_ts or (end_ts - 30 * 24 * 60 * 60)  # 30 days default

        # Adaptive window sizing - API uses milliseconds
        current_end = end_ts * 1000
        target_start = start_ts * 1000
        window_size_ms = 3600 * 1000  # Start with 1-hour window
        chunk_size = 300  # API max per request

        prev_timestamps = set()
        yielded_count = 0

        while current_end > target_start:
            current_start = max(current_end - window_size_ms, target_start)

            # Fetch candles
            params = {
                "instrument_name": pair.exchange_name,
                "timeframe": timeframe.value,
                "count": chunk_size,
                "start_ts": int(current_start),
                "end_ts": int(current_end),
            }
            data = await self.api.get("public/get-candlestick", params)

            # Parse and filter out duplicates
            candles = [Candle.from_api(candle, pair) for candle in reversed(data)]
            candles = [c for c in candles if c.time not in prev_timestamps]

            if not candles:
                # No new data, move window back
                current_end = current_start
                continue

            # Yield candles
            for candle in candles:
                # Check time boundaries
                if start_ts is not None and candle.time < start_ts:
                    return
                if end_ts is not None and candle.time > end_ts:
                    continue

                yield candle
                yielded_count += 1
                prev_timestamps.add(candle.time)

                # Check count limit
                if not include_all and yielded_count >= count:
                    return

            # Adaptive window sizing
            if len(candles) == chunk_size:
                # Got max, reduce window for more granular data
                window_size_ms = max(window_size_ms // 2, 60 * 1000)
            else:
                # Got fewer than max, reset to 1-hour
                window_size_ms = 3600 * 1000

            # Move window backward
            current_end = candles[-1].time * 1000

    async def get_trades(
        self,
        pair: Pair,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        count: int = 150,
        include_all: bool = False,
    ) -> AsyncGenerator[MarketTrade, None]:
        """
        Yield trades iteratively with adaptive window sizing.

        Trades are yielded in descending order (newest first), matching the
        API response order.

        Args:
            pair: Trading pair
            start_ts: Start timestamp (unix seconds)
            end_ts: End timestamp (unix seconds)
            count: Max trades to yield (default 150)
            include_all: Yield ALL available data, ignoring count

        Raises:
            ValueError: If include_all=True with start_ts or end_ts
        """
        # Validation: include_all cannot be used with time boundaries
        if include_all and (start_ts is not None or end_ts is not None):
            raise ValueError("include_all cannot be used with start_ts or end_ts")

        # Defaults
        end_ts = end_ts or int(time.time())
        start_ts = start_ts or (end_ts - 60 * 60)  # 1 hour default

        # Adaptive window sizing - API uses nanoseconds
        current_end = end_ts * 1_000_000_000
        target_start = start_ts * 1_000_000_000
        window_size_ns = 3600 * 1_000_000_000  # Start with 1-hour window
        chunk_count = 150  # API max per request

        prev_trade_ids = set()
        yielded_count = 0

        while current_end > target_start:
            current_start = max(current_end - window_size_ns, target_start)

            # Fetch trades
            params = {
                "instrument_name": pair.exchange_name,
                "count": chunk_count,
                "start_ts": int(current_start),
                "end_ts": int(current_end),
            }
            data = await self.api.get("public/get-trades", params)

            # Parse and filter out duplicates
            trades = [MarketTrade.from_api(pair, trade) for trade in reversed(data)]
            trades = [t for t in trades if t.id not in prev_trade_ids]

            if not trades:
                # No new data, move window back
                current_end = current_start
                continue

            # Yield trades
            for trade in trades:
                # Check time boundaries
                if start_ts is not None and trade.time < start_ts:
                    return
                if end_ts is not None and trade.time > end_ts:
                    continue

                yield trade
                yielded_count += 1
                prev_trade_ids.add(trade.id)

                # Check count limit
                if not include_all and yielded_count >= count:
                    return

            # Adaptive window sizing
            if len(trades) == chunk_count:
                # Got max, reduce window for more granular data
                window_size_ns = max(window_size_ns // 2, 60 * 1_000_000_000)
            else:
                # Got fewer than max, reset to 1-hour
                window_size_ns = 3600 * 1_000_000_000

            # Move window backward
            current_end = trades[-1].time * 1_000_000_000

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
        self, timeframe: Timeframe, *pairs: List[Pair]
    ) -> AsyncGenerator[Candle, None]:
        if not isinstance(timeframe, Timeframe):
            raise ValueError(f"Provide Timeframe enum not {timeframe}")

        channels = [
            f"candlestick.{timeframe.value}.{pair.exchange_name}" for pair in pairs
        ]

        async for data in self.api.listen("market", *channels):
            pair = self.pairs[data["instrument_name"]]
            for candle in data["data"]:
                yield Candle.from_api(candle, pair)

    async def listen_trades(
        self, *pairs: List[Pair]
    ) -> AsyncGenerator[MarketTrade, None]:
        channels = [f"trade.{pair.exchange_name}" for pair in pairs]
        async for data in self.api.listen("market", *channels):
            for trade in data["data"]:
                pair = self.pairs[data["instrument_name"]]
                yield MarketTrade.from_api(pair, trade)

    async def listen_orderbook(
        self, *pairs: List[Pair]
    ) -> AsyncGenerator[OrderBook, None]:
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

    async def get_risk_parameters(self) -> RiskParameters:
        """Get risk parameters for Smart Cross Margin including min/max order notional."""
        data = await self.api.get("public/get-risk-parameters")
        return RiskParameters.from_api(data)
