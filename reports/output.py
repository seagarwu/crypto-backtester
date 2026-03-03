"""
回測結果輸出模組

提供輸出交易紀錄、績效摘要、Markdown 報表等功能。
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import pandas as pd

from backtest import BacktestResult, Trade
from metrics import calculate_metrics


def trades_to_dataframe(trades: List[Trade]) -> pd.DataFrame:
    """
    將交易記錄轉換為 DataFrame

    Args:
        trades: 交易記錄列表

    Returns:
        交易記錄 DataFrame
    """
    if not trades:
        return pd.DataFrame(columns=[
            "entry_datetime",
            "entry_price",
            "quantity",
            "direction",
            "exit_datetime",
            "exit_price",
            "pnl",
            "commission",
        ])

    records = []
    for t in trades:
        records.append({
            "entry_datetime": t.entry_datetime,
            "entry_price": t.entry_price,
            "quantity": t.quantity,
            "direction": t.direction,
            "exit_datetime": t.exit_datetime,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "commission": t.commission,
        })

    return pd.DataFrame(records)


def save_trades_csv(result: BacktestResult, output_path: str) -> str:
    """
    儲存交易記錄為 CSV

    Args:
        result: BacktestResult 物件
        output_path: 輸出檔案路徑

    Returns:
        輸出檔案路徑
    """
    df = trades_to_dataframe(result.trades)

    # 建立目錄
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    df.to_csv(output_path, index=False)
    print(f"交易記錄已儲存至: {output_path}")

    return output_path


def save_equity_curve_csv(result: BacktestResult, output_path: str) -> str:
    """
    儲存資產曲線為 CSV

    Args:
        result: BacktestResult 物件
        output_path: 輸出檔案路徑

    Returns:
        輸出檔案路徑
    """
    # 建立目錄
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    result.equity_curve.to_csv(output_path, index=False)
    print(f"資產曲線已儲存至: {output_path}")

    return output_path


def generate_markdown_report(
    result: BacktestResult,
    metrics: dict,
    strategy_name: str = "Strategy",
    symbol: str = "Unknown",
    interval: str = "Unknown",
) -> str:
    """
    生成 Markdown 格式的回測報告

    Args:
        result: BacktestResult 物件
        metrics: 績效指標字典
        strategy_name: 策略名稱
        symbol: 交易標的
        interval: K 線間隔

    Returns:
        Markdown 格式的報告內容
    """
    md = []
    md.append(f"# 📊 回測報告")
    md.append("")
    md.append(f"**策略**: {strategy_name}")
    md.append(f"**標的**: {symbol}")
    md.append(f"**時間框架**: {interval}")
    md.append(f"**生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("")

    # 基本資訊
    md.append("## 📅 基本資訊")
    md.append("")
    md.append(f"| 項目 | 數值 |")
    md.append(f"|------|------|")
    md.append(f"| 開始日期 | {metrics.get('start_date', 'N/A')} |")
    md.append(f"| 結束日期 | {metrics.get('end_date', 'N/A')} |")
    md.append(f"| 天數 | {metrics.get('days', 0)} 天 |")
    md.append(f"| 初始資金 | ${metrics['initial_capital']:,.2f} |")
    md.append(f"| 最終資產 | ${metrics['final_equity']:,.2f} |")
    md.append("")

    # 報酬率
    md.append("## 📈 報酬率")
    md.append("")
    md.append(f"| 項目 | 數值 |")
    md.append(f"|------|------|")
    md.append(f"| 總報酬率 | {metrics['total_return_pct']:.2f}% |")
    md.append(f"| 年化報酬率 | {metrics['annualized_return_pct']:.2f}% |")
    md.append("")

    # 風險
    md.append("## ⚠️ 風險指標")
    md.append("")
    md.append(f"| 項目 | 數值 |")
    md.append(f"|------|------|")
    md.append(f"| 最大回撤 | {metrics['max_drawdown_pct']:.2f}% |")
    md.append(f"| Calmar Ratio | {metrics['calmar_ratio']:.2f} |")
    md.append("")

    # 風險調整報酬
    md.append("## 📊 風險調整報酬")
    md.append("")
    md.append(f"| 項目 | 數值 |")
    md.append(f"|------|------|")
    md.append(f"| Sharpe Ratio | {metrics['sharpe_ratio']:.2f} |")
    md.append(f"| Sortino Ratio | {metrics['sortino_ratio']:.2f} |")
    md.append("")

    # 交易統計
    md.append("## 🔄 交易統計")
    md.append("")
    md.append(f"| 項目 | 數值 |")
    md.append(f"|------|------|")
    md.append(f"| 總交易次數 | {metrics['total_trades']} |")
    md.append(f"| 獲勝次數 | {metrics['winning_trades']} |")
    md.append(f"| 虧損次數 | {metrics['losing_trades']} |")
    md.append(f"| 勝率 | {metrics['win_rate_pct']:.2f}% |")
    md.append(f"| 盈利因子 | {metrics['profit_factor']:.2f} |")
    md.append(f"| 平均盈虧比 | {metrics['avg_win_loss_ratio']:.2f} |")
    md.append("")

    # 最近交易記錄
    if result.trades:
        md.append("## 📋 最近交易記錄")
        md.append("")
        md.append("| 進場時間 | 進場價格 | 數量 | 方向 | 平倉時間 | 平倉價格 | 損益 |")
        md.append("|----------|----------|------|------|----------|----------|------|")

        # 只顯示最近 10 筆
        recent_trades = result.trades[-10:]
        for t in recent_trades:
            exit_price_str = f"{t.exit_price:.2f}" if t.exit_price else "-"
            md.append(
                f"| {t.entry_datetime[:19]} | {t.entry_price:.2f} | "
                f"{t.quantity:.4f} | {t.direction} | "
                f"{t.exit_datetime[:19] if t.exit_datetime else '-'} | "
                f"{exit_price_str} | "
                f"{t.pnl:.2f} |"
            )
        md.append("")

    return "\n".join(md)


def save_markdown_report(
    result: BacktestResult,
    metrics: dict,
    output_path: str,
    strategy_name: str = "Strategy",
    symbol: str = "Unknown",
    interval: str = "Unknown",
) -> str:
    """
    儲存 Markdown 報告

    Args:
        result: BacktestResult 物件
        metrics: 績效指標字典
        output_path: 輸出檔案路徑
        strategy_name: 策略名稱
        symbol: 交易標的
        interval: K 線間隔

    Returns:
        輸出檔案路徑
    """
    md_content = generate_markdown_report(
        result=result,
        metrics=metrics,
        strategy_name=strategy_name,
        symbol=symbol,
        interval=interval,
    )

    # 建立目錄
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Markdown 報告已儲存至: {output_path}")

    return output_path


def export_results(
    result: BacktestResult,
    metrics: dict,
    output_dir: str = "reports",
    strategy_name: str = "Strategy",
    symbol: str = "Unknown",
    interval: str = "Unknown",
) -> dict:
    """
    匯出所有結果

    Args:
        result: BacktestResult 物件
        metrics: 績效指標字典
        output_dir: 輸出目錄
        strategy_name: 策略名稱
        symbol: 交易標的
        interval: K 線間隔

    Returns:
        輸出檔案路徑的字典
    """
    # 建立輸出目錄
    os.makedirs(output_dir, exist_ok=True)

    # 產生檔名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{symbol}_{interval}_{timestamp}"

    output_files = {}

    # 交易記錄
    trades_path = os.path.join(output_dir, f"{prefix}_trades.csv")
    save_trades_csv(result, trades_path)
    output_files["trades"] = trades_path

    # 資產曲線
    equity_path = os.path.join(output_dir, f"{prefix}_equity.csv")
    save_equity_curve_csv(result, equity_path)
    output_files["equity"] = equity_path

    # Markdown 報告
    report_path = os.path.join(output_dir, f"{prefix}_report.md")
    save_markdown_report(
        result=result,
        metrics=metrics,
        output_path=report_path,
        strategy_name=strategy_name,
        symbol=symbol,
        interval=interval,
    )
    output_files["report"] = report_path

    return output_files
