"""
策略模組

提供各種量化交易策略的實作。
"""

from .base import BaseStrategy, SignalType, signals_to_positions
from .ma_crossover import MACrossoverStrategy, create_ma_crossover_strategy

__all__ = [
    "BaseStrategy",
    "SignalType",
    "signals_to_positions",
    "MACrossoverStrategy",
    "create_ma_crossover_strategy",
]
