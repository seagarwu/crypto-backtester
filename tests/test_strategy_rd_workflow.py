#!/usr/bin/env python3
"""
Strategy R&D Workflow 測試
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.strategy_rd_workflow import (
    StrategyRDWorkflow,
    RDConfig,
    CodeValidationResult,
    IterationFeedback,
    StrategyRoute,
    HumanDecision,
    HumanDecisionAction,
)
from agents.strategy_evaluator_agent import EvaluationResult
from agents.strategy_developer_agent import StrategySpec, EngineerCodeResult


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

    def test_build_iteration_feedback(self):
        workflow = StrategyRDWorkflow()

        validation = CodeValidationResult(
            passed=False,
            issues=["Syntax error", "Smoke backtest failed"],
        )

        class DummyEvaluation:
            weaknesses = ["Sharpe Ratio 低"]
            recommendations = ["提高 Sharpe Ratio", "降低回撤"]

        feedback = workflow._build_iteration_feedback(validation, DummyEvaluation())

        assert "Syntax error" in feedback.validation_issues
        assert "Sharpe Ratio 低" in feedback.performance_issues
        assert "降低回撤" in feedback.required_changes

    def test_build_iteration_feedback_includes_human_priorities(self):
        workflow = StrategyRDWorkflow()

        feedback = workflow._build_iteration_feedback(
            validation=None,
            evaluation=None,
            human_decision=HumanDecision(
                action=HumanDecisionAction.REVISE,
                rationale="保留策略方向，但加入更嚴格風控",
                next_focus=["add stop loss", "reduce drawdown"],
            ),
        )

        assert "Human decision: 保留策略方向，但加入更嚴格風控" in feedback.required_changes
        assert "Human priority: add stop loss" in feedback.required_changes

    def test_feedback_to_dict(self):
        workflow = StrategyRDWorkflow()
        feedback = IterationFeedback(
            bugs=["import error"],
            performance_issues=["high drawdown"],
            required_changes=["add stop loss"],
            validation_issues=["missing signal column"],
        )

        data = workflow._feedback_to_dict(feedback)

        assert data["bugs"] == ["import error"]
        assert data["performance_issues"] == ["high drawdown"]
        assert data["required_changes"] == ["add stop loss"]
        assert data["validation_issues"] == ["missing signal column"]

    def test_classify_strategy_known_multi_timeframe_bband(self):
        workflow = StrategyRDWorkflow()
        spec = StrategySpec(
            name="BTCUSDT_BBand_Reversion",
            description="test",
            indicators=["BBand", "Volume"],
            parameters={"higher_timeframe": "4h", "entry_timeframe": "1h"},
        )

        route = workflow._classify_strategy(spec)

        assert route.route is StrategyRoute.KNOWN
        assert route.strategy_family == "multi_timeframe_bband_reversion"

    def test_classify_strategy_composable_for_known_indicator_mix(self):
        workflow = StrategyRDWorkflow()
        spec = StrategySpec(
            name="ComposableIdea",
            description="test",
            indicators=["RSI", "MACD", "Volume"],
            parameters={},
        )

        route = workflow._classify_strategy(spec)

        assert route.route is StrategyRoute.COMPOSABLE
        assert route.strategy_family == "generic_rule_based"

    def test_classify_strategy_novel_for_unknown_indicator(self):
        workflow = StrategyRDWorkflow()
        spec = StrategySpec(
            name="NovelIdea",
            description="test",
            indicators=["OrderFlowImbalance"],
            parameters={},
        )

        route = workflow._classify_strategy(spec)

        assert route.route is StrategyRoute.NOVEL

    def test_known_route_uses_deterministic_codegen(self):
        workflow = StrategyRDWorkflow(RDConfig(max_iterations=1, report_dir="reports/test_route"))
        spec = StrategySpec(
            name="BTCUSDT_BBand_Reversion",
            description="4H/1H BBand reversion",
            indicators=["BBand", "Volume"],
            parameters={
                "bb_period": 20,
                "bb_std": 2.0,
                "volume_ma_period": 20,
                "volume_multiplier": 2.0,
                "stop_loss_pct": 0.03,
                "higher_timeframe": "4h",
                "entry_timeframe": "1h",
            },
        )

        class GuardDeveloper:
            def generate_strategy_code_structured(self, *args, **kwargs):
                raise AssertionError("LLM path should not be used for known route")

            def revise_strategy_code(self, *args, **kwargs):
                raise AssertionError("LLM path should not be used for known route")

        workflow.developer = GuardDeveloper()
        workflow.backtester = FakeBacktester()
        workflow.evaluator = FakeEvaluator()
        workflow.reporter = FakeReporter()

        report = workflow.run(initial_strategy=spec, market_analysis="test")

        assert report is not None
        assert workflow.route_decision.route is StrategyRoute.KNOWN
        assert "Deterministic known route" in workflow.iterations[0]["code_result"].summary

    def test_multi_timeframe_deterministic_code_keeps_lowercase_resample_freq(self):
        workflow = StrategyRDWorkflow()
        spec = build_known_spec()

        code = workflow._generate_multi_timeframe_bband_code(spec)

        assert '.resample(str(self.higher_timeframe).lower())' in code

    def test_run_uses_human_decision_provider_to_stop_after_checkpoint(self):
        workflow = StrategyRDWorkflow(RDConfig(max_iterations=3, report_dir="reports/test_human_stop"))
        workflow.backtester = FakeBacktester()
        workflow.evaluator = FakeEvaluator()
        workflow.reporter = FakeReporter()

        decisions = []

        def provider(context):
            decisions.append(context["proposed_action"].value)
            return HumanDecision(
                action=HumanDecisionAction.STOP,
                rationale="Human decided to pause after first report",
                next_focus=["review trades manually"],
            )

        report = workflow.run(
            initial_strategy=build_known_spec(),
            market_analysis="test",
            human_decision_provider=provider,
        )

        assert report is not None
        assert decisions == ["accept"]
        assert len(workflow.iterations) == 1
        assert workflow.iterations[0]["human_decision"].action is HumanDecisionAction.STOP
        assert report.approved is False
        assert report.approval_notes == "Human decided to pause after first report"

    def test_run_allows_human_pivot_strategy_for_next_iteration(self):
        workflow = StrategyRDWorkflow(RDConfig(max_iterations=2, report_dir="reports/test_human_pivot"))
        workflow.backtester = FakeBacktester()
        workflow.evaluator = FakeNeedsImprovementEvaluator()
        workflow.reporter = FakeReporter()

        pivot_spec = StrategySpec(
            name="Pivoted Strategy",
            description="New direction",
            indicators=["RSI", "MACD"],
            parameters={},
        )

        def provider(context):
            if context["iteration"] == 1:
                return HumanDecision(
                    action=HumanDecisionAction.PIVOT,
                    rationale="Switch to a new strategy family",
                    updated_strategy=pivot_spec,
                )
            return HumanDecision(action=HumanDecisionAction.STOP, rationale="Enough for now")

        workflow.run(
            initial_strategy=build_known_spec(),
            market_analysis="test",
            human_decision_provider=provider,
        )

        assert len(workflow.iterations) == 2
        assert workflow.iterations[0]["human_decision"].action is HumanDecisionAction.PIVOT
        assert workflow.iterations[1]["strategy"].name == "Pivoted Strategy"

    def test_run_applies_human_config_overrides_to_following_iteration(self):
        workflow = StrategyRDWorkflow(RDConfig(max_iterations=2, report_dir="reports/test_human_override"))
        workflow.backtester = FakeBacktester()
        workflow.evaluator = FakeNeedsImprovementEvaluator()
        workflow.reporter = FakeReporter()

        def provider(context):
            if context["iteration"] == 1:
                return HumanDecision(
                    action=HumanDecisionAction.CONTINUE,
                    rationale="Retry on 30m data",
                    config_overrides={"interval": "30m"},
                )
            return HumanDecision(action=HumanDecisionAction.STOP, rationale="done")

        workflow.run(
            initial_strategy=build_known_spec(),
            market_analysis="test",
            human_decision_provider=provider,
        )

        assert workflow.iterations[0]["human_decision"].config_overrides["interval"] == "30m"
        assert workflow.config.interval == "30m"


class FakeBacktester:
    def load_data(self, symbol, interval, start_date=None, end_date=None):
        import pandas as pd

        dates = pd.date_range("2024-01-01", periods=120, freq="h")
        return pd.DataFrame(
            {
                "datetime": dates,
                "open": [100.0 + i for i in range(120)],
                "high": [101.0 + i for i in range(120)],
                "low": [99.0 + i for i in range(120)],
                "close": [100.5 + i for i in range(120)],
                "volume": [1000.0 for _ in range(120)],
            }
        )

    def run_backtest(self, strategy_name, strategy_class=None, strategy_params=None, config=None):
        from agents.backtest_runner_agent import BacktestConfig, BacktestReport

        return BacktestReport(
            strategy_name=strategy_name,
            config=config or BacktestConfig(),
            total_return=10.0,
            sharpe_ratio=1.2,
            max_drawdown=20.0,
            win_rate=45.0,
            total_trades=40,
            profit_factor=1.2,
        )


class FakeEvaluator:
    def evaluate(self, backtest_report, metrics=None, target_metrics=None):
        from agents.strategy_evaluator_agent import StrategyEvaluation, EvaluationResult

        return StrategyEvaluation(
            result=EvaluationResult.PASS,
            score=80.0,
            sharpe_passed=True,
            drawdown_passed=True,
            win_rate_passed=True,
            trades_passed=True,
            return_passed=True,
            summary="pass",
            strengths=[],
            weaknesses=[],
            recommendations=[],
        )


class FakeNeedsImprovementEvaluator:
    def evaluate(self, backtest_report, metrics=None, target_metrics=None):
        from agents.strategy_evaluator_agent import StrategyEvaluation, EvaluationResult

        return StrategyEvaluation(
            result=EvaluationResult.NEEDS_IMPROVEMENT,
            score=62.0,
            sharpe_passed=False,
            drawdown_passed=True,
            win_rate_passed=True,
            trades_passed=True,
            return_passed=True,
            summary="needs improvement",
            strengths=["positive return"],
            weaknesses=["fragile edge"],
            recommendations=["refine entry logic"],
        )


class FakeReporter:
    def generate_report(self, market_analysis, strategy_spec, backtest_report, evaluation, iteration=1):
        from agents.reporter_agent import StrategyReport

        return StrategyReport(
            strategy_name=strategy_spec.name,
            strategy_description=strategy_spec.description,
            market_analysis=market_analysis,
            indicators=strategy_spec.indicators,
            entry_rules=strategy_spec.entry_rules,
            exit_rules=strategy_spec.exit_rules,
            parameters=strategy_spec.parameters,
            total_return=backtest_report.total_return,
            sharpe_ratio=backtest_report.sharpe_ratio,
            max_drawdown=backtest_report.max_drawdown,
            win_rate=backtest_report.win_rate,
            total_trades=backtest_report.total_trades,
            evaluation_passed=True,
            evaluation_score=evaluation.score,
            evaluation_summary=evaluation.summary,
            strengths=[],
            weaknesses=[],
            recommendations=[],
        )

    def format_report_compact(self, report):
        return f"{report.strategy_name}: {report.sharpe_ratio}"


def build_known_spec():
    return StrategySpec(
        name="BTCUSDT_BBand_Reversion",
        description="4H/1H BBand reversion",
        indicators=["BBand", "Volume"],
        parameters={
            "bb_period": 20,
            "bb_std": 2.0,
            "volume_ma_period": 20,
            "volume_multiplier": 2.0,
            "stop_loss_pct": 0.03,
            "higher_timeframe": "4h",
            "entry_timeframe": "1h",
        },
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
