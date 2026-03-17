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
        failure_categories=[],
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
            "engineer_attempt_log",
            "engineer_reference_cache",
            "strategy_handoff",
            "engineer_handoff",
            "backtest_handoff",
            "evaluation_handoff",
        }
        assert files["iteration_log"].read_text(encoding="utf-8").startswith("# Iteration Log")
        assert files["strategy_handoff"].read_text(encoding="utf-8").strip() == "{}"
        assert files["engineer_handoff"].read_text(encoding="utf-8").strip() == "{}"

    def test_write_handoffs_outputs_machine_readable_payloads(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()

        strategy_path = writer.write_strategy_handoff(
            iteration=1,
            strategy_spec=build_strategy(),
            human_decision=build_decision(),
            acceptance_criteria=["Return > 0"],
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-001",
                "parent_strategy_id": "",
            },
        )
        engineer_path = writer.write_engineer_handoff(
            iteration=1,
            strategy_spec=build_strategy(),
            code_result=build_code_result(),
            validation=build_validation(),
            code_path="reports/iterations/demo.py",
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-001",
                "parent_strategy_id": "",
            },
        )
        backtest_path = writer.write_backtest_handoff(
            iteration=1,
            strategy_spec=build_strategy(),
            backtest_report=build_backtest_report(),
            evaluation={"result": "needs_improvement"},
            dataset_metadata={"row_count": 120},
            status="success",
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-001",
                "parent_strategy_id": "",
            },
        )
        evaluation_path = writer.write_evaluation_handoff(
            iteration=1,
            strategy_spec=build_strategy(),
            evaluation={"score": 70},
            proposed_action="continue",
            human_decision=build_decision(),
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-001",
                "parent_strategy_id": "",
            },
        )

        strategy_payload = json.loads(strategy_path.read_text(encoding="utf-8"))
        engineer_payload = json.loads(engineer_path.read_text(encoding="utf-8"))
        backtest_payload = json.loads(backtest_path.read_text(encoding="utf-8"))
        evaluation_payload = json.loads(evaluation_path.read_text(encoding="utf-8"))

        assert strategy_payload["handoff_type"] == "strategy_to_engineer"
        assert strategy_payload["strategy_id"] == "strat-123"
        assert engineer_payload["handoff_type"] == "engineer_to_backtest"
        assert engineer_payload["reference_context"] == {}
        assert backtest_payload["handoff_type"] == "backtest_to_evaluator"
        assert backtest_payload["dataset_metadata"]["row_count"] == 120
        assert evaluation_payload["handoff_type"] == "evaluator_to_strategy"
        assert evaluation_payload["proposed_action"] == "continue"

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
            dataset_metadata={
                "row_count": 1234,
                "actual_start": "2024-01-01T00:00:00",
                "actual_end": "2024-12-31T23:00:00",
                "summary": "BTCUSDT 1h rows=1234 window=2024-01-01T00:00:00 -> 2024-12-31T23:00:00",
                "overrides": {"interval": "1h"},
                "override_summary": "interval=1h",
            },
            human_decision=build_decision(),
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-003",
                "parent_strategy_id": "strat-root",
            },
        )

        md_content = paths["markdown"].read_text(encoding="utf-8")
        json_content = json.loads(paths["json"].read_text(encoding="utf-8"))

        assert "Status: success" in md_content
        assert "Strategy ID: strat-123" in md_content
        assert "Effective dataset rows: 1234" in md_content
        assert "Effective overrides: interval=1h" in md_content
        assert json_content["strategy_name"] == "Demo Strategy"
        assert json_content["strategy_id"] == "strat-123"
        assert json_content["net_return_pct"] == 12.5
        assert json_content["dataset_row_count"] == 1234
        assert json_content["effective_overrides"] == {"interval": "1h"}
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
            dataset_metadata={
                "summary": "BTCUSDT 1h rows=120 window=2024-01-01T00:00:00 -> 2024-01-05T23:00:00",
                "override_summary": "interval=30m",
            },
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-001",
                "parent_strategy_id": "",
            },
        )

        content = path.read_text(encoding="utf-8")
        assert "## Iteration 1" in content
        assert "Strategy ID: strat-123" in content
        assert "Human decision: continue | Need more robustness checks" in content
        assert "Dataset used: BTCUSDT 1h rows=120 window=2024-01-01T00:00:00 -> 2024-01-05T23:00:00" in content
        assert "Effective overrides: interval=30m" in content

    def test_append_engineer_attempt_records_failure_categories_and_reference_context(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()
        validation = SimpleNamespace(
            passed=False,
            issues=["Smoke backtest failed: invalid frequency"],
            failure_categories=["smoke_backtest"],
        )

        path = writer.append_engineer_attempt(
            iteration=2,
            strategy_spec=build_strategy(),
            technique="reference_guided_synthesis",
            validation=validation,
            code_path="reports/iterations/iteration_02_demo.py",
            identity={
                "strategy_id": "strat-123",
                "iteration_id": "iter-002",
                "parent_strategy_id": "",
            },
            reference_context={"repo_patterns": [{"pattern": "multi_timeframe_bband_reversion"}]},
            attempt_summary={"attempt_count": 1},
            policy_decision={"reasons": ["external references available"]},
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload[0]["technique"] == "reference_guided_synthesis"
        assert payload[0]["failure_categories"] == ["smoke_backtest"]
        assert payload[0]["reference_context"]["repo_patterns"][0]["pattern"] == "multi_timeframe_bband_reversion"
        assert payload[0]["policy_decision"]["reasons"] == ["external references available"]

    def test_append_engineer_reference_appends_curated_reference(self, tmp_path):
        writer = ResearchArtifactWriter(str(tmp_path / "research"))
        writer.ensure_workspace()

        path = writer.append_engineer_reference(
            {
                "name": "Example Repo",
                "source_type": "github",
                "summary": "Use as pattern source only",
                "tags": ["bband"],
            }
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload[0]["name"] == "Example Repo"
        assert payload[0]["source_type"] == "github"

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
        assert "Reference inputs used: none" in content
        assert "Validation performed: passed" in content
        assert "total_return: 3.2" in content
