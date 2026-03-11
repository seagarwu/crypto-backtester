#!/usr/bin/env python3
"""
Strategy Developer Agent 測試
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.strategy_developer_agent import StrategyDeveloperAgent, StrategySpec


class TestStrategySpec:
    """測試策略規格"""
    
    def test_create_strategy_spec(self):
        spec = StrategySpec(
            name="Test Strategy",
            description="Test description",
            indicators=["MA_20", "RSI_14"],
            entry_rules="MA_20 > MA_50",
            exit_rules="MA_20 < MA_50",
            parameters={"fast_ma": 20, "slow_ma": 50},
            timeframe="1h",
            risk_level="medium",
        )
        
        assert spec.name == "Test Strategy"
        assert len(spec.indicators) == 2
        assert spec.parameters["fast_ma"] == 20
    
    def test_default_values(self):
        spec = StrategySpec(name="Default", description="Default description")
        
        assert spec.name == "Default"
        assert spec.description == "Default description"
        assert spec.indicators == []
        assert spec.risk_level == "medium"
        assert spec.timeframe == "1h"


class TestStrategyDeveloperAgent:
    """測試策略研發 Agent"""
    
    def test_agent_init(self):
        agent = StrategyDeveloperAgent()
        
        assert agent.model == "minimax/minimax-chat"
        assert agent.temperature == 0.8
        assert agent.llm is None  # 懒加载
    
    def test_agent_with_custom_model(self):
        agent = StrategyDeveloperAgent(model="gpt-4", temperature=0.5)
        
        assert agent.model == "gpt-4"
        assert agent.temperature == 0.5
    
    def test_diagnose_results_good(self):
        agent = StrategyDeveloperAgent()
        
        results = {
            "sharpe_ratio": 3.0,  # Very high
            "max_drawdown": 10.0,
            "win_rate": 60.0,
            "total_trades": 100,
        }
        
        diagnosis = agent._diagnose_results(results)
        
        # Very high Sharpe should trigger "too high" warning
        assert "Sharpe Ratio" in diagnosis
    
    def test_diagnose_results_bad(self):
        agent = StrategyDeveloperAgent()
        
        results = {
            "sharpe_ratio": 0.5,
            "max_drawdown": 50.0,
            "win_rate": 30.0,
            "total_trades": 5,
        }
        
        diagnosis = agent._diagnose_results(results)
        
        assert "Sharpe Ratio 低於 1.0" in diagnosis
        assert "最大回撤過大" in diagnosis
        assert "交易次數過少" in diagnosis


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
