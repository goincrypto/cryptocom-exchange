import asyncio
import platform

from .structs import (
    Order, OrderSide, OrderStatus, OrderType, Pair, Period, Candle,
    MarketTrade, Coin, PrivateTrade, Timeframe, DepositStatus, Deposit,
    WithdrawalStatus, Withdrawal
)
from .market import Exchange
from .private import Account
from .api import ApiError, ApiProvider
from . import pairs, coins

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

__all__ = [
    'Order', 'OrderSide', 'OrderStatus', 'OrderType',
    'pairs', 'Pair', 'coins', 'Coin',
    'Period', 'Candle', 'MarketTrade', 'PrivateTrade',
    'Timeframe', 'Deposit', 'Withdrawal', 'DepositStatus', 'WithdrawalStatus',
    'Exchange', 'Account',
    'ApiError', 'ApiProvider'
]

__version__ = '0.10.2'
