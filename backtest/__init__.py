"""
回測模組

提供回測引擎與相關功能。
"""

from .engine import BacktestEngine, BacktestResult, Trade, Position, run_backtest

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "Trade",
    "Position",
    "run_backtest",
]
