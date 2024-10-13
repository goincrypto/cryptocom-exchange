import asyncio
import platform

from . import instruments, pairs
from .api import ApiError, ApiProvider, RecordApiProvider
from .market import Exchange
from .private import Account
from .structs import (
    Candle,
    Deposit,
    DepositStatus,
    Instrument,
    MarketTrade,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Pair,
    PrivateTrade,
    TimeDelta,
    Timeframe,
    Withdrawal,
    WithdrawalStatus,
)

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

__all__ = [
    "Order",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "pairs",
    "Pair",
    "instruments",
    "Instrument",
    "Timeframe",
    "Candle",
    "MarketTrade",
    "PrivateTrade",
    "TimeDelta",
    "Deposit",
    "Withdrawal",
    "DepositStatus",
    "WithdrawalStatus",
    "Exchange",
    "Account",
    "ApiError",
    "ApiProvider",
    "RecordApiProvider",
]
