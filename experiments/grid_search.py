"""
參數網格掃描模組 (Grid Search)

針對策略參數進行網格掃描，找出最優參數組合。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from itertools import product

from backtest import BacktestEngine
from metrics import calculate_metrics


def calculate_practical_score(result_row: Dict[str, Any]) -> float:
    """
    計算實盤導向評分

    綜合考量 Sharpe/Sortino/Calmar、獲利因子、
    最大回撤與交易次數，降低只看單一指標造成的偏差。
    """
    required = [
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown",
        "profit_factor",
        "total_trades",
    ]
    if any(pd.isna(result_row.get(key)) for key in required):
        return np.nan

    # 風險懲罰：回撤超過 25% 開始扣分
    max_drawdown = float(result_row["max_drawdown"])
    drawdown_penalty = max(0.0, abs(max_drawdown) - 0.25)

    # 成本敏感度代理：交易次數越多，保守扣分
    total_trades = float(result_row["total_trades"])
    trade_penalty = total_trades / 1000.0

    score = (
        0.40 * float(result_row["sharpe_ratio"])
        + 0.20 * float(result_row["sortino_ratio"])
        + 0.20 * float(result_row["calmar_ratio"])
        + 0.20 * float(result_row["profit_factor"])
        - 0.80 * drawdown_penalty
        - 0.25 * trade_penalty
    )
    return score


def generate_parameter_grid(param_ranges: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    產生參數網格

    Args:
        param_ranges: 參數範圍字典
            例如: {"short_window": [10, 20], "long_window": [50, 100]}

    Returns:
        參數組合列表
    """
    keys = list(param_ranges.keys())
    values = list(param_ranges.values())
    
    combinations = list(product(*values))
    return [dict(zip(keys, combo)) for combo in combinations]


def run_grid_search(
    data: pd.DataFrame,
    strategy_class,
    param_ranges: Dict[str, Any],
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    scoring: str = "sharpe",
    execution_price: str = "next_open",
) -> pd.DataFrame:
    """
    執行參數網格掃描

    Args:
        data: OHLCV 資料
        strategy_class: 策略類別
        param_ranges: 參數範圍
        initial_capital: 初始資金
        commission_rate: 手續費率
        scoring: 評分指標 (sharpe, total_return, calmar)
        execution_price: 執行價格模式

    Returns:
        結果 DataFrame
    """
    # 產生參數網格
    param_grid = generate_parameter_grid(param_ranges)
    
    results = []
    total = len(param_grid)
    
    print(f"開始網格掃描: {total} 個參數組合")
    
    for i, params in enumerate(param_grid):
        print(f"  [{i+1}/{total}] 測試參數: {params}")
        
        try:
            # 建立策略實例
            strategy = strategy_class(**params)
            
            # 產生訊號
            signals = strategy.on_data(data)
            
            # 執行回測
            engine = BacktestEngine(
                initial_capital=initial_capital,
                commission_rate=commission_rate,
            )
            result = engine.run(data, signals)
            
            # 計算指標
            metrics = calculate_metrics(result)
            
            # 記錄結果
            row = {
                **params,
                "total_return": metrics["total_return"],
                "annualized_return": metrics["annualized_return"],
                "max_drawdown": metrics["max_drawdown"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "sortino_ratio": metrics["sortino_ratio"],
                "calmar_ratio": metrics["calmar_ratio"],
                "total_trades": metrics["total_trades"],
                "win_rate": metrics["win_rate"],
                "profit_factor": metrics["profit_factor"],
            }
            row["practical_score"] = calculate_practical_score(row)
            results.append(row)
            
        except Exception as e:
            print(f"    錯誤: {e}")
            # 記錄失敗的參數
            results.append({
                **params,
                "total_return": None,
                "annualized_return": None,
                "max_drawdown": None,
                "sharpe_ratio": None,
                "sortino_ratio": None,
                "calmar_ratio": None,
                "total_trades": None,
                "win_rate": None,
                "profit_factor": None,
                "practical_score": None,
                "error": str(e),
            })
    
    # 轉換為 DataFrame
    df = pd.DataFrame(results)
    
    # 排序
    if scoring and scoring in df.columns:
        df = df.sort_values(scoring, ascending=False, na_position="last")
    
    print(f"網格掃描完成: {len(df)} 個結果")
    
    return df


def select_top_k(
    results_df: pd.DataFrame,
    k: int = 10,
    by: str = "sharpe_ratio",
) -> pd.DataFrame:
    """
    選擇 Top K 參數組合

    Args:
        results_df: 網格掃描結果
        k: 選擇數量
        by: 排序依據欄位

    Returns:
        Top K 結果
    """
    df = results_df.copy()
    
    # 移除有錯誤的列（如果 error 欄位存在）
    if "error" in df.columns:
        df = df[df["error"].isna()]
    
    # 排序並取 Top K
    if by in df.columns:
        df = df.sort_values(by, ascending=False, na_position="last")
    
    return df.head(k)


def get_best_params(
    results_df: pd.DataFrame,
    by: str = "sharpe_ratio",
) -> Dict[str, Any]:
    """
    取得最佳參數

    Args:
        results_df: 網格掃描結果
        by: 排序依據欄位

    Returns:
        最佳參數字典
    """
    top = select_top_k(results_df, k=1, by=by)
    
    if top.empty:
        raise ValueError("沒有有效的結果")
    
    # 取得參數欄位
    param_cols = [col for col in top.columns
                  if col not in ["total_return", "annualized_return", "max_drawdown",
                                 "sharpe_ratio", "sortino_ratio", "calmar_ratio",
                                 "total_trades", "win_rate", "profit_factor",
                                 "practical_score", "error"]]
    
    best_params = {}
    for col in param_cols:
        best_params[col] = top[col].iloc[0]
    
    return best_params
