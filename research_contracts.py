#!/usr/bin/env python3
"""
Research artifact contracts for the human-in-the-loop strategy workflow.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {k: _to_serializable(v) for k, v in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_serializable(v) for v in value]
    if hasattr(value, "__dict__"):
        try:
            return {str(k): _to_serializable(v) for k, v in vars(value).items()}
        except TypeError:
            return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except TypeError:
            return str(value)
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class ResearchArtifactWriter:
    """Writes canonical research artifacts for agent collaboration."""

    def __init__(self, research_dir: str = "research"):
        self.research_dir = Path(research_dir)

    def ensure_workspace(self) -> Dict[str, Path]:
        self.research_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "strategy_spec": self.research_dir / "strategy_spec.md",
            "implementation_note": self.research_dir / "implementation_note.md",
            "backtest_report_md": self.research_dir / "backtest_report.md",
            "backtest_report_json": self.research_dir / "backtest_report.json",
            "iteration_log": self.research_dir / "iteration_log.md",
            "engineer_attempt_log": self.research_dir / "engineer_attempt_log.json",
            "engineer_reference_cache": self.research_dir / "engineer_reference_cache.json",
            "strategy_handoff": self.research_dir / "strategy_handoff.json",
            "engineer_handoff": self.research_dir / "engineer_handoff.json",
            "backtest_handoff": self.research_dir / "backtest_handoff.json",
            "evaluation_handoff": self.research_dir / "evaluation_handoff.json",
        }
        for key, path in files.items():
            if path.exists():
                continue
            if key == "iteration_log":
                _write_text(path, "# Iteration Log\n")
            elif key in {"engineer_attempt_log", "engineer_reference_cache"}:
                _write_text(path, "[]\n")
            elif path.suffix == ".json":
                _write_text(path, "{}\n")
            else:
                _write_text(path, "")
        return files

    def append_engineer_reference(self, reference_entry: Dict[str, Any]) -> Path:
        path = self.research_dir / "engineer_reference_cache.json"
        existing = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
        existing.append(_to_serializable(reference_entry))
        return _write_text(path, json.dumps(existing, ensure_ascii=False, indent=2) + "\n")

    def append_engineer_attempt(
        self,
        iteration: int,
        strategy_spec: Any,
        technique: str,
        validation: Any,
        code_path: str,
        identity: Optional[Dict[str, Any]] = None,
        reference_context: Optional[Dict[str, Any]] = None,
        attempt_summary: Optional[Dict[str, Any]] = None,
    ) -> Path:
        path = self.research_dir / "engineer_attempt_log.json"
        existing = []
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
        existing.append(
            {
                "iteration": iteration,
                "strategy_id": _stringify((identity or {}).get("strategy_id")),
                "iteration_id": _stringify((identity or {}).get("iteration_id")),
                "parent_strategy_id": _stringify((identity or {}).get("parent_strategy_id")),
                "strategy_name": _stringify(getattr(strategy_spec, "name", "")),
                "technique": technique,
                "code_path": code_path,
                "validation_passed": bool(getattr(validation, "passed", False)),
                "validation_issues": _to_serializable(getattr(validation, "issues", [])),
                "failure_categories": _to_serializable(getattr(validation, "failure_categories", [])),
                "reference_context": _to_serializable(reference_context or {}),
                "attempt_summary": _to_serializable(attempt_summary or {}),
            }
        )
        return _write_text(path, json.dumps(existing, ensure_ascii=False, indent=2) + "\n")

    def write_strategy_handoff(
        self,
        iteration: int,
        strategy_spec: Any,
        human_decision: Optional[Any] = None,
        acceptance_criteria: Optional[Iterable[str]] = None,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        identity = identity or {}
        payload = {
            "handoff_type": "strategy_to_engineer",
            "iteration": iteration,
            "strategy_id": _stringify(identity.get("strategy_id")),
            "iteration_id": _stringify(identity.get("iteration_id")),
            "parent_strategy_id": _stringify(identity.get("parent_strategy_id")),
            "strategy_name": _stringify(getattr(strategy_spec, "name", "")),
            "description": _stringify(getattr(strategy_spec, "description", "")),
            "indicators": _to_serializable(getattr(strategy_spec, "indicators", [])),
            "entry_rules": _stringify(getattr(strategy_spec, "entry_rules", "")),
            "exit_rules": _stringify(getattr(strategy_spec, "exit_rules", "")),
            "parameters": _to_serializable(getattr(strategy_spec, "parameters", {})),
            "timeframe": _stringify(getattr(strategy_spec, "timeframe", "")),
            "risk_level": _stringify(getattr(strategy_spec, "risk_level", "")),
            "acceptance_criteria": list(acceptance_criteria or []),
            "human_decision": _to_serializable(human_decision) if human_decision is not None else None,
        }
        return _write_text(
            self.research_dir / "strategy_handoff.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def write_strategy_spec(
        self,
        strategy_spec: Any,
        iteration: int,
        market: str,
        timeframe: str,
        acceptance_criteria: Iterable[str],
        human_decision: Optional[Any] = None,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        identity = identity or {}
        decision_action = getattr(human_decision, "action", "")
        if hasattr(decision_action, "value"):
            decision_action = decision_action.value
        rationale = getattr(human_decision, "rationale", "")
        next_focus = getattr(human_decision, "next_focus", []) or []

        content = "\n".join(
            [
                "# Strategy Spec",
                "",
                "## Metadata",
                f"- Strategy ID: {_stringify(identity.get('strategy_id')) or 'pending'}",
                f"- Iteration ID: {_stringify(identity.get('iteration_id')) or 'pending'}",
                f"- Parent Strategy ID: {_stringify(identity.get('parent_strategy_id')) or 'none'}",
                f"- Strategy: {_stringify(getattr(strategy_spec, 'name', ''))}",
                f"- Iteration: {iteration}",
                f"- Market: {market}",
                f"- Timeframe: {timeframe}",
                "",
                "## Hypothesis",
                _stringify(getattr(strategy_spec, "description", "")) or "TBD",
                "",
                "## Entry Rules",
                f"- {_stringify(getattr(strategy_spec, 'entry_rules', '')) or 'TBD'}",
                "",
                "## Exit Rules",
                f"- {_stringify(getattr(strategy_spec, 'exit_rules', '')) or 'TBD'}",
                "",
                "## Position Sizing",
                "- Full allocation unless strategy parameters specify otherwise.",
                "",
                "## Risk Controls",
                f"- Risk level: {_stringify(getattr(strategy_spec, 'risk_level', 'medium'))}",
                "",
                "## Parameters Under Test",
                *(
                    [f"- {key}: {_to_serializable(value)}" for key, value in (getattr(strategy_spec, "parameters", {}) or {}).items()]
                    or ["- None"]
                ),
                "",
                "## Acceptance Criteria",
                *[f"- {item}" for item in acceptance_criteria],
                "",
                "## Human Decision Checkpoint",
                f"- Continue / Stop / Pivot: {_stringify(decision_action) or 'pending'}",
                f"- Human rationale: {_stringify(rationale) or 'pending'}",
                f"- Any overridden constraints or new priorities: {', '.join(next_focus) if next_focus else 'none'}",
                "",
            ]
        )
        return _write_text(self.research_dir / "strategy_spec.md", content)

    def write_implementation_note(
        self,
        iteration: int,
        strategy_spec: Any,
        code_result: Any,
        validation: Any,
        code_path: str,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        identity = identity or {}
        assumptions = getattr(code_result, "assumptions", []) or []
        issues = getattr(validation, "issues", []) or []
        smoke_metrics = getattr(validation, "smoke_metrics", {}) or {}

        content = "\n".join(
            [
                "# Implementation Note",
                "",
                f"- Strategy ID: {_stringify(identity.get('strategy_id')) or 'pending'}",
                f"- Iteration ID: {_stringify(identity.get('iteration_id')) or 'pending'}",
                f"- Iteration: {iteration}",
                f"- Strategy: {_stringify(getattr(strategy_spec, 'name', ''))}",
                f"- Files changed: {code_path or 'N/A'}",
                f"- Strategy behaviors implemented: {_stringify(getattr(code_result, 'summary', '')) or 'N/A'}",
                f"- Assumptions: {', '.join(_stringify(item) for item in assumptions) if assumptions else 'none'}",
                f"- Known gaps: {', '.join(_stringify(item) for item in issues) if issues else 'none'}",
                f"- Validation performed: {'passed' if getattr(validation, 'passed', False) else 'failed'}",
                "",
                "## Smoke Metrics",
                *(
                    [f"- {key}: {_to_serializable(value)}" for key, value in smoke_metrics.items()]
                    or ["- None"]
                ),
                "",
            ]
        )
        return _write_text(self.research_dir / "implementation_note.md", content)

    def write_engineer_handoff(
        self,
        iteration: int,
        strategy_spec: Any,
        code_result: Any,
        validation: Any,
        code_path: str,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        identity = identity or {}
        payload = {
            "handoff_type": "engineer_to_backtest",
            "iteration": iteration,
            "strategy_id": _stringify(identity.get("strategy_id")),
            "iteration_id": _stringify(identity.get("iteration_id")),
            "parent_strategy_id": _stringify(identity.get("parent_strategy_id")),
            "strategy_name": _stringify(getattr(strategy_spec, "name", "")),
            "code_path": code_path,
            "implementation_summary": _stringify(getattr(code_result, "summary", "")),
            "assumptions": _to_serializable(getattr(code_result, "assumptions", [])),
            "validation_passed": bool(getattr(validation, "passed", False)),
            "validation_issues": _to_serializable(getattr(validation, "issues", [])),
            "failure_categories": _to_serializable(getattr(validation, "failure_categories", [])),
            "smoke_metrics": _to_serializable(getattr(validation, "smoke_metrics", {})),
        }
        return _write_text(
            self.research_dir / "engineer_handoff.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def write_backtest_report(
        self,
        iteration: int,
        strategy_spec: Any,
        backtest_report: Optional[Any],
        evaluation: Optional[Any],
        command: str,
        status: str,
        notes: Optional[Iterable[str]] = None,
        dataset_metadata: Optional[Dict[str, Any]] = None,
        human_decision: Optional[Any] = None,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Path]:
        notes_list = [str(item) for item in (notes or [])]
        report_md = self._render_backtest_report_md(
            iteration=iteration,
            strategy_spec=strategy_spec,
            backtest_report=backtest_report,
            command=command,
            status=status,
            notes=notes_list,
            dataset_metadata=dataset_metadata or {},
            human_decision=human_decision,
            identity=identity or {},
        )
        report_json = self._render_backtest_report_json(
            iteration=iteration,
            strategy_spec=strategy_spec,
            backtest_report=backtest_report,
            evaluation=evaluation,
            command=command,
            status=status,
            notes=notes_list,
            dataset_metadata=dataset_metadata or {},
            human_decision=human_decision,
            identity=identity or {},
        )
        return {
            "markdown": _write_text(self.research_dir / "backtest_report.md", report_md),
            "json": _write_text(
                self.research_dir / "backtest_report.json",
                json.dumps(report_json, ensure_ascii=False, indent=2) + "\n",
            ),
        }

    def write_backtest_handoff(
        self,
        iteration: int,
        strategy_spec: Any,
        backtest_report: Optional[Any],
        evaluation: Optional[Any],
        dataset_metadata: Optional[Dict[str, Any]] = None,
        status: str = "",
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        identity = identity or {}
        config = getattr(backtest_report, "config", None)
        payload = {
            "handoff_type": "backtest_to_evaluator",
            "iteration": iteration,
            "strategy_id": _stringify(identity.get("strategy_id")),
            "iteration_id": _stringify(identity.get("iteration_id")),
            "parent_strategy_id": _stringify(identity.get("parent_strategy_id")),
            "strategy_name": _stringify(getattr(strategy_spec, "name", "")),
            "status": status,
            "market": _stringify(getattr(config, "symbol", "")),
            "timeframe": _stringify(getattr(config, "interval", "")),
            "period_start": _stringify(getattr(config, "start_date", "")),
            "period_end": _stringify(getattr(config, "end_date", "")),
            "dataset_metadata": _to_serializable(dataset_metadata or {}),
            "metrics": {
                "net_return_pct": _to_serializable(getattr(backtest_report, "total_return", None)),
                "max_drawdown_pct": _to_serializable(getattr(backtest_report, "max_drawdown", None)),
                "sharpe": _to_serializable(getattr(backtest_report, "sharpe_ratio", None)),
                "win_rate_pct": _to_serializable(getattr(backtest_report, "win_rate", None)),
                "profit_factor": _to_serializable(getattr(backtest_report, "profit_factor", None)),
                "total_trades": _to_serializable(getattr(backtest_report, "total_trades", None)),
            },
            "evaluation_snapshot": _to_serializable(evaluation) if evaluation is not None else None,
        }
        return _write_text(
            self.research_dir / "backtest_handoff.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def write_evaluation_handoff(
        self,
        iteration: int,
        strategy_spec: Any,
        evaluation: Any,
        proposed_action: str,
        human_decision: Optional[Any] = None,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        identity = identity or {}
        payload = {
            "handoff_type": "evaluator_to_strategy",
            "iteration": iteration,
            "strategy_id": _stringify(identity.get("strategy_id")),
            "iteration_id": _stringify(identity.get("iteration_id")),
            "parent_strategy_id": _stringify(identity.get("parent_strategy_id")),
            "strategy_name": _stringify(getattr(strategy_spec, "name", "")),
            "evaluation": _to_serializable(evaluation),
            "proposed_action": proposed_action,
            "human_decision": _to_serializable(human_decision) if human_decision is not None else None,
        }
        return _write_text(
            self.research_dir / "evaluation_handoff.json",
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def append_iteration_log(
        self,
        iteration: int,
        spec_version: str,
        code_status: str,
        backtest_status: str,
        total_return: Optional[float],
        max_drawdown: Optional[float],
        strategy_recommendation: str,
        human_decision: Optional[Any],
        next_action: str,
        dataset_metadata: Optional[Dict[str, Any]] = None,
        identity: Optional[Dict[str, Any]] = None,
    ) -> Path:
        path = self.research_dir / "iteration_log.md"
        if not path.exists():
            _write_text(path, "# Iteration Log\n")
        action = getattr(human_decision, "action", "")
        if hasattr(action, "value"):
            action = action.value
        rationale = getattr(human_decision, "rationale", "")
        dataset_metadata = dataset_metadata or {}
        identity = identity or {}
        dataset_summary = dataset_metadata.get("summary", "")
        override_summary = dataset_metadata.get("override_summary", "")
        entry = "\n".join(
            [
                "",
                f"## Iteration {iteration}",
                f"- Strategy ID: {_stringify(identity.get('strategy_id')) or 'pending'}",
                f"- Iteration ID: {_stringify(identity.get('iteration_id')) or 'pending'}",
                f"- Parent Strategy ID: {_stringify(identity.get('parent_strategy_id')) or 'none'}",
                f"- Spec version: {spec_version}",
                f"- Code status: {code_status}",
                f"- Backtest status: {backtest_status}",
                f"- Return: {'' if total_return is None else total_return}",
                f"- MDD: {'' if max_drawdown is None else max_drawdown}",
                f"- Strategy recommendation: {strategy_recommendation}",
                f"- Human decision: {action or 'pending'}{f' | {rationale}' if rationale else ''}",
                f"- Dataset used: {dataset_summary or 'unknown'}",
                f"- Effective overrides: {override_summary or 'none'}",
                f"- Next action: {next_action}",
                "",
            ]
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        return path

    def _render_backtest_report_md(
        self,
        iteration: int,
        strategy_spec: Any,
        backtest_report: Optional[Any],
        command: str,
        status: str,
        notes: Iterable[str],
        dataset_metadata: Dict[str, Any],
        human_decision: Optional[Any],
        identity: Dict[str, Any],
    ) -> str:
        config = getattr(backtest_report, "config", None)
        run_timestamp = datetime.now().isoformat(timespec="seconds")
        action = getattr(human_decision, "action", "")
        if hasattr(action, "value"):
            action = action.value
        override_summary = dataset_metadata.get("override_summary", "")
        lines = [
            "# Backtest Report",
            "",
            f"- Strategy ID: {_stringify(identity.get('strategy_id')) or 'pending'}",
            f"- Iteration ID: {_stringify(identity.get('iteration_id')) or 'pending'}",
            f"- Parent Strategy ID: {_stringify(identity.get('parent_strategy_id')) or 'none'}",
            f"- Strategy: {_stringify(getattr(strategy_spec, 'name', ''))}",
            f"- Iteration: {iteration}",
            f"- Dataset / symbol / timeframe used: {_stringify(getattr(config, 'symbol', ''))} / {_stringify(getattr(config, 'interval', getattr(strategy_spec, 'timeframe', '')))}",
            f"- Requested period: {_stringify(getattr(config, 'start_date', ''))} -> {_stringify(getattr(config, 'end_date', ''))}",
            f"- Effective dataset rows: {_stringify(dataset_metadata.get('row_count', ''))}",
            f"- Effective dataset window: {_stringify(dataset_metadata.get('actual_start', ''))} -> {_stringify(dataset_metadata.get('actual_end', ''))}",
            f"- Effective overrides: {_stringify(override_summary) or 'none'}",
            f"- Command executed: {command}",
            f"- Run timestamp: {run_timestamp}",
            f"- Status: {status}",
            "",
            "## Summary Metrics",
        ]
        metrics = [
            ("Net return %", getattr(backtest_report, "total_return", None)),
            ("Max drawdown %", getattr(backtest_report, "max_drawdown", None)),
            ("Sharpe", getattr(backtest_report, "sharpe_ratio", None)),
            ("Sortino", None),
            ("Win rate %", getattr(backtest_report, "win_rate", None)),
            ("Profit factor", getattr(backtest_report, "profit_factor", None)),
            ("Total trades", getattr(backtest_report, "total_trades", None)),
        ]
        for label, value in metrics:
            lines.append(f"- {label}: {'' if value is None else value}")
        lines.extend(
            [
                "",
                "## Notable Trades Or Failure Modes",
                *([f"- {item}" for item in notes] or ["- None"]),
                "",
                "## Human Checkpoint",
                f"- Final action after this iteration: {_stringify(action) or 'pending'}",
                "",
                "## Interpretation Limits",
                f"- Evaluation status: {_stringify(status)}",
                "",
            ]
        )
        return "\n".join(lines)

    def _render_backtest_report_json(
        self,
        iteration: int,
        strategy_spec: Any,
        backtest_report: Optional[Any],
        evaluation: Optional[Any],
        command: str,
        status: str,
        notes: Iterable[str],
        dataset_metadata: Dict[str, Any],
        human_decision: Optional[Any],
        identity: Dict[str, Any],
    ) -> Dict[str, Any]:
        config = getattr(backtest_report, "config", None)
        action = getattr(human_decision, "action", "")
        if hasattr(action, "value"):
            action = action.value
        return {
            "strategy_name": _stringify(getattr(strategy_spec, "name", "")),
            "strategy_id": _stringify(identity.get("strategy_id")),
            "iteration_id": _stringify(identity.get("iteration_id")),
            "parent_strategy_id": _stringify(identity.get("parent_strategy_id")),
            "iteration": iteration,
            "status": status,
            "market": _stringify(getattr(config, "symbol", "")),
            "timeframe": _stringify(getattr(config, "interval", getattr(strategy_spec, "timeframe", ""))),
            "period_start": _stringify(getattr(config, "start_date", "")),
            "period_end": _stringify(getattr(config, "end_date", "")),
            "dataset_row_count": _to_serializable(dataset_metadata.get("row_count")),
            "dataset_actual_start": _to_serializable(dataset_metadata.get("actual_start")),
            "dataset_actual_end": _to_serializable(dataset_metadata.get("actual_end")),
            "dataset_summary": _to_serializable(dataset_metadata.get("summary")),
            "effective_overrides": _to_serializable(dataset_metadata.get("overrides", {})),
            "net_return_pct": _to_serializable(getattr(backtest_report, "total_return", 0)),
            "max_drawdown_pct": _to_serializable(getattr(backtest_report, "max_drawdown", 0)),
            "sharpe": _to_serializable(getattr(backtest_report, "sharpe_ratio", None)),
            "sortino": None,
            "win_rate_pct": _to_serializable(getattr(backtest_report, "win_rate", None)),
            "profit_factor": _to_serializable(getattr(backtest_report, "profit_factor", None)),
            "total_trades": _to_serializable(getattr(backtest_report, "total_trades", 0)),
            "notes": list(notes),
            "command": command,
            "evaluation": _to_serializable(evaluation) if evaluation is not None else None,
            "human_decision": _stringify(action),
        }
