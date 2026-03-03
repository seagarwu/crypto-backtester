"""
回測引擎測試
"""

import pytest
import pandas as pd
import numpy as np

from backtest import BacktestEngine, BacktestResult, run_backtest
from strategies.base import SignalType


class TestBacktestEngine:
    """測試回測引擎"""

    def test_init(self):
        """測試初始化"""
        engine = BacktestEngine(
            initial_capital=10000.0,
            commission_rate=0.001,
            position_size=1.0,
        )
        assert engine.initial_capital == 10000.0
        assert engine.commission_rate == 0.001
        assert engine.position_size == 1.0
        assert engine.current_capital == 10000.0

    def test_reset(self):
        """測試重置"""
        engine = BacktestEngine(initial_capital=10000.0)
        engine.current_capital = 5000.0
        engine.position = "some_position"

        engine.reset()

        assert engine.current_capital == 10000.0
        assert engine.position is None

    def test_run_with_no_signals(self):
        """測試無訊號的回測"""
        # 建立測試資料
        n = 50
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": list(range(100, 100 + n)),
            "volume": [1000] * n,
        })

        signals = pd.DataFrame({
            "datetime": df["datetime"],
            "signal": [SignalType.HOLD] * n,
        })

        engine = BacktestEngine(initial_capital=10000.0)
        result = engine.run(df, signals)

        assert isinstance(result, BacktestResult)
        assert result.total_trades == 0
        assert result.final_equity == 10000.0

    def test_run_with_buy_and_sell(self):
        """測試買入賣出訊號"""
        n = 100
        prices = [100] * 50 + [110] * 50  # 價格上漲

        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000] * n,
        })

        # 建立訊號：第 50 根買入，第 60 根賣出
        signals = pd.DataFrame({
            "datetime": df["datetime"],
            "signal": [SignalType.HOLD] * 49 + [SignalType.BUY] + [SignalType.HOLD] * 9 + [SignalType.SELL] + [SignalType.HOLD] * (n - 60),
        })

        engine = BacktestEngine(
            initial_capital=10000.0,
            commission_rate=0.001,
        )
        result = engine.run(df, signals)

        assert result.total_trades == 1
        assert result.final_equity > 0

    def test_run_invalid_data(self):
        """測試無效資料"""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=10, freq="h"),
            "open": [100] * 10,
            # 缺少 high, low, close
        })

        signals = pd.DataFrame({
            "datetime": df["datetime"],
            "signal": [0] * 10,
        })

        engine = BacktestEngine()

        with pytest.raises(ValueError):
            engine.run(df, signals)

    def test_equity_curve(self):
        """測試資產曲線"""
        n = 30
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": list(range(100, 100 + n)),
            "volume": [1000] * n,
        })

        signals = pd.DataFrame({
            "datetime": df["datetime"],
            "signal": [0] * n,
        })

        engine = BacktestEngine(initial_capital=10000.0)
        result = engine.run(df, signals)

        # 檢查資產曲線（會有 n 或 n+1 行，取決於結束時是否多記錄一筆）
        assert len(result.equity_curve) >= n
        assert "equity" in result.equity_curve.columns
        assert "capital" in result.equity_curve.columns


class TestRunBacktest:
    """測試便捷函數"""

    def test_run_backtest_function(self):
        """測試 run_backtest 函數"""
        n = 30
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=n, freq="h"),
            "open": [100] * n,
            "high": [105] * n,
            "low": [95] * n,
            "close": [100 + i for i in range(n)],
            "volume": [1000] * n,
        })

        signals = pd.DataFrame({
            "datetime": df["datetime"],
            "signal": [0] * n,
        })

        result = run_backtest(df, signals, initial_capital=5000.0)

        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 5000.0


class TestBacktestResult:
    """測試 BacktestResult 資料類別"""

    def test_backtest_result_creation(self):
        """測試建立 BacktestResult"""
        equity_curve = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=10, freq="h"),
            "equity": [10000] * 10,
        })

        result = BacktestResult(
            equity_curve=equity_curve,
            trades=[],
            final_equity=10000.0,
            initial_capital=10000.0,
            total_return=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
        )

        assert result.final_equity == 10000.0
