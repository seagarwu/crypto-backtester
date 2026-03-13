#!/usr/bin/env python3
"""
Deterministic smoke test for the agentic strategy R&D loop.

用途：
1. 不呼叫任何 LLM API
2. 驗證 Engineer -> validation -> backtest -> evaluation -> report 的流程
3. 快速區分「流程 bug」與「真實模型輸出問題」

使用方式:
    python scripts/debug_agentic_loop.py --scenario first_pass
    python scripts/debug_agentic_loop.py --scenario repair_success
    python scripts/debug_agentic_loop.py --scenario always_fail
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.backtest_runner_agent import BacktestConfig, BacktestReport
from agents.reporter_agent import StrategyReport
from agents.strategy_developer_agent import EngineerCodeResult, StrategySpec
from agents.strategy_evaluator_agent import EvaluationResult, StrategyEvaluation
from agents.strategy_rd_workflow import RDConfig, StrategyRDWorkflow


VALID_CODE = """from strategies.base import BaseStrategy, SignalType
import pandas as pd


class BTCUSDT_BBand_Reversion(BaseStrategy):
    def __init__(self, bb_period=20, bb_std=2.0, volume_ma_period=20, volume_multiplier=2.0, stop_loss_pct=0.03, higher_timeframe='4h', entry_timeframe='1h'):
        super().__init__(name="BTCUSDT_BBand_Reversion")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_ma_period = volume_ma_period
        self.volume_multiplier = volume_multiplier
        self.stop_loss_pct = stop_loss_pct
        self.higher_timeframe = higher_timeframe
        self.entry_timeframe = entry_timeframe

    @property
    def required_indicators(self):
        return ["BBand", "Volume"]

    def calculate_signals(self, data: pd.DataFrame, indicators: dict) -> dict:
        return {"signal": SignalType.HOLD, "strength": 0.0}

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        if "datetime" not in df.columns:
            df["datetime"] = df.index
        df["signal"] = SignalType.HOLD
        return df[["datetime", "open", "high", "low", "close", "volume", "signal"]]
"""


TRUNCATED_CODE = """from strategies.base import BaseStrategy, SignalType
import pandas as pd


class BTCUSDT_BBand_Reversion(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.bb_period = 20
        self.bb_std = 2.0
        self.volume_ma_period =
"""


class FakeDeveloper:
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.calls = 0

    def generate_strategy_code_structured(self, spec, md_context=None, feedback=None, previous_code=""):
        self.calls += 1
        if self.scenario == "first_pass":
            code = VALID_CODE
        elif self.scenario == "repair_success":
            code = TRUNCATED_CODE if self.calls == 1 else VALID_CODE
        else:
            code = TRUNCATED_CODE
        return EngineerCodeResult(
            code=code,
            summary=f"fake generation #{self.calls}",
            assumptions=[],
            raw_response=code,
        )

    def revise_strategy_code(self, spec, feedback, previous_code, md_context=None):
        return self.generate_strategy_code_structured(
            spec=spec,
            md_context=md_context,
            feedback=feedback,
            previous_code=previous_code,
        )


class FakeBacktester:
    def load_data(self, symbol, interval, start_date=None, end_date=None):
        dates = pd.date_range("2024-01-01", periods=24, freq="h")
        return pd.DataFrame(
            {
                "datetime": dates,
                "open": [100.0 + i for i in range(24)],
                "high": [101.0 + i for i in range(24)],
                "low": [99.0 + i for i in range(24)],
                "close": [100.5 + i for i in range(24)],
                "volume": [1000.0 for _ in range(24)],
            }
        )

    def run_backtest(self, strategy_name, strategy_class=None, strategy_params=None, config=None):
        return BacktestReport(
            strategy_name=strategy_name,
            config=config or BacktestConfig(),
            total_return=12.5,
            sharpe_ratio=1.35,
            max_drawdown=18.0,
            win_rate=47.0,
            total_trades=36,
            profit_factor=1.28,
        )


class FakeEvaluator:
    def evaluate(self, backtest_report, metrics=None, target_metrics=None):
        return StrategyEvaluation(
            result=EvaluationResult.PASS,
            score=82.0,
            sharpe_passed=True,
            drawdown_passed=True,
            win_rate_passed=True,
            trades_passed=True,
            return_passed=True,
            summary="Deterministic smoke test passed",
            strengths=["Loop completed"],
            weaknesses=[],
            recommendations=[],
        )


class FakeReporter:
    def generate_report(self, market_analysis, strategy_spec, backtest_report, evaluation, iteration=1):
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
            strengths=evaluation.strengths,
            weaknesses=evaluation.weaknesses,
            recommendations=evaluation.recommendations,
        )

    def format_report_compact(self, report):
        return (
            f"[FAKE REPORT] {report.strategy_name} | "
            f"Sharpe={report.sharpe_ratio:.2f} | "
            f"MDD={report.max_drawdown:.1f}% | "
            f"Trades={report.total_trades}"
        )


def build_spec() -> StrategySpec:
    return StrategySpec(
        name="BTCUSDT_BBand_Reversion",
        description="4H/1H dual timeframe Bollinger mean reversion strategy.",
        indicators=["BBand", "Volume"],
        entry_rules="4H lower band arms long; 1H lower band plus volume spike enters.",
        exit_rules="1H opposite band exits; fixed 3% stop loss.",
        parameters={
            "bb_period": 20,
            "bb_std": 2.0,
            "volume_ma_period": 20,
            "volume_multiplier": 2.0,
            "stop_loss_pct": 0.03,
            "higher_timeframe": "4h",
            "entry_timeframe": "1h",
        },
        timeframe="1h",
        risk_level="medium",
    )


def main():
    parser = argparse.ArgumentParser(description="Deterministic smoke test for StrategyRDWorkflow")
    parser.add_argument(
        "--scenario",
        choices=["first_pass", "repair_success", "always_fail"],
        default="repair_success",
        help="Control fake Engineer behavior.",
    )
    parser.add_argument(
        "--report-dir",
        default="reports/debug_loop",
        help="Directory for iteration artifacts.",
    )
    args = parser.parse_args()

    config = RDConfig(
        symbol="BTCUSDT",
        interval="1h",
        max_iterations=3,
        report_dir=args.report_dir,
        data_dir="data",
    )
    workflow = StrategyRDWorkflow(config)
    workflow.developer = FakeDeveloper(args.scenario)
    workflow.backtester = FakeBacktester()
    workflow.evaluator = FakeEvaluator()
    workflow.reporter = FakeReporter()

    report = workflow.run(
        market_analysis="deterministic local smoke test",
        initial_strategy=build_spec(),
        md_context="## 策略規格\n- 名稱: BTCUSDT_BBand_Reversion",
    )

    print("\n=== Debug Summary ===")
    print(f"scenario: {args.scenario}")
    print(f"iterations: {len(workflow.iterations)}")
    print(f"validated_code: {workflow.current_validated_code_path or 'NONE'}")
    print(f"report_generated: {report is not None}")

    for item in workflow.iterations:
        validation = item.get("validation")
        issues = getattr(validation, "issues", []) if validation else []
        print(
            f"iteration {item['iteration']}: "
            f"passed={bool(validation and validation.passed)} "
            f"issues={issues}"
        )


if __name__ == "__main__":
    main()
