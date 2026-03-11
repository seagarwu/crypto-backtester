#!/usr/bin/env python3
"""
Strategy R&D Workflow 測試
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.strategy_rd_workflow import StrategyRDWorkflow, RDConfig
from agents.strategy_evaluator_agent import EvaluationResult


class TestRDConfig:
    """測試研發配置"""
    
    def test_default_config(self):
        config = RDConfig()
        
        assert config.symbol == "BTCUSDT"
        assert config.interval == "1h"
        assert config.initial_capital == 10000.0
        assert config.max_iterations == 5
        assert config.min_sharpe == 1.0
    
    def test_custom_config(self):
        config = RDConfig(
            symbol="ETHUSDT",
            interval="4h",
            initial_capital=50000.0,
            max_iterations=10,
            min_sharpe=1.5,
            max_drawdown=20.0,
        )
        
        assert config.symbol == "ETHUSDT"
        assert config.interval == "4h"
        assert config.initial_capital == 50000.0
        assert config.max_iterations == 10
        assert config.min_sharpe == 1.5


class TestStrategyRDWorkflow:
    """測試策略研發閉環"""
    
    def test_workflow_init(self):
        workflow = StrategyRDWorkflow()
        
        assert workflow.config.symbol == "BTCUSDT"
        assert workflow.developer is not None
        assert workflow.backtester is not None
        assert workflow.evaluator is not None
        assert workflow.reporter is not None
        assert workflow.iterations == []
    
    def test_workflow_with_config(self):
        config = RDConfig(
            symbol="ETHUSDT",
            max_iterations=3,
        )
        
        workflow = StrategyRDWorkflow(config)
        
        assert workflow.config.symbol == "ETHUSDT"
        assert workflow.config.max_iterations == 3
    
    def test_approve_strategy(self):
        """測試批准策略"""
        workflow = StrategyRDWorkflow()
        
        from agents.reporter_agent import StrategyReport
        from agents.backtest_runner_agent import BacktestReport, BacktestConfig
        from agents.strategy_evaluator_agent import StrategyEvaluation, EvaluationResult
        
        # 創建模擬報告 - 使用 StrategySpec 而不透過 LLM
        from agents.strategy_developer_agent import StrategySpec
        
        config = BacktestConfig()
        btreport = BacktestReport(
            strategy_name="Test",
            config=config,
        )
        evaluation = StrategyEvaluation(
            result=EvaluationResult.PASS,
            score=80.0,
        )
        
        strategy_spec = StrategySpec(
            name="Test Strategy",
            description="Test description"
        )
        
        report = workflow.reporter.generate_report(
            market_analysis="test",
            strategy_spec=strategy_spec,
            backtest_report=btreport,
            evaluation=evaluation,
        )
        
        workflow.current_report = report
        
        workflow.approve_strategy("Test approval")
        
        assert workflow.current_report.approved == True
        assert workflow.current_report.approval_notes == "Test approval"
    
    def test_reject_strategy(self):
        """測試拒絕策略"""
        workflow = StrategyRDWorkflow()

        from agents.reporter_agent import StrategyReport
        from agents.backtest_runner_agent import BacktestReport, BacktestConfig
        from agents.strategy_evaluator_agent import StrategyEvaluation, EvaluationResult
        from agents.strategy_developer_agent import StrategySpec
        
        config = BacktestConfig()
        btreport = BacktestReport(
            strategy_name="Test",
            config=config,
        )
        evaluation = StrategyEvaluation(
            result=EvaluationResult.FAIL,
            score=30.0,
        )
        
        strategy_spec = StrategySpec(
            name="Test Strategy",
            description="Test description"
        )
        
        report = workflow.reporter.generate_report(
            market_analysis="test",
            strategy_spec=strategy_spec,
            backtest_report=btreport,
            evaluation=evaluation,
        )
        
        workflow.current_report = report
        
        workflow.reject_strategy("Not good enough")
        
        assert workflow.current_report.approved == False
        assert workflow.current_report.approval_notes == "Not good enough"
    
    def test_get_best_strategy_none(self):
        """測試無策略時返回 None"""
        workflow = StrategyRDWorkflow()
        
        best = workflow.get_best_strategy()
        assert best is None
    
    def test_get_best_report_none(self):
        """測試無報告時返回 None"""
        workflow = StrategyRDWorkflow()
        
        best = workflow.get_best_report()
        assert best is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
