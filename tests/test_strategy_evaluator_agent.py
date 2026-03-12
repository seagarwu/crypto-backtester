#!/usr/bin/env python3
"""
Strategy Evaluator Agent 測試
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.strategy_evaluator_agent import (
    StrategyEvaluatorAgent,
    EvaluationMetrics,
    EvaluationResult,
    StrategyEvaluation,
)
from agents.backtest_runner_agent import BacktestReport, BacktestConfig


class TestEvaluationMetrics:
    """測試評估指標"""
    
    def test_default_metrics(self):
        metrics = EvaluationMetrics()
        
        assert metrics.min_sharpe == 1.0
        assert metrics.max_drawdown == 30.0
        assert metrics.min_win_rate == 40.0
        assert metrics.min_trades == 30
    
    def test_custom_metrics(self):
        metrics = EvaluationMetrics(
            min_sharpe=1.5,
            max_drawdown=20.0,
            min_win_rate=50.0,
            min_trades=50,
        )
        
        assert metrics.min_sharpe == 1.5
        assert metrics.max_drawdown == 20.0
        assert metrics.min_win_rate == 50.0
        assert metrics.min_trades == 50


class TestStrategyEvaluatorAgent:
    """測試策略評估 Agent"""
    
    def test_agent_init(self):
        agent = StrategyEvaluatorAgent()
        
        assert agent.model == "gemini-3-flash-preview"
        assert isinstance(agent.metrics, EvaluationMetrics)
    
    def test_agent_with_custom_metrics(self):
        metrics = EvaluationMetrics(min_sharpe=2.0)
        agent = StrategyEvaluatorAgent(metrics=metrics)
        
        assert agent.metrics.min_sharpe == 2.0


class TestEvaluation:
    """測試評估邏輯"""
    
    def create_mock_report(
        self,
        sharpe=1.5,
        drawdown=20.0,
        win_rate=50.0,
        trades=100,
        total_return=20.0,
    ):
        """創建模擬回測報告"""
        config = BacktestConfig()
        
        report = BacktestReport(
            strategy_name="Test Strategy",
            config=config,
            total_return=total_return,
            annual_return=15.0,
            sharpe_ratio=sharpe,
            max_drawdown=drawdown,
            volatility=25.0,
            total_trades=trades,
            winning_trades=int(trades * win_rate / 100),
            losing_trades=int(trades * (100 - win_rate) / 100),
            win_rate=win_rate,
            avg_win=100.0,
            avg_loss=50.0,
            profit_factor=2.0,
            backtest_duration_days=365,
            trades=[],
        )
        
        return report
    
    def test_evaluate_pass(self):
        """測試通過評估"""
        agent = StrategyEvaluatorAgent()
        report = self.create_mock_report(
            sharpe=1.5,
            drawdown=20.0,
            win_rate=50.0,
            trades=50,
            total_return=20.0,
        )
        
        result = agent.evaluate(report)
        
        assert result.result == EvaluationResult.PASS
        assert result.score >= 70
    
    def test_evaluate_fail(self):
        """測試未通過評估"""
        agent = StrategyEvaluatorAgent()
        report = self.create_mock_report(
            sharpe=0.3,
            drawdown=50.0,
            win_rate=30.0,
            trades=10,
            total_return=-10.0,
        )
        
        result = agent.evaluate(report)
        
        assert result.result == EvaluationResult.FAIL
    
    def test_evaluate_needs_improvement(self):
        """測試需要改進"""
        agent = StrategyEvaluatorAgent()
        # 部分通過，部分失敗
        report = self.create_mock_report(
            sharpe=0.8,  # 低於 1.0
            drawdown=25.0,  # 通過
            win_rate=45.0,  # 通過
            trades=40,  # 通過
            total_return=5.0,  # 通過
        )
        
        result = agent.evaluate(report)
        
        assert result.result in [EvaluationResult.FAIL, EvaluationResult.NEEDS_IMPROVEMENT]
    
    def test_sharpe_check(self):
        """測試 Sharpe 檢查"""
        agent = StrategyEvaluatorAgent(metrics=EvaluationMetrics(min_sharpe=1.5))
        
        # 低於門檻
        report = self.create_mock_report(sharpe=1.0)
        result = agent.evaluate(report)
        assert result.sharpe_passed == False
        
        # 高於門檻
        report = self.create_mock_report(sharpe=2.0)
        result = agent.evaluate(report)
        assert result.sharpe_passed == True
    
    def test_drawdown_check(self):
        """測試回撤檢查"""
        agent = StrategyEvaluatorAgent(metrics=EvaluationMetrics(max_drawdown=20.0))
        
        # 高於門檻（壞）
        report = self.create_mock_report(drawdown=30.0)
        result = agent.evaluate(report)
        assert result.drawdown_passed == False
        
        # 低於門檻（好）
        report = self.create_mock_report(drawdown=15.0)
        result = agent.evaluate(report)
        assert result.drawdown_passed == True
    
    def test_target_metrics(self):
        """測試目標指標覆蓋"""
        agent = StrategyEvaluatorAgent()
        
        report = self.create_mock_report(
            sharpe=1.2,
            drawdown=25.0,
            win_rate=45.0,
            trades=30,
        )
        
        # 使用不同的目標指標
        result = agent.evaluate(
            report,
            target_metrics={'sharpe': 1.0, 'max_drawdown': 30.0, 'win_rate': 40.0}
        )
        
        # 應該通過
        assert result.sharpe_passed == True
        assert result.drawdown_passed == True
        assert result.win_rate_passed == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
