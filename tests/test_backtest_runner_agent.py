#!/usr/bin/env python3
"""
Backtest Runner Agent 測試
"""

import pytest
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.backtest_runner_agent import (
    BacktestRunnerAgent,
    BacktestConfig,
    BacktestReport,
)
from backtest.engine import BacktestEngine


class TestBacktestConfig:
    """測試回測配置"""
    
    def test_default_config(self):
        config = BacktestConfig()
        
        assert config.symbol == "BTCUSDT"
        assert config.interval == "1h"
        assert config.initial_capital == 10000.0
        assert config.commission_rate == 0.001
    
    def test_custom_config(self):
        config = BacktestConfig(
            symbol="ETHUSDT",
            interval="4h",
            initial_capital=50000.0,
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        
        assert config.symbol == "ETHUSDT"
        assert config.interval == "4h"
        assert config.initial_capital == 50000.0


class TestBacktestRunnerAgent:
    """測試回測執行 Agent"""
    
    def test_agent_init(self):
        agent = BacktestRunnerAgent(data_dir="data")
        
        assert agent.data_dir == "data"
        assert isinstance(agent.strategies, dict)
    
    def test_agent_init_default_dir(self):
        agent = BacktestRunnerAgent()
        
        # 預設使用專案根目錄下的 data
        assert "data" in agent.data_dir
    
    def test_get_available_strategies(self):
        agent = BacktestRunnerAgent()
        
        strategies = agent.get_available_strategies()
        
        assert isinstance(strategies, list)


class TestIndicatorCalculation:
    """測試指標計算"""
    
    def create_sample_data(self, rows=100):
        """創建測試數據"""
        dates = pd.date_range(start="2023-01-01", periods=rows, freq="1h")
        
        # 模擬價格走勢
        np.random.seed(42)
        close = 50000 + np.cumsum(np.random.randn(rows) * 100)
        
        data = pd.DataFrame({
            'datetime': dates,
            'open': close - np.random.rand(rows) * 50,
            'high': close + np.random.rand(rows) * 50,
            'low': close - np.random.rand(rows) * 50,
            'close': close,
            'volume': np.random.rand(rows) * 1000,
        })
        
        return data
    
    def test_calculate_ma(self):
        """測試 MA 指標計算"""
        agent = BacktestRunnerAgent()
        
        # 創建簡單策略
        class MockStrategy:
            required_indicators = ["MA_20"]
            
            def calculate_signals(self, data, indicators):
                return pd.DataFrame({
                    'datetime': data['datetime'],
                    'signal': [0] * len(data),
                })
        
        strategy = MockStrategy()
        data = self.create_sample_data(100)
        
        indicators = agent._calculate_indicators(strategy, data)
        
        assert "MA_20" in indicators
        assert len(indicators["MA_20"]) == 100
        assert not indicators["MA_20"].iloc[-1] != indicators["MA_20"].iloc[-1]  # 不是 NaN
    
    def test_calculate_rsi(self):
        """測試 RSI 指標計算"""
        agent = BacktestRunnerAgent()
        
        class MockStrategy:
            required_indicators = ["RSI_14"]
            
            def calculate_signals(self, data, indicators):
                return pd.DataFrame({
                    'datetime': data['datetime'],
                    'signal': [0] * len(data),
                })
        
        strategy = MockStrategy()
        data = self.create_sample_data(100)
        
        indicators = agent._calculate_indicators(strategy, data)
        
        assert "RSI_14" in indicators
    
    def test_calculate_macd(self):
        """測試 MACD 指標計算"""
        agent = BacktestRunnerAgent()
        
        class MockStrategy:
            required_indicators = ["MACD"]
            
            def calculate_signals(self, data, indicators):
                return pd.DataFrame({
                    'datetime': data['datetime'],
                    'signal': [0] * len(data),
                })
        
        strategy = MockStrategy()
        data = self.create_sample_data(100)
        
        indicators = agent._calculate_indicators(strategy, data)
        
        assert "MACD" in indicators


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
