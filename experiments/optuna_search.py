"""
Optuna 貝葉斯優化模組

使用 Optuna 的 TPE (Tree-structured Parzen Estimator) 演算法進行高效的參數優化。
"""

from typing import Dict, Any, Optional, Callable, List
import pandas as pd
import numpy as np
import optuna
from optuna.samplers import TPESampler

from backtest import BacktestEngine
from metrics import calculate_metrics


def suggest_params(trial: optuna.Trial, param_space: Dict[str, Any]) -> Dict[str, Any]:
    """
    根據參數空間建議參數

    Args:
        trial: Optuna trial
        param_space: 參數空間定義
            支援類型:
            - categorical: ["a", "b", "c"]
            - int: {"low": 1, "high": 100}
            - uniform: {"low": 0.0, "high": 1.0}
            - log_uniform: {"low": 0.001, "high": 1.0, "log": True}

    Returns:
        參數字典
    """
    params = {}
    
    for name, config in param_space.items():
        if isinstance(config, list):
            # 分類參數
            params[name] = trial.suggest_categorical(name, config)
        elif isinstance(config, dict):
            if config.get("log", False):
                # 對數均勻分布
                params[name] = trial.suggest_float(
                    name, 
                    config["low"], 
                    config["high"],
                    log=True
                )
            elif config.get("step", 1) > 1:
                # 整數間距
                params[name] = trial.suggest_int(
                    name,
                    config["low"],
                    config["high"],
                    step=config["step"]
                )
            elif "type" in config and config["type"] == "int":
                # 整數參數
                params[name] = trial.suggest_int(
                    name,
                    config["low"],
                    config["high"]
                )
            else:
                # 浮點數均勻分布
                params[name] = trial.suggest_float(
                    name,
                    config["low"],
                    config["high"]
                )
        else:
            raise ValueError(f"不支持的參數類型: {name} = {config}")
    
    return params


def run_optuna_optimization(
    data: pd.DataFrame,
    strategy_class,
    param_space: Dict[str, Any],
    objective: str = "sharpe_ratio",
    n_trials: int = 100,
    timeout: Optional[int] = None,
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    direction: str = "maximize",
    n_jobs: int = 1,
    show_progress: bool = True,
    constraints: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    執行 Optuna 貝葉斯優化

    Args:
        data: OHLCV 資料
        strategy_class: 策略類別
        param_space: 參數空間
            例如: {
                "short_window": {"low": 5, "high": 50, "type": "int"},
                "long_window": {"low": 20, "high": 200, "type": "int"},
            }
        objective: 優化目標 (sharpe_ratio, total_return, calmar_ratio, etc.)
        n_trials: 試驗次數
        timeout: 超時秒數
        initial_capital: 初始資金
        commission_rate: 手續費率
        direction: 優化方向 ("maximize" 或 "minimize")
        n_jobs: 並行任務數
        show_progress: 是否顯示進度
        constraints: 約束函數 (params -> bool)

    Returns:
        包含最佳參數和結果的字典
    """
    
    def objective_wrapper(trial: optuna.Trial) -> float:
        # 建議參數
        params = suggest_params(trial, param_space)
        
        # 檢查約束
        if constraints and not constraints(params):
            raise optuna.exceptions.TrialPruned("Constraint not satisfied")
        
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
            
            # 取得目標值
            if objective in metrics:
                value = metrics[objective]
                if value is None or pd.isna(value):
                    raise optuna.exceptions.TrialPruned("Invalid metric value")
                return value
            else:
                raise ValueError(f"Unknown objective: {objective}")
                
        except Exception as e:
            raise optuna.exceptions.TrialPruned(str(e))
    
    # 建立 study
    sampler = TPESampler(seed=42)
    study = optuna.create_study(
        direction=direction,
        sampler=sampler,
        study_name="strategy_optimization"
    )
    
    # 執行優化
    if show_progress:
        print(f"🚀 開始 Optuna 優化...")
        print(f"   目標: {objective}")
        print(f"   試驗次數: {n_trials}")
        if timeout:
            print(f"   超時: {timeout} 秒")
        print(f"   參數空間: {param_space}")
    
    study.optimize(
        objective_wrapper,
        n_trials=n_trials,
        timeout=timeout,
        n_jobs=n_jobs,
        show_progress_bar=show_progress,
    )
    
    # 取得最佳參數
    best_params = study.best_params
    
    # 執行最終回測以獲取完整指標
    best_strategy = strategy_class(**best_params)
    signals = best_strategy.on_data(data)
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission_rate=commission_rate,
    )
    final_result = engine.run(data, signals)
    final_metrics = calculate_metrics(final_result)
    
    return {
        "best_params": best_params,
        "best_value": study.best_value,
        "best_trial": study.best_trial.number,
        "n_trials": len(study.trials),
        "study": study,
        "final_metrics": final_metrics,
    }


def run_optuna_with_walk_forward(
    data: pd.DataFrame,
    strategy_class,
    param_space: Dict[str, Any],
    train_bars: int,
    test_bars: int,
    step_bars: Optional[int] = None,
    n_trials: int = 50,
    objective: str = "sharpe_ratio",
    initial_capital: float = 10000.0,
    commission_rate: float = 0.001,
    scoring: str = "sharpe_ratio",
    show_progress: bool = True,
) -> Dict[str, Any]:
    """
    結合 Optuna 優化的 Walk-Forward Testing

    在每個訓練期使用 Optuna 找到最佳參數，然後在測試期驗證。

    Args:
        data: 完整歷史資料
        strategy_class: 策略類別
        param_space: 參數空間
        train_bars: 訓練期 bars 數
        test_bars: 測試期 bars 數
        step_bars: 每次移動 bars 數
        n_trials: 每個訓練期的 Optuna 試驗次數
        objective: Optuna 優化目標
        initial_capital: 初始資金
        commission_rate: 手續費率
        scoring: 測試期評分標準
        show_progress: 是否顯示進度

    Returns:
        包含所有 fold 結果的字典
    """
    from experiments.walk_forward import create_folds
    
    if step_bars is None:
        step_bars = test_bars
    
    # 建立 folds
    folds = create_folds(data, train_bars, test_bars, step_bars)
    
    if show_progress:
        print(f"🔄 Walk-Forward + Optuna 優化")
        print(f"   總 Fold 數: {len(folds)}")
        print(f"   訓練期: {train_bars} bars")
        print(f"   測試期: {test_bars} bars")
        print(f"   Optuna 試驗: {n_trials}/fold")
    
    fold_results = []
    all_equity = []
    
    for i, (train_df, test_df) in enumerate(folds):
        if show_progress:
            print(f"\n{'='*50}")
            print(f"Fold {i+1}/{len(folds)}")
            print(f"  Train: {train_df['datetime'].iloc[0]} ~ {train_df['datetime'].iloc[-1]}")
            print(f"  Test:  {test_df['datetime'].iloc[0]} ~ {test_df['datetime'].iloc[-1]}")
        
        # 在訓練期執行 Optuna 優化
        optuna_result = run_optuna_optimization(
            data=train_df,
            strategy_class=strategy_class,
            param_space=param_space,
            objective=objective,
            n_trials=n_trials,
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            direction="maximize",
            show_progress=show_progress,
        )
        
        best_params = optuna_result["best_params"]
        
        if show_progress:
            print(f"  最佳參數: {best_params}")
            print(f"  訓練期 {objective}: {optuna_result['best_value']:.4f}")
        
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
            "train_best_score": optuna_result["best_value"],
            "test_total_return": test_metrics["total_return"],
            "test_annualized_return": test_metrics["annualized_return"],
            "test_max_drawdown": test_metrics["max_drawdown"],
            "test_sharpe_ratio": test_metrics["sharpe_ratio"],
            "test_sortino_ratio": test_metrics["sortino_ratio"],
            "test_calmar_ratio": test_metrics["calmar_ratio"],
            "test_total_trades": test_metrics["total_trades"],
            "test_win_rate": test_metrics["win_rate"],
        }
        fold_results.append(fold_result)
        
        # 收集 equity curve
        equity = test_result.equity_curve.copy()
        if all_equity:
            last_equity = all_equity[-1]["equity"].iloc[-1]
            equity["equity"] = equity["equity"] / equity["equity"].iloc[0] * last_equity
        all_equity.append(equity)
    
    # 合併結果
    folds_df = pd.DataFrame(fold_results)
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
