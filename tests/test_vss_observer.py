"""
市場觀察器測試

測試 MarketObserver 與 BacktestObserver 功能。
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from vss.observer import MarketObserver, BacktestObserver
from vss.analyzer import VSSAnalyzer
from vss.types import VSSAnalysisResult, TrendDirection


def generate_test_data(n_bars: int = 100) -> pd.DataFrame:
    """生成測試用 K 線數據"""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1h')
    prices = 50000 + np.cumsum(np.random.randn(n_bars) * 100)
    
    df = pd.DataFrame({
        'open': prices * 0.99,
        'high': prices * 1.02,
        'low': prices * 0.98,
        'close': prices,
        'volume': np.random.randint(1000, 10000, n_bars),
    }, index=dates)
    
    return df


class TestMarketObserverInit:
    """測試 MarketObserver 初始化"""
    
    def test_default_init(self):
        observer = MarketObserver()
        
        assert observer.analyzer is not None
        assert observer.callback is None
        assert observer.symbols == ["BTCUSDT"]
        assert observer.intervals == ["1h"]
    
    def test_custom_init(self):
        analyzer = VSSAnalyzer(short_window=10)
        callback = Mock()
        
        observer = MarketObserver(
            analyzer=analyzer,
            callback=callback,
            symbols=["ETHUSDT", "SOLUSDT"],
            intervals=["15m", "1h"],
        )
        
        assert observer.analyzer == analyzer
        assert observer.callback == callback
        assert observer.symbols == ["ETHUSDT", "SOLUSDT"]
        assert observer.intervals == ["15m", "1h"]


class TestMarketObserverDataManagement:
    """測試數據管理"""
    
    def test_load_historical_data(self):
        observer = MarketObserver()
        df = generate_test_data(100)
        
        observer.load_historical_data("BTCUSDT", "1h", df)
        
        key = "BTCUSDT_1h"
        assert key in observer._data_cache
        assert len(observer._data_cache[key]) == 100
    
    def test_load_multiple_symbols(self):
        observer = MarketObserver(symbols=["BTCUSDT", "ETHUSDT"])
        df1 = generate_test_data(100)
        df2 = generate_test_data(80)
        
        observer.load_historical_data("BTCUSDT", "1h", df1)
        observer.load_historical_data("ETHUSDT", "1h", df2)
        
        assert "BTCUSDT_1h" in observer._data_cache
        assert "ETHUSDT_1h" in observer._data_cache
    
    def test_analyze_current_with_data(self):
        observer = MarketObserver()
        df = generate_test_data(100)
        
        observer.load_historical_data("BTCUSDT", "1h", df)
        result = observer.analyze_current("BTCUSDT", "1h")
        
        assert result is not None
        assert result.symbol == "BTCUSDT"
        assert result.interval == "1h"
    
    def test_analyze_current_no_data(self):
        observer = MarketObserver()
        
        result = observer.analyze_current("BTCUSDT", "1h")
        
        assert result is None
    
    def test_get_analysis_history(self):
        observer = MarketObserver()
        df = generate_test_data(100)
        
        # 添加數據並分析
        observer.load_historical_data("BTCUSDT", "1h", df)
        
        # 手動添加分析結果到歷史
        result = observer.analyze_current("BTCUSDT", "1h")
        
        history = observer.get_analysis_history("BTCUSDT", "1h")
        assert isinstance(history, list)


class TestMarketObserverCallbacks:
    """測試回調功能"""
    
    def test_callback_execution(self):
        callback = Mock()
        observer = MarketObserver(callback=callback)
        
        # 創建模擬的分析結果
        from vss.types import MarketState, Momentum, Volatility
        market_state = MarketState(
            timestamp=datetime.now(),
            trend=TrendDirection.UP,
            trend_confidence=0.8,
            momentum=Momentum.MODERATE_BULL,
            volatility=Volatility.NORMAL,
            current_price=50000.0,
        )
        
        result = VSSAnalysisResult(
            timestamp=datetime.now(),
            symbol="BTCUSDT",
            interval="1h",
            market_state=market_state,
            price_change_pct=5.0,
            volume_ratio=1.2,
        )
        
        # 模擬回調觸發
        callback(result)
        
        callback.assert_called_once()


class TestMarketObserverRunning:
    """測試監控狀態"""
    
    def test_is_running_initial(self):
        observer = MarketObserver()
        assert observer.is_running() is False
    
    def test_start_stop_monitoring(self):
        observer = MarketObserver()
        
        # 使用 mock 防止實際網絡請求
        with patch.object(observer, '_monitor_loop'):
            observer.start_monitoring(lookback_bars=100, poll_interval=1)
            assert observer.is_running() is True
            
            observer.stop_monitoring()
            assert observer.is_running() is False


class TestBacktestObserver:
    """測試回測觀察器"""
    
    def test_backtest_observer_init(self):
        observer = BacktestObserver()
        
        assert isinstance(observer, MarketObserver)
        assert observer._current_index == {}
    
    def test_run_backtest(self):
        callback = Mock()
        observer = BacktestObserver(callback=callback)
        df = generate_test_data(100)
        
        observer.run_backtest(df, symbol="BTCUSDT", interval="1h", start_bar=50)
        
        # 檢查歷史記錄
        key = "BTCUSDT_1h"
        assert key in observer._analysis_history
        assert len(observer._analysis_history[key]) > 0
    
    def test_run_backtest_with_callback(self):
        callback = Mock()
        observer = BacktestObserver(callback=callback)
        df = generate_test_data(60)
        
        observer.run_backtest(df, symbol="ETHUSDT", interval="4h", start_bar=30)
        
        # 回調應該被調用多次
        assert callback.call_count > 0
    
    def test_get_current_state(self):
        callback = Mock()
        observer = BacktestObserver(callback=callback)
        df = generate_test_data(100)
        
        observer.run_backtest(df, symbol="BTCUSDT", interval="1h", start_bar=50)
        
        state = observer.get_current_state("BTCUSDT", "1h")
        
        assert state is not None
        assert isinstance(state, VSSAnalysisResult)


class TestBacktestObserverEdgeCases:
    """測試邊界情況"""
    
    def test_run_backtest_minimal_data(self):
        observer = BacktestObserver()
        df = generate_test_data(55)  # 剛好夠 start_bar + 指標計算
        
        # 應該不會崩潰
        observer.run_backtest(df, start_bar=50)
    
    def test_get_current_state_no_data(self):
        observer = BacktestObserver()
        
        state = observer.get_current_state("BTCUSDT", "1h")
        
        assert state is None
    
    def test_run_backtest_single_bar(self):
        observer = BacktestObserver()
        df = generate_test_data(10)
        
        # start_bar 大於數據長度，應該安全處理
        observer.run_backtest(df, start_bar=5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
