#!/usr/bin/env python3
"""Session-oriented task wrappers for artifact-driven agent execution."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from agents.strategy_developer_agent import EngineerCodeResult, StrategyDeveloperAgent, StrategySpec


class EngineerTechnique(Enum):
    DETERMINISTIC_TEMPLATE = "deterministic_template"
    REPO_NATIVE_REPAIR = "repo_native_repair"
    STRUCTURED_GENERATION = "structured_generation"


class EngineerExecutionMode(Enum):
    INLINE = "inline"
    SUBPROCESS = "subprocess"


@dataclass
class EngineerSessionInput:
    strategy_handoff_path: str
    technique: EngineerTechnique = EngineerTechnique.STRUCTURED_GENERATION
    md_context: Optional[str] = None
    previous_code: str = ""
    feedback: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["technique"] = self.technique.value
        return payload

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "EngineerSessionInput":
        return cls(
            strategy_handoff_path=str(payload["strategy_handoff_path"]),
            technique=EngineerTechnique(str(payload.get("technique", EngineerTechnique.STRUCTURED_GENERATION.value))),
            md_context=payload.get("md_context"),
            previous_code=str(payload.get("previous_code", "")),
            feedback=dict(payload.get("feedback", {}) or {}),
        )


@dataclass
class EngineerSessionResult:
    strategy_spec: StrategySpec
    identity: Dict[str, Any]
    technique: EngineerTechnique
    code_result: EngineerCodeResult
    handoff_payload: Dict[str, Any]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "strategy_spec": asdict(self.strategy_spec),
            "identity": dict(self.identity),
            "technique": self.technique.value,
            "code_result": asdict(self.code_result),
            "handoff_payload": dict(self.handoff_payload),
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "EngineerSessionResult":
        return cls(
            strategy_spec=StrategySpec(**dict(payload["strategy_spec"])),
            identity=dict(payload.get("identity", {}) or {}),
            technique=EngineerTechnique(str(payload.get("technique", EngineerTechnique.STRUCTURED_GENERATION.value))),
            code_result=EngineerCodeResult(**dict(payload["code_result"])),
            handoff_payload=dict(payload.get("handoff_payload", {}) or {}),
        )


class EngineerSessionTask:
    """Execute the engineer step from a machine-readable strategy handoff."""

    def __init__(
        self,
        developer: Optional[StrategyDeveloperAgent] = None,
        deterministic_builder: Optional[Callable[[StrategySpec], EngineerCodeResult]] = None,
    ):
        self.developer = developer or StrategyDeveloperAgent()
        self.deterministic_builder = deterministic_builder

    def run(self, session_input: EngineerSessionInput) -> EngineerSessionResult:
        payload = self._load_handoff(session_input.strategy_handoff_path)
        strategy_spec = self._strategy_spec_from_handoff(payload)
        identity = {
            "strategy_id": payload.get("strategy_id", ""),
            "iteration_id": payload.get("iteration_id", ""),
            "parent_strategy_id": payload.get("parent_strategy_id", ""),
        }

        if session_input.technique is EngineerTechnique.DETERMINISTIC_TEMPLATE:
            if self.deterministic_builder is None:
                raise ValueError("deterministic_builder is required for deterministic_template technique")
            code_result = self.deterministic_builder(strategy_spec)
        elif session_input.previous_code or session_input.feedback:
            code_result = self.developer.revise_strategy_code(
                strategy_spec,
                feedback=session_input.feedback,
                previous_code=session_input.previous_code,
                md_context=session_input.md_context,
            )
        else:
            code_result = self.developer.generate_strategy_code_structured(
                strategy_spec,
                md_context=session_input.md_context,
                feedback=session_input.feedback,
                previous_code=session_input.previous_code,
            )

        return EngineerSessionResult(
            strategy_spec=strategy_spec,
            identity=identity,
            technique=session_input.technique,
            code_result=code_result,
            handoff_payload=payload,
        )

    def _load_handoff(self, path: str) -> Dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def _strategy_spec_from_handoff(self, payload: Dict[str, Any]) -> StrategySpec:
        return StrategySpec(
            name=str(payload.get("strategy_name", "Unnamed Strategy")),
            description=str(payload.get("description", "")),
            indicators=list(payload.get("indicators", []) or []),
            entry_rules=str(payload.get("entry_rules", "")),
            exit_rules=str(payload.get("exit_rules", "")),
            parameters=dict(payload.get("parameters", {}) or {}),
            timeframe=str(payload.get("timeframe", "1h")),
            risk_level=str(payload.get("risk_level", "medium")),
        )


class EngineerSessionRunner:
    """Run engineer sessions inline or in a subprocess."""

    def __init__(
        self,
        task: Optional[EngineerSessionTask] = None,
        python_executable: Optional[str] = None,
    ):
        self.task = task or EngineerSessionTask()
        self.python_executable = python_executable or sys.executable

    def run(
        self,
        session_input: EngineerSessionInput,
        mode: EngineerExecutionMode = EngineerExecutionMode.INLINE,
    ) -> EngineerSessionResult:
        if mode is EngineerExecutionMode.INLINE or session_input.technique is EngineerTechnique.DETERMINISTIC_TEMPLATE:
            return self.task.run(session_input)
        return self._run_subprocess(session_input)

    def _run_subprocess(self, session_input: EngineerSessionInput) -> EngineerSessionResult:
        with tempfile.TemporaryDirectory(prefix="engineer-session-") as tmpdir:
            tmpdir_path = Path(tmpdir)
            input_path = tmpdir_path / "engineer_session_input.json"
            output_path = tmpdir_path / "engineer_session_result.json"
            input_path.write_text(
                json.dumps(session_input.to_payload(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [
                    self.python_executable,
                    "-m",
                    "agents.session_tasks",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                check=True,
            )
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            return EngineerSessionResult.from_payload(payload)


def _run_cli(input_path: str, output_path: str) -> None:
    session_input = EngineerSessionInput.from_payload(
        json.loads(Path(input_path).read_text(encoding="utf-8"))
    )
    result = EngineerSessionTask().run(session_input)
    Path(output_path).write_text(
        json.dumps(result.to_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the engineer session task from a JSON handoff payload.")
    parser.add_argument("--input", required=True, help="Path to the engineer session input JSON")
    parser.add_argument("--output", required=True, help="Path to the engineer session result JSON")
    args = parser.parse_args()
    _run_cli(args.input, args.output)


if __name__ == "__main__":
    main()

