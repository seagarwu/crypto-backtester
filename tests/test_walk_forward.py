"""
Walk-Forward Testing 測試
"""

import pytest
import pandas as pd
import numpy as np

from experiments.walk_forward import (
    create_folds,
    run_walk_forward,
)
from strategies import MACrossoverStrategy


class TestCreateFolds:
    """測試 Fold 建立"""

    def test_create_folds_basic(self):
        """測試基本 fold 建立"""
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=100, freq="h"),
            "close": list(range(100)),
        })
        
        # train=30, test=20, step=20
        # 可建立: (0-30, 30-50), (20-50, 50-70), (40-70, 70-90)
        # 但最後一個需要 train_bars + test_bars = 50 <= 100
        # 所以是: 0-30/30-50, 20-50/50-70, 40-70/70-90 (3個)
        folds = create_folds(data, train_bars=30, test_bars=20, step_bars=20)
        
        # 驗證 fold 數量 (100 - 30) / 20 = 3.5，取 3
        assert len(folds) == 3
        
        # 第一個 fold
        assert len(folds[0][0]) == 30  # train
        assert len(folds[0][1]) == 20  # test

    def test_create_folds_no_overlap(self):
        """測試 folds 的 test 區間不越界"""
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=100, freq="h"),
            "close": list(range(100)),
        })
        
        folds = create_folds(data, train_bars=30, test_bars=20, step_bars=30)
        
        # 驗證每個 test 區間都在資料範圍內
        for train_df, test_df in folds:
            assert len(test_df) == 20  # test_bars
            # test 的最後一筆不應超過原始資料最後一筆
            assert test_df.index.max() < len(data)

    def test_create_folds_with_default_step(self):
        """測試預設 step 等於 train_bars"""
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=100, freq="h"),
            "close": list(range(100)),
        })
        
        # 不指定 step_bars，預設等於 train_bars
        folds = create_folds(data, train_bars=30, test_bars=20)
        
        # 100 - 30 = 70, 70 / 30 = 2.33, 取 2
        assert len(folds) == 2


class TestRunWalkForward:
    """測試 Walk-Forward 執行"""

    def test_run_walk_forward_basic(self):
        """測試基本 Walk-Forward"""
        # 建立測試資料
        np.random.seed(42)
        n = 150
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": list(100 + np.random.randn(n).cumsum()),
            "volume": [1000] * n,
        })
        
        param_ranges = {
            "short_window": [10],
            "long_window": [30],
        }
        
        result = run_walk_forward(
            data=data,
            strategy_class=MACrossoverStrategy,
            param_ranges=param_ranges,
            train_bars=50,
            test_bars=30,
            step_bars=30,
            initial_capital=10000.0,
            scoring="sharpe_ratio",
        )
        
        # 驗證結果結構
        assert "folds_results" in result
        assert "stitched_equity" in result
        assert "summary" in result
        
        # 驗證 folds 數量
        assert len(result["folds_results"]) >= 1
        
        # 驗證 stitched equity
        assert len(result["stitched_equity"]) > 0
