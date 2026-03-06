"""
回測報告模組

提供結果輸出功能。
"""

from .output import (
    trades_to_dataframe,
    save_trades_csv,
    save_equity_curve_csv,
    generate_markdown_report,
    save_markdown_report,
    export_results,
)
from .generator import (
    ReportGenerator,
    generate_optimization_report,
)

__all__ = [
    "trades_to_dataframe",
    "save_trades_csv",
    "save_equity_curve_csv",
    "generate_markdown_report",
    "save_markdown_report",
    "export_results",
    "ReportGenerator",
    "generate_optimization_report",
]
