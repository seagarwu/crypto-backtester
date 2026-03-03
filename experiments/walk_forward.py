"""
Walk-Forward Testing 模組

執行 Walk-forward analysis，評估策略在不同時間區間的穩定性。
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from backtest import BacktestEngine
from metrics import calculate_metrics
from experiments.grid_search import run_grid_search, get_best_params


def create_folds(
    data: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    step_bars: Optional[int] = None,
) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    建立 Walk-forward folds

    注意：為了避免資料洩漏，train 和 test 區間是連續的（不重疊）。

    Args:
        data: 完整資料
        train_bars: 訓練區間 bars 數
        test_bars: 測試區間 bars 數
        step_bars: 每次移動的 bars 數，預設等於 train_bars

    Returns:
        [(train_df, test_df), ...] 的列表
    """
    if step_bars is None:
        step_bars = train_bars  # 預設滑動一個訓練期
    
    folds = []
    n = len(data)
    
    # 每個 fold: train 從 start 到 start+train_bars，test 從 start+train_bars 到 start+train_bars+test_bars
    start = 0
    while start + train_bars + test_bars <= n:
        train_df = data.iloc[start:start + train_bars].reset_index(drop=True)
        test_df = data.iloc[start + train_bars:start + train_bars + test_bars].reset_index(drop=True)
        
        folds.append((train_df, test_df))
        
        start += step_bars
    
    return folds


def run_walk_forward(
    data: pd.DataFrame,
    strategy_class,
    param_ranges: Dict[str, Any],
    train_bars: int,
    test_bars: int,
    step_bars: Optional[int] = None,
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    scoring: str = "sharpe",
) -> Dict[str, Any]:
    """
    執行 Walk-forward testing

    Args:
        data: 完整歷史資料
        strategy_class: 策略類別
        param_ranges: 參數範圍（用於訓練期優化）
        train_bars: 訓練期 bars 數
        test_bars: 測試期 bars 數
        step_bars: 每次移動 bars 數
        initial_capital: 初始資金
        commission_rate: 手續費率
        scoring: 評分標準

    Returns:
        包含 folds_results 和 stitched_equity 的字典
    """
    if step_bars is None:
        step_bars = test_bars
    
    # 建立 folds
    folds = create_folds(data, train_bars, test_bars, step_bars)
    
    print(f"建立 {len(folds)} 個 fold")
    
    fold_results = []
    all_equity = []
    
    for i, (train_df, test_df) in enumerate(folds):
        print(f"\n{'='*50}")
        print(f"Fold {i+1}/{len(folds)}")
        print(f"  Train: {train_df['datetime'].iloc[0]} ~ {train_df['datetime'].iloc[-1]} ({len(train_df)} bars)")
        print(f"  Test:  {test_df['datetime'].iloc[0]} ~ {test_df['datetime'].iloc[-1]} ({len(test_df)} bars)")
        
        # 在訓練期做網格掃描找最佳參數
        grid_results = run_grid_search(
            data=train_df,
            strategy_class=strategy_class,
            param_ranges=param_ranges,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            scoring=scoring,
        )
        
        # 取得最佳參數
        try:
            best_params = get_best_params(grid_results, by=scoring)
            print(f"  最佳參數: {best_params}")
        except ValueError as e:
            print(f"  錯誤: 無法取得最佳參數 - {e}")
            continue
        
        # 用最佳參數在測試期執行回測
        strategy = strategy_class(**best_params)
        signals = strategy.on_data(test_df)
        
        engine = BacktestEngine(
            initial_capital=initial_capital,
            commission_rate=commission_rate,
        )
        test_result = engine.run(test_df, signals)
        
        # 計算指標
        test_metrics = calculate_metrics(test_result)
        
        # 記錄結果
        fold_result = {
            "fold": i + 1,
            "train_start": train_df["datetime"].iloc[0],
            "train_end": train_df["datetime"].iloc[-1],
            "test_start": test_df["datetime"].iloc[0],
            "test_end": test_df["datetime"].iloc[-1],
            **best_params,
            "test_total_return": test_metrics["total_return"],
            "test_annualized_return": test_metrics["annualized_return"],
            "test_max_drawdown": test_metrics["max_drawdown"],
            "test_sharpe_ratio": test_metrics["sharpe_ratio"],
            "test_sortino_ratio": test_metrics["sortino_ratio"],
            "test_calmar_ratio": test_metrics["calmar_ratio"],
            "test_total_trades": test_metrics["total_trades"],
            "test_win_rate": test_metrics["win_rate"],
            "train_best_score": grid_results[scoring].iloc[0] if len(grid_results) > 0 else None,
        }
        fold_results.append(fold_result)
        
        # 收集 equity curve（調整初始值）
        equity = test_result.equity_curve.copy()
        if all_equity:
            # 延續之前的 equity
            last_equity = all_equity[-1]["equity"].iloc[-1]
            equity["equity"] = equity["equity"] / equity["equity"].iloc[0] * last_equity
        
        all_equity.append(equity)
    
    # 合併 fold 結果
    folds_df = pd.DataFrame(fold_results)
    
    # 合併 equity curves
    stitched_equity = pd.concat(all_equity, ignore_index=True)
    
    # 計算整體統計
    summary = {
        "total_folds": len(folds_df),
        "avg_test_return": folds_df["test_total_return"].mean() if len(folds_df) > 0 else 0,
        "avg_test_sharpe": folds_df["test_sharpe_ratio"].mean() if len(folds_df) > 0 else 0,
        "avg_test_drawdown": folds_df["test_max_drawdown"].mean() if len(folds_df) > 0 else 0,
        "cumulative_return": (stitched_equity["equity"].iloc[-1] / stitched_equity["equity"].iloc[0] - 1) if len(stitched_equity) > 0 else 0,
    }
    
    return {
        "folds_results": folds_df,
        "stitched_equity": stitched_equity,
        "summary": summary,
    }
