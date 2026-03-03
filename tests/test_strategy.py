"""
均線交叉策略測試
"""

import pytest
import pandas as pd
import numpy as np

from strategies.ma_crossover import MACrossoverStrategy, create_ma_crossover_strategy
from strategies.base import SignalType


class TestMACrossoverStrategy:
    """測試均線交叉策略"""

    def test_init(self):
        """測試初始化"""
        strategy = MACrossoverStrategy(short_window=10, long_window=20)
        assert strategy.short_window == 10
        assert strategy.long_window == 20

    def test_invalid_parameters(self):
        """測試無效參數"""
        # short_window >= long_window
        with pytest.raises(ValueError):
            MACrossoverStrategy(short_window=50, long_window=20)

        # 負數參數
        with pytest.raises(ValueError):
            MACrossoverStrategy(short_window=-1, long_window=20)

    def test_generate_signals_uptrend(self):
        """測試上升趨勢的訊號"""
        # 建立價格上漲的測試資料
        np.random.seed(42)
        n = 100
        prices = 100 + np.cumsum(np.random.normal(1, 2, n))

        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": prices * 0.99,
            "high": prices * 1.02,
            "low": prices * 0.98,
            "close": prices,
            "volume": np.random.uniform(100, 1000, n),
        })

        strategy = MACrossoverStrategy(short_window=10, long_window=30)
        result = strategy.generate_signals(df)

        # 檢查訊號欄位存在
        assert "signal" in result.columns

        # 檢查 MA 欄位
        assert "ma_short" in result.columns
        assert "ma_long" in result.columns

    def test_generate_signals_with_buy_signal(self):
        """測試買入訊號"""
        # 建立明確的黃金交叉資料
        prices = [100] * 30 + [110] * 30 + [120] * 30  # 價格上漲
        # 前面低於均線，後面高於均線

        n = len(prices)
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000] * n,
        })

        strategy = MACrossoverStrategy(short_window=10, long_window=20)
        result = strategy.generate_signals(df)

        # 應該有買入訊號
        buy_signals = (result["signal"] == SignalType.BUY).sum()
        assert buy_signals >= 1

    def test_generate_signals_with_sell_signal(self):
        """測試賣出訊號"""
        # 建立價格下跌的資料
        prices = [120] * 30 + [110] * 30 + [100] * 30  # 價格下跌

        n = len(prices)
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000] * n,
        })

        strategy = MACrossoverStrategy(short_window=10, long_window=20)
        result = strategy.generate_signals(df)

        # 應該有賣出訊號
        sell_signals = (result["signal"] == SignalType.SELL).sum()
        assert sell_signals >= 1

    def test_get_params(self):
        """測試取得參數"""
        strategy = MACrossoverStrategy(short_window=15, long_window=40)
        params = strategy.get_params()

        assert params["short_window"] == 15
        assert params["long_window"] == 40

    def test_repr(self):
        """測試 __repr__"""
        strategy = MACrossoverStrategy(short_window=20, long_window=50)
        assert "short=20" in repr(strategy)
        assert "long=50" in repr(strategy)


class TestConvenienceFunction:
    """測試便捷函數"""

    def test_create_ma_crossover_strategy(self):
        """測試建立策略函數"""
        strategy = create_ma_crossover_strategy(short_window=10, long_window=30)
        assert isinstance(strategy, MACrossoverStrategy)
        assert strategy.short_window == 10
        assert strategy.long_window == 30
