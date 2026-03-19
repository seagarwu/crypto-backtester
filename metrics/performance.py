"""
績效指標計算模組

計算各種量化策略常用的績效指標。
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional

from backtest import BacktestResult, Trade


def _get_result_attr(result: Any, name: str, default: Any = None) -> Any:
    """從不同回測結果型別中安全取值。"""
    if hasattr(result, name):
        return getattr(result, name)

    config = getattr(result, "config", None)
    if config is not None and hasattr(config, name):
        return getattr(config, name)

    return default


def _trade_pnl(trade: Any) -> float:
    """支援 dataclass Trade 與 dict trade payload。"""
    if hasattr(trade, "pnl"):
        return float(trade.pnl)
    if isinstance(trade, dict):
        return float(trade.get("pnl", 0.0))
    return 0.0


def calculate_returns(equity_curve: pd.DataFrame) -> pd.Series:
    """
    計算收益率序列

    Args:
        equity_curve: 資產曲線 DataFrame

    Returns:
        收益率 Series
    """
    equity = equity_curve["equity"]
    returns = equity.pct_change().fillna(0)
    return returns


def calculate_annualized_return(total_return: float, days: int) -> float:
    """
    計算年化報酬率

    Args:
        total_return: 總報酬率（如 0.2 = 20%）
        days: 天數

    Returns:
        年化報酬率
    """
    if days <= 0:
        return 0.0
    years = days / 365.0
    return (1 + total_return) ** (1 / years) - 1


def calculate_max_drawdown(equity_curve: pd.DataFrame) -> float:
    """
    計算最大回撤

    Args:
        equity_curve: 資產曲線 DataFrame

    Returns:
        最大回撤（負值，如 -0.2 = 20%）
    """
    equity = equity_curve["equity"]
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    return drawdown.min()


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365 * 24,  # 假設是小時資料
) -> float:
    """
    計算 Sharpe Ratio

    Args:
        returns: 收益率序列
        risk_free_rate: 無風險利率（年化）
        periods_per_year: 每年資料點數

    Returns:
        Sharpe Ratio
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0

    # 年化
    mean_return = returns.mean() * periods_per_year
    std_return = returns.std() * np.sqrt(periods_per_year)

    sharpe = (mean_return - risk_free_rate) / std_return
    return sharpe


def calculate_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365 * 24,
    target_return: float = 0.0,
) -> float:
    """
    計算 Sortino Ratio

    Args:
        returns: 收益率序列
        risk_free_rate: 無風險利率（年化）
        periods_per_year: 每年資料點數
        target_return: 目標收益（預設 0）

    Returns:
        Sortino Ratio
    """
    if len(returns) == 0:
        return 0.0

    # 年化
    mean_return = returns.mean() * periods_per_year

    # 只計算下行標準差
    downside_returns = returns[returns < target_return]
    if len(downside_returns) == 0:
        return float("inf") if mean_return > risk_free_rate else 0.0

    downside_std = downside_returns.std() * np.sqrt(periods_per_year)

    if downside_std == 0:
        return float("inf") if mean_return > risk_free_rate else 0.0

    sortino = (mean_return - risk_free_rate) / downside_std
    return sortino


def calculate_win_rate(trades: List[Trade]) -> float:
    """
    計算勝率

    Args:
        trades: 交易記錄列表

    Returns:
        勝率（0-1）
    """
    if not trades:
        return 0.0

    wins = sum(1 for t in trades if _trade_pnl(t) > 0)
    return wins / len(trades)


def calculate_profit_factor(trades: List[Trade]) -> float:
    """
    計算盈利因子（Profit Factor）

    Args:
        trades: 交易記錄列表

    Returns:
        盈利因子 = 總盈利 / 總虧損
    """
    if not trades:
        return 0.0

    total_profit = sum(_trade_pnl(t) for t in trades if _trade_pnl(t) > 0)
    total_loss = abs(sum(_trade_pnl(t) for t in trades if _trade_pnl(t) < 0))

    if total_loss == 0:
        return float("inf") if total_profit > 0 else 0.0

    return total_profit / total_loss


def calculate_avg_win_loss(trades: List[Trade]) -> float:
    """
    計算平均盈虧比

    Args:
        trades: 交易記錄列表

    Returns:
        平均盈利 / 平均虧損的絕對值
    """
    if not trades:
        return 0.0

    wins = [_trade_pnl(t) for t in trades if _trade_pnl(t) > 0]
    losses = [_trade_pnl(t) for t in trades if _trade_pnl(t) < 0]

    if not wins or not losses:
        return 0.0

    avg_win = np.mean(wins)
    avg_loss = abs(np.mean(losses))

    return avg_win / avg_loss if avg_loss > 0 else 0.0


def calculate_calmar_ratio(
    total_return: float,
    max_drawdown: float,
    years: float,
) -> float:
    """
    計算 Calmar Ratio

    Args:
        total_return: 總報酬率
        max_drawdown: 最大回撤（負值）
        years: 投資年數

    Returns:
        Calmar Ratio
    """
    if max_drawdown == 0 or years == 0:
        return 0.0

    annualized_return = calculate_annualized_return(total_return, int(years * 365))
    return annualized_return / abs(max_drawdown)


def calculate_metrics(
    result: BacktestResult,
    periods_per_year: int = 365 * 24,
) -> Dict[str, Any]:
    """
    計算完整的績效指標

    Args:
        result: BacktestResult 物件
        periods_per_year: 每年資料點數（用於年化計算）

    Returns:
        包含所有指標的字典
    """
    # 基本資料
    equity_curve = getattr(result, "equity_curve", None)
    if equity_curve is None:
        raise ValueError("result 缺少 equity_curve，無法計算績效指標")

    trades = list(getattr(result, "trades", []) or [])

    initial_capital = _get_result_attr(result, "initial_capital")
    if initial_capital is None:
        raise ValueError("result 缺少 initial_capital，無法計算績效指標")

    final_equity = _get_result_attr(result, "final_equity")
    if final_equity is None:
        total_return_pct = getattr(result, "total_return", None)
        if total_return_pct is not None:
            final_equity = initial_capital * (1 + float(total_return_pct) / 100.0)
        else:
            raise ValueError("result 缺少 final_equity，無法計算績效指標")

    # 時間範圍
    if len(equity_curve) > 1:
        start_date = equity_curve["datetime"].iloc[0]
        end_date = equity_curve["datetime"].iloc[-1]
        days = (end_date - start_date).days
    else:
        days = 0
        start_date = None
        end_date = None

    # 收益率
    returns = calculate_returns(equity_curve)

    # 總報酬率
    total_return = (final_equity - initial_capital) / initial_capital

    # 年化報酬率
    annualized_return = calculate_annualized_return(total_return, days) if days > 0 else 0.0

    # 最大回撤
    max_drawdown = calculate_max_drawdown(equity_curve)

    # Sharpe Ratio（假設無風險利率為 0）
    sharpe_ratio = calculate_sharpe_ratio(returns, 0, periods_per_year)

    # Sortino Ratio
    sortino_ratio = calculate_sortino_ratio(returns, 0, periods_per_year)

    # 交易統計
    total_trades = len(trades)
    winning_trades = int(
        getattr(result, "winning_trades", sum(1 for t in trades if _trade_pnl(t) > 0))
    )
    losing_trades = int(
        getattr(result, "losing_trades", sum(1 for t in trades if _trade_pnl(t) < 0))
    )
    win_rate = calculate_win_rate(trades)

    # 盈利因子
    profit_factor = calculate_profit_factor(trades)

    # 平均盈虧比
    avg_win_loss = calculate_avg_win_loss(trades)

    # Calmar Ratio
    years = days / 365.0
    calmar_ratio = calculate_calmar_ratio(total_return, max_drawdown, years)

    return {
        # 基本資訊
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "initial_capital": initial_capital,
        "final_equity": final_equity,
        # 報酬率
        "total_return": total_return,
        "total_return_pct": total_return * 100,
        "annualized_return": annualized_return,
        "annualized_return_pct": annualized_return * 100,
        # 風險指標
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown * 100,
        # 風險調整報酬
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        # 交易統計
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "win_rate_pct": win_rate * 100,
        "profit_factor": profit_factor,
        "avg_win_loss_ratio": avg_win_loss,
    }


def print_metrics(metrics: Dict[str, Any]) -> None:
    """
    格式化列印績效指標

    Args:
        metrics: 績效指標字典
    """
    print("\n" + "=" * 50)
    print("📊 回測績效報告")
    print("=" * 50)

    # 基本資訊
    print(f"\n📅 時間範圍")
    print(f"  開始日期: {metrics.get('start_date', 'N/A')}")
    print(f"  結束日期: {metrics.get('end_date', 'N/A')}")
    print(f"  天數: {metrics.get('days', 0)} 天")

    print(f"\n💰 資金")
    print(f"  初始資金: ${metrics['initial_capital']:,.2f}")
    print(f"  最終資產: ${metrics['final_equity']:,.2f}")

    print(f"\n📈 報酬率")
    print(f"  總報酬率: {metrics['total_return_pct']:.2f}%")
    print(f"  年化報酬率: {metrics['annualized_return_pct']:.2f}%")

    print(f"\n⚠️ 風險")
    print(f"  最大回撤: {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Calmar Ratio: {metrics['calmar_ratio']:.2f}")

    print(f"\n📊 風險調整報酬")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"  Sortino Ratio: {metrics['sortino_ratio']:.2f}")

    print(f"\n🔄 交易統計")
    print(f"  總交易次數: {metrics['total_trades']}")
    print(f"  獲勝次數: {metrics['winning_trades']}")
    print(f"  虧損次數: {metrics['losing_trades']}")
    print(f"  勝率: {metrics['win_rate_pct']:.2f}%")
    print(f"  盈利因子: {metrics['profit_factor']:.2f}")
    print(f"  平均盈虧比: {metrics['avg_win_loss_ratio']:.2f}")

    print("\n" + "=" * 50 + "\n")
