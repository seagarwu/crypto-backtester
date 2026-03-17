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
from typing import Any, Callable, Dict, List, Optional

from agents.strategy_developer_agent import EngineerCodeResult, StrategyDeveloperAgent, StrategySpec


class EngineerTechnique(Enum):
    DETERMINISTIC_TEMPLATE = "deterministic_template"
    REPO_NATIVE_REPAIR = "repo_native_repair"
    STRUCTURED_GENERATION = "structured_generation"
    REFERENCE_GUIDED_SYNTHESIS = "reference_guided_synthesis"
    CONSERVATIVE_FALLBACK = "conservative_fallback"


class EngineerExecutionMode(Enum):
    INLINE = "inline"
    SUBPROCESS = "subprocess"


class EngineerFailureCategory(Enum):
    EMPTY_OUTPUT = "empty_output"
    FORBIDDEN_DEPENDENCY = "forbidden_dependency"
    SYNTAX = "syntax"
    IMPORT = "import"
    STRUCTURE = "structure"
    INSTANTIATION = "instantiation"
    SMOKE_BACKTEST = "smoke_backtest"
    FULL_BACKTEST = "full_backtest"
    PERFORMANCE = "performance"
    UNKNOWN = "unknown"


@dataclass
class EngineerSessionInput:
    strategy_handoff_path: str
    technique: EngineerTechnique = EngineerTechnique.STRUCTURED_GENERATION
    md_context: Optional[str] = None
    previous_code: str = ""
    feedback: Dict[str, Any] = field(default_factory=dict)
    reference_context: Dict[str, Any] = field(default_factory=dict)
    prior_attempts: List[Dict[str, Any]] = field(default_factory=list)

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
            reference_context=dict(payload.get("reference_context", {}) or {}),
            prior_attempts=list(payload.get("prior_attempts", []) or []),
        )


@dataclass
class EngineerSessionResult:
    strategy_spec: StrategySpec
    identity: Dict[str, Any]
    technique: EngineerTechnique
    code_result: EngineerCodeResult
    handoff_payload: Dict[str, Any]
    reference_context: Dict[str, Any] = field(default_factory=dict)
    attempt_summary: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "strategy_spec": asdict(self.strategy_spec),
            "identity": dict(self.identity),
            "technique": self.technique.value,
            "code_result": asdict(self.code_result),
            "handoff_payload": dict(self.handoff_payload),
            "reference_context": dict(self.reference_context),
            "attempt_summary": dict(self.attempt_summary),
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "EngineerSessionResult":
        return cls(
            strategy_spec=StrategySpec(**dict(payload["strategy_spec"])),
            identity=dict(payload.get("identity", {}) or {}),
            technique=EngineerTechnique(str(payload.get("technique", EngineerTechnique.STRUCTURED_GENERATION.value))),
            code_result=EngineerCodeResult(**dict(payload["code_result"])),
            handoff_payload=dict(payload.get("handoff_payload", {}) or {}),
            reference_context=dict(payload.get("reference_context", {}) or {}),
            attempt_summary=dict(payload.get("attempt_summary", {}) or {}),
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
        elif session_input.technique is EngineerTechnique.REFERENCE_GUIDED_SYNTHESIS:
            code_result = self.developer.generate_strategy_code_structured(
                strategy_spec,
                md_context=self._merge_context(session_input.md_context, session_input.reference_context),
                feedback=self._merge_feedback(session_input.feedback, session_input.reference_context, session_input.prior_attempts),
                previous_code=session_input.previous_code,
            )
        elif session_input.technique is EngineerTechnique.CONSERVATIVE_FALLBACK:
            code_result = self.developer.generate_strategy_code_structured(
                strategy_spec,
                md_context=self._merge_context(
                    session_input.md_context,
                    {
                        **session_input.reference_context,
                        "fallback_guidance": "Prefer the smallest repo-native implementation that satisfies BaseStrategy contracts and avoids advanced multi-timeframe logic.",
                    },
                ),
                feedback=self._merge_feedback(
                    session_input.feedback,
                    {
                        **session_input.reference_context,
                        "fallback_guidance": "Minimize moving parts. Favor correctness and validation success over feature richness.",
                    },
                    session_input.prior_attempts,
                ),
                previous_code=session_input.previous_code,
            )
        elif session_input.previous_code or session_input.feedback:
            code_result = self.developer.revise_strategy_code(
                strategy_spec,
                feedback=self._merge_feedback(session_input.feedback, session_input.reference_context, session_input.prior_attempts),
                previous_code=session_input.previous_code,
                md_context=self._merge_context(session_input.md_context, session_input.reference_context),
            )
        else:
            code_result = self.developer.generate_strategy_code_structured(
                strategy_spec,
                md_context=self._merge_context(session_input.md_context, session_input.reference_context),
                feedback=self._merge_feedback(session_input.feedback, session_input.reference_context, session_input.prior_attempts),
                previous_code=session_input.previous_code,
            )

        return EngineerSessionResult(
            strategy_spec=strategy_spec,
            identity=identity,
            technique=session_input.technique,
            code_result=code_result,
            handoff_payload=payload,
            reference_context=session_input.reference_context,
            attempt_summary={
                "attempt_count": len(session_input.prior_attempts),
                "latest_failure_categories": self._latest_failure_categories(session_input.prior_attempts),
            },
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

    def _merge_context(self, md_context: Optional[str], reference_context: Dict[str, Any]) -> Optional[str]:
        sections: List[str] = []
        if md_context:
            sections.append(md_context)
        if reference_context:
            sections.append(
                "Reference guidance:\n"
                + json.dumps(reference_context, ensure_ascii=False, indent=2)
            )
        return "\n\n".join(section for section in sections if section) or None

    def _merge_feedback(
        self,
        feedback: Dict[str, Any],
        reference_context: Dict[str, Any],
        prior_attempts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged = dict(feedback or {})
        if reference_context:
            merged["reference_context"] = reference_context
        if prior_attempts:
            merged["prior_attempts"] = prior_attempts
        return merged

    def _latest_failure_categories(self, prior_attempts: List[Dict[str, Any]]) -> List[str]:
        if not prior_attempts:
            return []
        return list(prior_attempts[-1].get("failure_categories", []) or [])


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
