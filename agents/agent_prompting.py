#!/usr/bin/env python3
"""Helpers for loading per-agent instructions and shared tool capability context."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Literal, Tuple


PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"

SHARED_TOOL_CAPABILITIES = """Shared Tool Capabilities:
- MCP and Skills are available to the local orchestrator, not directly to the remote LLM.
- Repo-level AGENTS.md defines global workflow rules and canonical research artifacts.
- Agent-specific AGENTS.md files define role-local constraints.
- Prefer repo-local modules, deterministic templates, and validation feedback over speculative code.
"""

ENGINEER_BOOTSTRAP_FILES: List[Tuple[str, str]] = [
    (
        "strategies/base.py",
        "BaseStrategy only requires generate_signals(data)->DataFrame; super().__init__(name=...) is the correct initializer and get_params() is optional.",
    ),
    (
        "strategies/ma_crossover.py",
        "Repo-native example: parameters live in __init__, required_indicators is set on self, and generate_signals returns a DataFrame with signal.",
    ),
    (
        "agents/prompts/engineer_agent/AGENTS.md",
        "Engineer-specific operating rules override speculation: avoid undefined framework fields, preserve strategy intent, and keep code fully runnable.",
    ),
]

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


def load_bootstrap_context(agent_name: str) -> str:
    if agent_name != "engineer_agent":
        return ""

    lines = ["Bootstrap Files:"]
    for path, summary in ENGINEER_BOOTSTRAP_FILES:
        lines.append(f"- {path}: {summary}")
    lines.append(
        "- Runtime Note: the remote engineer model cannot directly use MCP tools; any external references must be supplied by the orchestrator as controlled context."
    )
    return "\n".join(lines)


EngineerPromptStyle = Literal["default", "openhands_inspired", "compact"]


def _build_default_engineer_sections(project_root: str | None = None) -> List[Tuple[str, str]]:
    return [
        (
            "Identity",
            "You are the engineer agent for this repository. Your job is to produce repo-native strategy code that passes local validation, not to brainstorm or narrate.",
        ),
        (
            "Operating Mode",
            "Act like a constrained repository engineer: follow the repo contract first, preserve strategy intent, and prefer the smallest viable implementation that passes validation.",
        ),
        ("Repo Rules", load_repo_rules(project_root=project_root)),
        ("Agent Rules", load_agent_instructions("engineer_agent")),
        ("Tool Capabilities", SHARED_TOOL_CAPABILITIES.strip()),
        ("Workflow Hints", AGENT_TOOL_HINTS.get("engineer_agent", "").strip()),
        ("Bootstrap Files", load_bootstrap_context("engineer_agent")),
        (
            "Output Discipline",
            "Return only the requested structured sections. Do not add markdown fences, explanations, or alternative implementations outside the required format.",
        ),
    ]


def _build_openhands_inspired_engineer_sections(project_root: str | None = None) -> List[Tuple[str, str]]:
    return [
        (
            "Identity",
            "You are a cautious Python quant-strategy engineer. Your job is to return a complete, runnable, repo-native strategy implementation that can survive validation, not a partial draft.",
        ),
        (
            "Operating Mode",
            "Work like a disciplined coding agent: first reconcile the repo contract, then mentally plan the data flow and method boundaries, then emit one complete implementation. Never stop at a sketch, outline, or half-written class.",
        ),
        ("Repo Rules", load_repo_rules(project_root=project_root)),
        ("Agent Rules", load_agent_instructions("engineer_agent")),
        ("Tool Capabilities", SHARED_TOOL_CAPABILITIES.strip()),
        (
            "Workflow Hints",
            "\n".join(
                [
                    AGENT_TOOL_HINTS.get("engineer_agent", "").strip(),
                    "- Before emitting code, mentally check assumptions, edge cases, and repo invariants, but do not print that private reasoning.",
                    "- When strategy logic is simple, prefer a small deterministic implementation over an ambitious abstraction.",
                    "- A response is incorrect if the class, __init__, or generate_signals body is incomplete or truncated.",
                ]
            ).strip(),
        ),
        ("Bootstrap Files", load_bootstrap_context("engineer_agent")),
        (
            "Strategy Safety Checklist",
            "\n".join(
                [
                    "- Avoid look-ahead bias; only use information available at each row.",
                    "- Keep index / datetime alignment explicit.",
                    "- Handle NaN warmup rows safely.",
                    "- Respect fees, slippage, and boundary conditions when strategy logic depends on them.",
                    "- Do not invent framework helpers or config objects that this repo does not define.",
                ]
            ),
        ),
        (
            "Output Discipline",
            "\n".join(
                [
                    "Return only the requested structured sections.",
                    "Do not add markdown fences, explanations, or alternative implementations outside the required format.",
                    "Do not emit a section unless you can complete it.",
                    "Inside <CODE>, output one complete Python file from the first import to the final return statement.",
                ]
            ),
        ),
    ]


def _build_compact_engineer_sections(project_root: str | None = None) -> List[Tuple[str, str]]:
    return [
        (
            "Identity",
            "You are the engineer agent for this repository. Return one repo-valid strategy file, not analysis.",
        ),
        ("Repo Rules", load_repo_rules(project_root=project_root)),
        (
            "Contract",
            "\n".join(
                [
                    "- Inherit BaseStrategy from strategies/base.py.",
                    "- Implement generate_signals(self, data: pd.DataFrame) -> pd.DataFrame.",
                    "- Return a DataFrame with at least datetime and signal.",
                    "- Do not use self.config, self.params, or non-repo framework helpers.",
                    "- Do not import pandas_ta, ta-lib, backtrader, or vectorbt.",
                ]
            ),
        ),
        (
            "Output Discipline",
            "\n".join(
                [
                    "Return exactly <SUMMARY>, <ASSUMPTIONS>, and <CODE>.",
                    "Inside <CODE>, output one complete Python file.",
                    "Do not output markdown fences or extra explanation.",
                ]
            ),
        ),
    ]


def build_engineer_system_prompt(
    project_root: str | None = None,
    style: EngineerPromptStyle = "default",
) -> str:
    if style == "openhands_inspired":
        sections = _build_openhands_inspired_engineer_sections(project_root=project_root)
    elif style == "compact":
        sections = _build_compact_engineer_sections(project_root=project_root)
    else:
        sections = _build_default_engineer_sections(project_root=project_root)

    rendered = []
    for title, content in sections:
        if not content:
            continue
        rendered.append(f"## {title}\n{content}")
    return "\n\n".join(rendered).strip()


def build_agent_context(agent_name: str, project_root: str | None = None) -> str:
    sections: Dict[str, str] = {
        "Repo Rules": load_repo_rules(project_root=project_root),
        "Agent Rules": load_agent_instructions(agent_name),
        "Tool Capabilities": SHARED_TOOL_CAPABILITIES.strip(),
        "Workflow Hints": AGENT_TOOL_HINTS.get(agent_name, "").strip(),
        "Bootstrap Files": load_bootstrap_context(agent_name),
    }
    rendered = []
    for title, content in sections.items():
        if not content:
            continue
        rendered.append(f"## {title}\n{content}")
    return "\n\n".join(rendered).strip()
