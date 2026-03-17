import json
from types import SimpleNamespace

from research_contracts import ResearchArtifactWriter


def build_strategy():
    return SimpleNamespace(
        name="Demo Strategy",
        description="Mean reversion with human checkpoints",
        indicators=["BBand", "Volume"],
        entry_rules="Touch lower band and confirm volume spike",
        exit_rules="Take profit at middle band or stop out",
        parameters={"bb_period": 20, "stop_loss_pct": 0.03},
        timeframe="1h",
        risk_level="medium",
    )


def build_validation():
    return SimpleNamespace(
        passed=True,
        issues=[],
        smoke_metrics={"total_return": 3.2, "max_drawdown": 9.4},
    )


def build_code_result():
    return SimpleNamespace(
        summary="Implemented BBand reversion entry/exit logic",
        assumptions=["Volume spike is defined as 2x rolling mean"],
    )


def build_backtest_report():
    config = SimpleNamespace(
        symbol="BTCUSDT",
        interval="1h",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )
    return SimpleNamespace(
        config=config,
        total_return=12.5,
        max_drawdown=18.0,
        sharpe_ratio=1.3,
        win_rate=46.0,
        profit_factor=1.25,
        total_trades=38,
    )


def build_decision():
    return SimpleNamespace(
        action=SimpleNamespace(value="continue"),
        rationale="Need more robustness checks",
        next_focus=["walk-forward validation", "reduce drawdown"],
    )


class TestResearchArtifactWriter:
    def test_ensure_workspace_creates_contract_files(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))

        files = writer.ensure_workspace()

        assert set(files) == {
            "strategy_spec",
            "implementation_note",
            "backtest_report_md",
            "backtest_report_json",
            "iteration_log",
        }
        assert files["iteration_log"].read_text(encoding="utf-8").startswith("# Iteration Log")

    def test_write_strategy_spec_includes_human_checkpoint(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()

        path = writer.write_strategy_spec(
            strategy_spec=build_strategy(),
            iteration=2,
            market="BTCUSDT",
            timeframe="1h",
            acceptance_criteria=["Return > 0", "MDD < 30%"],
            human_decision=build_decision(),
        )

        content = path.read_text(encoding="utf-8")
        assert "## Human Decision Checkpoint" in content
        assert "Continue / Stop / Pivot: continue" in content
        assert "walk-forward validation, reduce drawdown" in content

    def test_write_backtest_report_outputs_markdown_and_json(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()

        paths = writer.write_backtest_report(
            iteration=3,
            strategy_spec=build_strategy(),
            backtest_report=build_backtest_report(),
            evaluation={"result": "needs_improvement"},
            command="workflow.run_backtest strategy=Demo Strategy",
            status="success",
            notes=["Trade count still modest"],
        )

        md_content = paths["markdown"].read_text(encoding="utf-8")
        json_content = json.loads(paths["json"].read_text(encoding="utf-8"))

        assert "Status: success" in md_content
        assert json_content["strategy_name"] == "Demo Strategy"
        assert json_content["net_return_pct"] == 12.5
        assert json_content["notes"] == ["Trade count still modest"]

    def test_append_iteration_log_records_human_decision(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()

        path = writer.append_iteration_log(
            iteration=1,
            spec_version="demo-iteration-1",
            code_status="validated",
            backtest_status="success",
            total_return=12.5,
            max_drawdown=18.0,
            strategy_recommendation="continue",
            human_decision=build_decision(),
            next_action="continue",
        )

        content = path.read_text(encoding="utf-8")
        assert "## Iteration 1" in content
        assert "Human decision: continue | Need more robustness checks" in content

    def test_write_implementation_note_keeps_validation_summary(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()

        path = writer.write_implementation_note(
            iteration=4,
            strategy_spec=build_strategy(),
            code_result=build_code_result(),
            validation=build_validation(),
            code_path="reports/iterations/iteration_04_demo.py",
        )

        content = path.read_text(encoding="utf-8")
        assert "Files changed: reports/iterations/iteration_04_demo.py" in content
        assert "Validation performed: passed" in content
        assert "total_return: 3.2" in content
