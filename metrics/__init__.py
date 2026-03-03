"""
績效指標模組

提供各種績效指標計算功能。
"""

from .performance import (
    calculate_metrics,
    calculate_returns,
    calculate_annualized_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_avg_win_loss,
    calculate_calmar_ratio,
    print_metrics,
)

__all__ = [
    "calculate_metrics",
    "calculate_returns",
    "calculate_annualized_return",
    "calculate_max_drawdown",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_win_rate",
    "calculate_profit_factor",
    "calculate_avg_win_loss",
    "calculate_calmar_ratio",
    "print_metrics",
]
