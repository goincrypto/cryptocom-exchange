import logging
import time
from collections.abc import AsyncGenerator

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
    RiskParameters,
    Timeframe,
)


class Exchange:
    """Interface to base exchange methods."""

    api: ApiProvider
    pairs: DefaultPairDict

    def __init__(self, api: ApiProvider | None = None) -> None:
        self.api = api or ApiProvider(auth_required=False)
        self.pairs = DefaultPairDict(**{pair.name: pair for pair in pairs.all()})

    async def sync_pairs(self):
        """Use this method to sync pairs if you have issues with missing
        pairs in library side."""
        self.pairs = DefaultPairDict(
            **{pair.name: pair for pair in (await self.get_pairs())}
        )

    async def get_pairs(self) -> list[Pair]:
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
        start_ts: int | None = None,
        end_ts: int | None = None,
        count: int | None = None,
        all_history: bool = False,
    ) -> AsyncGenerator[Candle, None]:
        """
        Yield candles iteratively using pagination.

        Candles are yielded in descending order (newest first).

        Args:
            pair: Trading pair
            timeframe: Candle timeframe
            start_ts: Start timestamp (unix seconds). Cannot be used with all_history=True.
            end_ts: End timestamp (unix seconds). Cannot be used with all_history=True.
            count: Maximum number of candles to yield. Default None (no limit).
            all_history: If True, fetch ALL candles ignoring count limit.
                Cannot be used with start_ts or end_ts.
        """
        logger = logging.getLogger(__name__)

        # Validation: all_history cannot be used with time boundaries
        if all_history and (start_ts is not None or end_ts is not None):
            raise ValueError("'all_history' cannot be used with start_ts or end_ts")

        actual_end_ts = end_ts or int(time.time())
        actual_start_ts = start_ts

        logger.info(
            "get_candles: pair=%s timeframe=%s start_ts=%s end_ts=%s all_history=%s",
            pair,
            timeframe.value,
            actual_start_ts,
            actual_end_ts,
            all_history,
        )

        # Pagination constants - API uses milliseconds
        chunk_size = 300  # API max per request, always used internally
        yielded_count = 0
        prev_timestamps = set()

        # First request: use end_ts to get latest candles
        current_end = actual_end_ts * 1000

        while True:
            # Fetch candles up to 300 ending at current_end
            params = {
                "instrument_name": pair.exchange_name,
                "timeframe": timeframe.value,
                "count": chunk_size,
                "end_ts": int(current_end),
            }

            logger.debug(
                "API request: end_ts=%s, chunk_size=%d", current_end / 1000, chunk_size
            )
            data = await self.api.get("public/get-candlestick", params)

            if not data:
                # No more data
                break

            # API returns candles ascending (oldest first), reverse for newest-first yield
            candles = [Candle.from_api(candle, pair) for candle in reversed(data)]

            # Filter duplicates
            unique_candles = [c for c in candles if c.time not in prev_timestamps]

            logger.debug(
                "Response: raw=%d candles unique=%d", len(data), len(unique_candles)
            )

            if not unique_candles:
                # All duplicates, we're done
                break

            # Apply start_ts filter if specified
            if actual_start_ts is not None:
                oldest_candle_time = unique_candles[-1].time
                if oldest_candle_time < actual_start_ts:
                    # Filter to only candles >= start_ts
                    unique_candles = [
                        c for c in unique_candles if c.time >= actual_start_ts
                    ]
                    if not unique_candles:
                        break

            # Yield candles (already in newest-first order)
            for candle in unique_candles:
                # Check upper boundary
                if actual_end_ts is not None and candle.time > actual_end_ts:
                    continue

                yield candle
                yielded_count += 1
                prev_timestamps.add(candle.time)

                # Check count limit
                if count is not None and yielded_count >= count:
                    return

            # Stop conditions:
            # - When start_ts provided: stop when we've reached or passed start boundary
            # - Otherwise: stop when partial results (no more data)
            if actual_start_ts is not None:
                oldest_yet = unique_candles[-1].time
                if oldest_yet <= actual_start_ts:
                    break
            elif len(unique_candles) < chunk_size:
                break

            # Continue pagination: next request starts from oldest candle we just processed
            current_end = unique_candles[-1].time * 1000

    async def get_trades(
        self,
        pair: Pair,
        start_ts: int | None = None,
        end_ts: int | None = None,
        count: int | None = None,
        all_history: bool = False,
    ) -> AsyncGenerator[MarketTrade, None]:
        """
        Yield trades iteratively using pagination.

        Trades are yielded in descending order (newest first).

        Args:
            pair: Trading pair
            start_ts: Start timestamp (unix seconds). Cannot be used with all_history=True.
            end_ts: End timestamp (unix seconds). Cannot be used with all_history=True.
            count: Maximum number of trades to yield. Default None (no limit).
            all_history: If True, fetch ALL trades ignoring count limit.
                Cannot be used with start_ts or end_ts.
        """
        logger = logging.getLogger(__name__)

        # Validation: all_history cannot be used with time boundaries
        if all_history and (start_ts is not None or end_ts is not None):
            raise ValueError("'all_history' cannot be used with start_ts or end_ts")

        actual_end_ts = end_ts or int(time.time())
        actual_start_ts = start_ts

        logger.info(
            "get_trades: pair=%s start_ts=%s end_ts=%s all_history=%s",
            pair,
            actual_start_ts,
            actual_end_ts,
            all_history,
        )

        # Pagination constants - API uses nanoseconds
        chunk_size = 150  # API max per request, always used internally
        yielded_count = 0
        prev_trade_ids = set()

        # First request: use end_ts to get latest trades
        current_end = actual_end_ts * 1_000_000_000

        while True:
            # Fetch trades up to 150 ending at current_end
            params = {
                "instrument_name": pair.exchange_name,
                "count": chunk_size,
                "end_ts": int(current_end),
            }

            logger.debug(
                "API request: end_ts=%s, chunk_size=%d", current_end / 1e9, chunk_size
            )
            data = await self.api.get("public/get-trades", params)

            if not data:
                # No more data
                break

            # API returns trades in descending order (newest first)
            trades = [MarketTrade.from_api(pair, trade) for trade in data]

            # Filter duplicates
            unique_trades = [t for t in trades if t.id not in prev_trade_ids]

            logger.debug(
                "Response: raw=%d trades unique=%d", len(data), len(unique_trades)
            )

            if not unique_trades:
                # All duplicates, we're done
                break

            # Apply start_ts filter if specified
            if actual_start_ts is not None:
                oldest_trade_time = unique_trades[-1].time
                if oldest_trade_time < actual_start_ts:
                    # Filter to only trades >= start_ts
                    unique_trades = [
                        t for t in unique_trades if t.time >= actual_start_ts
                    ]
                    if not unique_trades:
                        break

            # Yield trades (already in newest-first order)
            for trade in unique_trades:
                # Check upper boundary
                if actual_end_ts is not None and trade.time > actual_end_ts:
                    continue

                yield trade
                yielded_count += 1
                prev_trade_ids.add(trade.id)

                # Check count limit
                if count is not None and yielded_count >= count:
                    return

            # Stop conditions:
            # - When start_ts provided: stop when we've reached or passed start boundary
            # - Otherwise: stop when partial results (no more data)
            if actual_start_ts is not None:
                oldest_yet = unique_trades[-1].time
                if oldest_yet <= actual_start_ts:
                    break
            elif len(unique_trades) < chunk_size:
                break

            # Continue pagination: next request starts from oldest trade we just processed
            current_end = unique_trades[-1].time * 1_000_000_000

    async def get_ticker(self, pair: Pair) -> MarketTicker:
        """Get ticker in for provided pair."""
        data = await self.api.get(
            "public/get-tickers", {"instrument_name": pair.exchange_name}
        )
        return MarketTicker.from_api(pair, data[0])

    async def get_tickers(self) -> dict[Pair, MarketTicker]:
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
        self, timeframe: Timeframe, *pairs: list[Pair]
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
        self, *pairs: list[Pair]
    ) -> AsyncGenerator[MarketTrade, None]:
        channels = [f"trade.{pair.exchange_name}" for pair in pairs]
        async for data in self.api.listen("market", *channels):
            for trade in data["data"]:
                pair = self.pairs[data["instrument_name"]]
                yield MarketTrade.from_api(pair, trade)

    async def listen_orderbook(
        self, *pairs: list[Pair]
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
