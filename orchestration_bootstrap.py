#!/usr/bin/env python3
"""Bootstrap helpers for autonomous tasks and deep research runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random
import re
from typing import Dict, Iterable, List, Optional


def slugify(value: str, max_length: int = 48) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if not normalized:
        normalized = "task"
    return normalized[:max_length].rstrip("-")


def build_run_name(topic: str, now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    suffix = f"{random.randint(0, 0xFFFF):04x}"
    return f"{now.strftime('%Y%m%d')}-{slugify(topic, max_length=28)}-{suffix}"


@dataclass
class AutonomousTaskPaths:
    root: Path
    task_list: Path
    progress: Path
    session_id: Path
    session_log: Path
    brief: Path


@dataclass
class ResearchRunPaths:
    root: Path
    prompts: Path
    logs: Path
    child_outputs: Path
    raw: Path
    cache: Path
    tmp: Path
    manifest: Path
    outline: Path


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def init_autonomous_task(
    project_root: str,
    task_name: str,
    description: str,
    goals: Optional[Iterable[str]] = None,
) -> AutonomousTaskPaths:
    root = Path(project_root) / ".autonomous" / slugify(task_name, max_length=30)
    root.mkdir(parents=True, exist_ok=True)
    goals_list = [item for item in (goals or []) if item]

    task_list = _write(
        root / "task_list.md",
        "\n".join(
            [
                "# Autonomous Task List",
                "",
                f"- Task: {task_name}",
                f"- Description: {description}",
                "",
                "## Tasks",
                "- [ ] Review latest research/strategy_spec.md and research/iteration_log.md",
                "- [ ] Execute one validated engineer/backtest iteration",
                "- [ ] Record the latest human checkpoint and next action",
                *[f"- [ ] {goal}" for goal in goals_list],
                "",
            ]
        ),
    )
    progress = _write(
        root / "progress.md",
        "\n".join(
            [
                "# Progress",
                "",
                f"- Created at: {datetime.now().isoformat(timespec='seconds')}",
                "- Session notes:",
                "",
            ]
        ),
    )
    session_id = _write(root / "session.id", "")
    session_log = _write(root / "session.log", "")
    brief = _write(
        root / "brief.md",
        "\n".join(
            [
                "# Task Brief",
                "",
                f"## Description\n{description}",
                "",
                "## Working Rules",
                "- Respect human checkpoints as the final control signal.",
                "- Keep research artifacts in research/ up to date.",
                "- Do not claim performance improvements without a fresh backtest report.",
                "",
            ]
        ),
    )
    return AutonomousTaskPaths(
        root=root,
        task_list=task_list,
        progress=progress,
        session_id=session_id,
        session_log=session_log,
        brief=brief,
    )


def init_deep_research_run(
    project_root: str,
    topic: str,
    question: str,
    dimensions: Optional[Iterable[str]] = None,
    now: Optional[datetime] = None,
) -> ResearchRunPaths:
    run_name = build_run_name(topic, now=now)
    root = Path(project_root) / ".research" / run_name
    prompts = root / "prompts"
    logs = root / "logs"
    child_outputs = root / "child_outputs"
    raw = root / "raw"
    cache = root / "cache"
    tmp = root / "tmp"

    for directory in [prompts, logs, child_outputs, raw, cache, tmp]:
        directory.mkdir(parents=True, exist_ok=True)

    dimensions_list = [item for item in (dimensions or []) if item]
    manifest = _write(
        root / "manifest.md",
        "\n".join(
            [
                "# Deep Research Manifest",
                "",
                f"- Topic: {topic}",
                f"- Question: {question}",
                f"- Created at: {(now or datetime.now()).isoformat(timespec='seconds')}",
                "",
                "## Dimensions",
                *([f"- {item}" for item in dimensions_list] or ["- TBD"]),
                "",
                "## Output Contract",
                "- Save raw findings into child_outputs/ as markdown.",
                "- Aggregate into a polished report instead of concatenating raw notes.",
                "- Cite sources inline and preserve the human checkpoint context.",
                "",
            ]
        ),
    )
    outline = _write(
        root / "polish_outline.md",
        "\n".join(
            [
                "# Polish Outline",
                "",
                "## Audience",
                "- Human operator reviewing strategy direction and evidence quality.",
                "",
                "## Sections",
                "- Executive summary",
                "- Candidate strategy families",
                "- Evidence and risks",
                "- Recommended next experiment",
                "",
            ]
        ),
    )
    return ResearchRunPaths(
        root=root,
        prompts=prompts,
        logs=logs,
        child_outputs=child_outputs,
        raw=raw,
        cache=cache,
        tmp=tmp,
        manifest=manifest,
        outline=outline,
    )
