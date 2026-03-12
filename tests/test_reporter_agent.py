#!/usr/bin/env python3
"""
Reporter Agent 測試
"""

import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.reporter_agent import (
    ReporterAgent,
    StrategyReport,
)
from agents.strategy_developer_agent import StrategySpec
from agents.strategy_evaluator_agent import EvaluationResult
from agents.backtest_runner_agent import BacktestReport, BacktestConfig


class TestReporterAgent:
    """測試彙報 Agent"""
    
    def test_agent_init(self):
        agent = ReporterAgent()
        
        assert agent.model == "gemini-3-flash-preview"
        assert agent.llm is None
    
    def test_agent_with_custom_model(self):
        agent = ReporterAgent(model="gpt-4")
        
        assert agent.model == "gpt-4"


class TestStrategyReport:
    """測試策略報告"""
    
    def test_create_report(self):
        report = StrategyReport(
            strategy_name="Test Strategy",
            strategy_description="A test strategy",
        )
        
        assert report.strategy_name == "Test Strategy"
        assert isinstance(report.created_at, datetime)
        assert report.approved == False


class TestReportFormatting:
    """測試報告格式化"""
    
    def create_mock_report(self):
        """創建模擬報告"""
        config = BacktestConfig()
        
        backtest_report = BacktestReport(
            strategy_name="Test Strategy",
            config=config,
            total_return=25.5,
            annual_return=20.0,
            sharpe_ratio=1.8,
            max_drawdown=15.0,
            volatility=20.0,
            total_trades=80,
            winning_trades=50,
            losing_trades=30,
            win_rate=62.5,
            avg_win=150.0,
            avg_loss=75.0,
            profit_factor=2.0,
            backtest_duration_days=365,
            trades=[],
        )
        
        from agents.strategy_evaluator_agent import StrategyEvaluation
        
        evaluation = StrategyEvaluation(
            result=EvaluationResult.PASS,
            score=85.0,
            sharpe_passed=True,
            drawdown_passed=True,
            win_rate_passed=True,
            trades_passed=True,
            return_passed=True,
            summary="策略通過評估",
            strengths=["Sharpe 高", "回撤可控"],
            weaknesses=["交易次數偏少"],
            recommendations=["增加止損機制"],
        )
        
        strategy_spec = StrategySpec(
            name="Test Strategy",
            description="一個測試策略",
            indicators=["MA_20", "RSI_14"],
            entry_rules="MA_20 > MA_50",
            exit_rules="MA_20 < MA_50",
            parameters={"fast_ma": 20, "slow_ma": 50},
        )
        
        return strategy_spec, backtest_report, evaluation
    
    def test_format_markdown(self):
        """測試 Markdown 格式化"""
        agent = ReporterAgent()
        
        strategy_spec, backtest_report, evaluation = self.create_mock_report()
        
        report = agent.generate_report(
            market_analysis="比特幣上漲趨勢",
            strategy_spec=strategy_spec,
            backtest_report=backtest_report,
            evaluation=evaluation,
        )
        
        md = agent.format_report_markdown(report)
        
        assert "Test Strategy" in md
        assert "比特幣上漲趨勢" in md
        assert "Sharpe Ratio" in md
        assert "1.8" in md
        assert "通過" in md
    
    def test_format_compact(self):
        """測試簡短格式化"""
        agent = ReporterAgent()
        
        strategy_spec, backtest_report, evaluation = self.create_mock_report()
        
        report = agent.generate_report(
            market_analysis="比特幣上漲趨勢",
            strategy_spec=strategy_spec,
            backtest_report=backtest_report,
            evaluation=evaluation,
        )
        
        compact = agent.format_report_compact(report)
        
        assert "Test Strategy" in compact
        assert "25.5" in compact  # total return
        assert "1.8" in compact  # sharpe
    
    def test_generate_report(self):
        """測試報告生成"""
        agent = ReporterAgent()
        
        strategy_spec, backtest_report, evaluation = self.create_mock_report()
        
        report = agent.generate_report(
            market_analysis="比特幣上漲趨勢",
            strategy_spec=strategy_spec,
            backtest_report=backtest_report,
            evaluation=evaluation,
        )
        
        assert report.strategy_name == "Test Strategy"
        assert report.total_return == 25.5
        assert report.sharpe_ratio == 1.8
        assert report.evaluation_passed == True
        assert len(report.strengths) == 2
    
    def test_approved_flag(self):
        """測試批准標記"""
        agent = ReporterAgent()
        
        strategy_spec, backtest_report, evaluation = self.create_mock_report()
        
        report = agent.generate_report(
            market_analysis="",
            strategy_spec=strategy_spec,
            backtest_report=backtest_report,
            evaluation=evaluation,
        )
        
        assert report.approved == False
        
        # 測試批准
        report.approved = True
        report.approval_notes = "通過測試"
        
        assert report.approved == True
        assert report.approval_notes == "通過測試"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
