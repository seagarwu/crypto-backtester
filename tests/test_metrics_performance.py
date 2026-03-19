from types import SimpleNamespace

import pandas as pd

from agents.backtest_runner_agent import BacktestConfig, BacktestReport
from agents.strategy_evaluator_agent import StrategyEvaluatorAgent, EvaluationResult
from backtest.engine import BacktestResult, Trade
from metrics.performance import calculate_metrics


def test_calculate_metrics_accepts_backtest_report():
    equity_curve = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "equity": [10000.0, 10500.0, 11000.0],
        }
    )
    report = BacktestReport(
        strategy_name="Demo",
        config=BacktestConfig(initial_capital=10000.0),
        total_return=10.0,
        sharpe_ratio=1.1,
        max_drawdown=12.5,
        win_rate=50.0,
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        profit_factor=1.5,
        equity_curve=equity_curve,
        trades=[{"pnl": 100.0}, {"pnl": -50.0}],
    )

    metrics = calculate_metrics(report)

    assert metrics["initial_capital"] == 10000.0
    assert metrics["final_equity"] == 11000.0
    assert metrics["total_return"] == 0.1
    assert metrics["max_drawdown_pct"] <= 0
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0


def test_evaluator_accepts_fractional_metrics_dict():
    equity_curve = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "equity": [10000.0, 12000.0],
        }
    )
    result = BacktestResult(
        equity_curve=equity_curve,
        trades=[Trade("2024-01-01", 100.0, 1.0, "long", "2024-01-02", 110.0, 50.0, 1.0)],
        final_equity=12000.0,
        initial_capital=10000.0,
        total_return=0.2,
        total_trades=40,
        winning_trades=20,
        losing_trades=20,
    )
    metrics = {
        "sharpe_ratio": 1.3,
        "max_drawdown": 0.2,
        "win_rate": 0.45,
        "total_return": 0.12,
        "profit_factor": 1.4,
    }

    evaluation = StrategyEvaluatorAgent().evaluate(result, metrics)

    assert evaluation.result in {EvaluationResult.PASS, EvaluationResult.NEEDS_IMPROVEMENT}
    assert evaluation.drawdown_passed is True
    assert evaluation.win_rate_passed is True
    assert evaluation.return_passed is True


def test_display_code_path_returns_absolute_path(tmp_path):
    from agents.conversation import ConversationalStrategyDeveloper

    conversation = ConversationalStrategyDeveloper()
    relative = tmp_path / "reports" / "iterations" / "demo.py"
    relative.parent.mkdir(parents=True)
    relative.write_text("print('demo')\n", encoding="utf-8")

    displayed = conversation._display_code_path(str(relative.relative_to(tmp_path)))

    assert displayed.endswith("reports/iterations/demo.py")
