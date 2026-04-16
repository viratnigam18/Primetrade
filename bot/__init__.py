"""Core trading bot package for Binance Futures Testnet."""

from bot.client import BinanceClient
from bot.orders import OrderManager
from bot.config import settings

__all__ = ["BinanceClient", "OrderManager", "settings"]
