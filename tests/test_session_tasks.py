import json
import subprocess
from pathlib import Path

from agents.session_tasks import (
    EngineerExecutionMode,
    EngineerSessionInput,
    EngineerSessionResult,
    EngineerSessionRunner,
    EngineerSessionTask,
    EngineerTechnique,
)
from agents.strategy_developer_agent import EngineerCodeResult, StrategySpec


class FakeDeveloper:
    def __init__(self):
        self.calls = []

    def generate_strategy_code_structured(self, spec, md_context=None, feedback=None, previous_code=""):
        self.calls.append(("generate", spec.name, md_context, feedback or {}, previous_code))
        return EngineerCodeResult(code="print('generate')", summary="generated")

    def revise_strategy_code(self, spec, feedback, previous_code, md_context=None):
        self.calls.append(("revise", spec.name, md_context, feedback or {}, previous_code))
        return EngineerCodeResult(code="print('revise')", summary="revised")


class TestEngineerSessionTask:
    def test_run_uses_structured_generation_from_strategy_handoff(self, tmp_path):
        handoff = tmp_path / "strategy_handoff.json"
        handoff.write_text(
            json.dumps(
                {
                    "handoff_type": "strategy_to_engineer",
                    "strategy_id": "strat-123",
                    "iteration_id": "iter-001",
                    "parent_strategy_id": "",
                    "iteration": 1,
                    "strategy_name": "Demo Strategy",
                    "description": "desc",
                    "indicators": ["BBand"],
                    "entry_rules": "buy",
                    "exit_rules": "sell",
                    "parameters": {"bb_period": 20},
                    "timeframe": "1h",
                    "risk_level": "medium",
                }
            ),
            encoding="utf-8",
        )
        developer = FakeDeveloper()
        task = EngineerSessionTask(developer=developer)

        result = task.run(EngineerSessionInput(strategy_handoff_path=str(handoff)))

        assert result.identity["strategy_id"] == "strat-123"
        assert result.strategy_spec.name == "Demo Strategy"
        assert result.technique is EngineerTechnique.STRUCTURED_GENERATION
        assert result.code_result.summary == "generated"
        assert developer.calls[0][0] == "generate"

    def test_run_uses_revision_when_previous_code_or_feedback_exists(self, tmp_path):
        handoff = tmp_path / "strategy_handoff.json"
        handoff.write_text(
            json.dumps(
                {
                    "handoff_type": "strategy_to_engineer",
                    "strategy_id": "strat-123",
                    "iteration_id": "iter-002",
                    "parent_strategy_id": "",
                    "iteration": 2,
                    "strategy_name": "Demo Strategy",
                    "description": "desc",
                    "indicators": ["BBand"],
                    "entry_rules": "buy",
                    "exit_rules": "sell",
                    "parameters": {"bb_period": 20},
                    "timeframe": "1h",
                    "risk_level": "medium",
                }
            ),
            encoding="utf-8",
        )
        developer = FakeDeveloper()
        task = EngineerSessionTask(developer=developer)

        result = task.run(
            EngineerSessionInput(
                strategy_handoff_path=str(handoff),
                technique=EngineerTechnique.REPO_NATIVE_REPAIR,
                previous_code="broken()",
                feedback={"validation_issues": ["syntax error"]},
            )
        )

        assert result.code_result.summary == "revised"
        assert developer.calls[0][0] == "revise"

    def test_run_uses_deterministic_builder_for_deterministic_technique(self, tmp_path):
        handoff = tmp_path / "strategy_handoff.json"
        handoff.write_text(
            json.dumps(
                {
                    "handoff_type": "strategy_to_engineer",
                    "strategy_id": "strat-123",
                    "iteration_id": "iter-003",
                    "parent_strategy_id": "",
                    "iteration": 3,
                    "strategy_name": "Known Strategy",
                    "description": "desc",
                    "indicators": ["MA"],
                    "entry_rules": "buy",
                    "exit_rules": "sell",
                    "parameters": {},
                    "timeframe": "1h",
                    "risk_level": "medium",
                }
            ),
            encoding="utf-8",
        )
        task = EngineerSessionTask(
            developer=FakeDeveloper(),
            deterministic_builder=lambda spec: EngineerCodeResult(code="print('det')", summary=spec.name),
        )

        result = task.run(
            EngineerSessionInput(
                strategy_handoff_path=str(handoff),
                technique=EngineerTechnique.DETERMINISTIC_TEMPLATE,
            )
        )

        assert result.code_result.code == "print('det')"
        assert result.code_result.summary == "Known Strategy"

    def test_result_payload_round_trip(self, tmp_path):
        result = EngineerSessionResult(
            strategy_spec=StrategySpec(
                name="Demo Strategy",
                description="desc",
                indicators=["BBand"],
                entry_rules="buy",
                exit_rules="sell",
                parameters={},
                timeframe="1h",
                risk_level="medium",
            ),
            identity={"strategy_id": "strat-123", "iteration_id": "iter-001", "parent_strategy_id": ""},
            technique=EngineerTechnique.STRUCTURED_GENERATION,
            code_result=EngineerCodeResult(code="print('x')", summary="ok", assumptions=["a"], raw_response="raw"),
            handoff_payload={"strategy_name": "Demo Strategy"},
        )

        restored = EngineerSessionResult.from_payload(result.to_payload())

        assert restored.identity["strategy_id"] == "strat-123"
        assert restored.code_result.raw_response == "raw"
        assert restored.strategy_spec.name == "Demo Strategy"

    def test_runner_subprocess_mode_reads_written_result(self, tmp_path, monkeypatch):
        handoff = tmp_path / "strategy_handoff.json"
        handoff.write_text(
            json.dumps(
                {
                    "handoff_type": "strategy_to_engineer",
                    "strategy_id": "strat-123",
                    "iteration_id": "iter-004",
                    "parent_strategy_id": "",
                    "iteration": 4,
                    "strategy_name": "Demo Strategy",
                    "description": "desc",
                    "indicators": ["BBand"],
                    "entry_rules": "buy",
                    "exit_rules": "sell",
                    "parameters": {"bb_period": 20},
                    "timeframe": "1h",
                    "risk_level": "medium",
                }
            ),
            encoding="utf-8",
        )

        def fake_subprocess_run(cmd, check):
            assert cmd[1:3] == ["-m", "agents.session_tasks"]
            output_path = Path(cmd[cmd.index("--output") + 1])
            payload = {
                "strategy_spec": {
                    "name": "Demo Strategy",
                    "description": "desc",
                    "indicators": ["BBand"],
                    "entry_rules": "buy",
                    "exit_rules": "sell",
                    "parameters": {"bb_period": 20},
                    "timeframe": "1h",
                    "risk_level": "medium",
                },
                "identity": {
                    "strategy_id": "strat-123",
                    "iteration_id": "iter-004",
                    "parent_strategy_id": "",
                },
                "technique": "structured_generation",
                "code_result": {
                    "code": "print('child')",
                    "summary": "child",
                    "assumptions": [],
                    "raw_response": "raw",
                },
                "handoff_payload": {"strategy_name": "Demo Strategy"},
            }
            output_path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr("agents.session_tasks.subprocess.run", fake_subprocess_run)
        runner = EngineerSessionRunner(task=EngineerSessionTask(developer=FakeDeveloper()))

        result = runner.run(
            EngineerSessionInput(strategy_handoff_path=str(handoff)),
            mode=EngineerExecutionMode.SUBPROCESS,
        )

        assert result.code_result.summary == "child"
        assert result.identity["iteration_id"] == "iter-004"
