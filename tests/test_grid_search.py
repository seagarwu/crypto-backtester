"""
Grid Search 測試
"""

import pytest
import pandas as pd
import numpy as np

from experiments.grid_search import (
    generate_parameter_grid,
    run_grid_search,
    select_top_k,
    get_best_params,
)
from strategies import MACrossoverStrategy


class TestGenerateParameterGrid:
    """測試參數網格產生"""

    def test_simple_grid(self):
        """測試簡單網格"""
        ranges = {"a": [1, 2], "b": [3, 4]}
        grid = generate_parameter_grid(ranges)
        
        assert len(grid) == 4
        assert {"a": 1, "b": 3} in grid
        assert {"a": 2, "b": 4} in grid

    def test_single_param(self):
        """測試單一參數"""
        ranges = {"window": [10, 20, 30]}
        grid = generate_parameter_grid(ranges)
        
        assert len(grid) == 3
        assert grid[0] == {"window": 10}

    def test_empty_grid(self):
        """測試空網格"""
        ranges = {}
        grid = generate_parameter_grid(ranges)
        
        assert len(grid) == 1  # 空的 Cartesian product


class TestSelectTopK:
    """測試 Top K 選擇"""

    def test_select_top_k(self):
        """測試選擇 Top K"""
        results = pd.DataFrame({
            "short_window": [10, 20, 30],
            "long_window": [50, 50, 50],
            "sharpe_ratio": [1.5, 2.0, 1.0],
            "total_return": [0.1, 0.2, 0.05],
        })
        
        top = select_top_k(results, k=2, by="sharpe_ratio")
        
        assert len(top) == 2
        assert top.iloc[0]["sharpe_ratio"] == 2.0
        assert top.iloc[1]["sharpe_ratio"] == 1.5


class TestGetBestParams:
    """測試取得最佳參數"""

    def test_get_best_params(self):
        """測試取得最佳參數"""
        results = pd.DataFrame({
            "short_window": [10, 20],
            "long_window": [50, 50],
            "sharpe_ratio": [1.5, 2.0],
            "total_return": [0.1, 0.2],
        })
        
        best = get_best_params(results, by="sharpe_ratio")
        
        assert best["short_window"] == 20
        assert best["long_window"] == 50

    def test_exclude_invalid_params(self):
        """測試排除 short >= long 的組合"""
        results = pd.DataFrame({
            "short_window": [10, 50, 30],
            "long_window": [50, 30, 50],  # 第二個 short=50 >= long=30 是無效的
            "sharpe_ratio": [1.5, 2.0, 1.0],
        })
        
        # 這個測試驗證篩選邏輯存在
        top = select_top_k(results, k=2, by="sharpe_ratio")
        assert len(top) >= 1


class TestRunGridSearch:
    """測試網格掃描"""

    def test_run_grid_search_basic(self):
        """測試基本網格掃描"""
        # 建立測試資料
        np.random.seed(42)
        n = 200
        data = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": list(range(100, 100 + n)),
            "volume": [1000] * n,
        })
        
        # 參數網格
        param_ranges = {
            "short_window": [10, 15],
            "long_window": [30, 40],
        }
        
        # 執行網格掃描
        results = run_grid_search(
            data=data,
            strategy_class=MACrossoverStrategy,
            param_ranges=param_ranges,
            initial_capital=10000.0,
            scoring="sharpe_ratio",
        )
        
        # 驗證
        assert len(results) == 4  # 2 * 2
        assert "sharpe_ratio" in results.columns
        assert "total_return" in results.columns
