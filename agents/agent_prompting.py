#!/usr/bin/env python3
"""Helpers for loading per-agent instructions and shared tool capability context."""

from __future__ import annotations

from pathlib import Path
from typing import Dict


PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"

SHARED_TOOL_CAPABILITIES = """Shared Tool Capabilities:
- MCP and Skills are available to the local orchestrator, not directly to the remote LLM.
- Repo-level AGENTS.md defines global workflow rules and canonical research artifacts.
- Agent-specific AGENTS.md files define role-local constraints.
- Prefer repo-local modules, deterministic templates, and validation feedback over speculative code.
"""


def get_agent_prompt_path(agent_name: str) -> Path:
    return PROMPTS_ROOT / agent_name / "AGENTS.md"


def load_agent_instructions(agent_name: str) -> str:
    path = get_agent_prompt_path(agent_name)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_repo_rules(project_root: str | None = None) -> str:
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
    for filename in ["AGENTS.md", "AGENTS.md.new"]:
        candidate = root / filename
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()
    return ""


def build_agent_context(agent_name: str, project_root: str | None = None) -> str:
    sections: Dict[str, str] = {
        "Repo Rules": load_repo_rules(project_root=project_root),
        "Agent Rules": load_agent_instructions(agent_name),
        "Tool Capabilities": SHARED_TOOL_CAPABILITIES.strip(),
    }
    rendered = []
    for title, content in sections.items():
        if not content:
            continue
        rendered.append(f"## {title}\n{content}")
    return "\n\n".join(rendered).strip()
