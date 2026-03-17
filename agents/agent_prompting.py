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

AGENT_TOOL_HINTS: Dict[str, str] = {
    "strategy_agent": """Agent Workflow Hints:
- Use canonical research artifacts as the primary source of truth.
- Propose concrete hypothesis revisions, not implementation details.
- Treat human checkpoint guidance as authoritative when suggesting continue, revise, or pivot.""",
    "engineer_agent": """Agent Workflow Hints:
- Favor existing strategy patterns and deterministic templates before inventing new structures.
- Produce complete code that can pass syntax, subclass, instantiation, and smoke-backtest validation.
- Use validation failures as the primary input for the next repair step.""",
    "backtest_agent": """Agent Workflow Hints:
- Keep strategy code fixed during evaluation and focus on reproducible execution.
- Preserve run configuration details so downstream evaluation can compare iterations correctly.
- Log failures explicitly instead of masking them with partial success language.""",
    "evaluator_agent": """Agent Workflow Hints:
- Evaluate the reported metrics against stable thresholds and explicit risk concerns.
- Call out overfitting, weak trade counts, and configuration caveats before recommending continuation.
- Keep the scoring discipline consistent across iterations unless the human changes the rubric.""",
    "reporter_agent": """Agent Workflow Hints:
- Summarize what happened, why it matters, and what the human should decide next.
- Align all claims with canonical research artifacts and evaluator output.
- Highlight unresolved risks and human overrides, not just top-line metrics.""",
}


def get_agent_prompt_path(agent_name: str) -> Path:
    return PROMPTS_ROOT / agent_name / "AGENTS.md"


def load_agent_instructions(agent_name: str) -> str:
    path = get_agent_prompt_path(agent_name)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_repo_rules(project_root: str | None = None) -> str:
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent
    candidate = root / "AGENTS.md"
    if candidate.exists():
        return candidate.read_text(encoding="utf-8").strip()
    return ""


def build_agent_context(agent_name: str, project_root: str | None = None) -> str:
    sections: Dict[str, str] = {
        "Repo Rules": load_repo_rules(project_root=project_root),
        "Agent Rules": load_agent_instructions(agent_name),
        "Tool Capabilities": SHARED_TOOL_CAPABILITIES.strip(),
        "Workflow Hints": AGENT_TOOL_HINTS.get(agent_name, "").strip(),
    }
    rendered = []
    for title, content in sections.items():
        if not content:
            continue
        rendered.append(f"## {title}\n{content}")
    return "\n\n".join(rendered).strip()
