# Agent Governance Template

This template captures the operating pattern that makes coding agents more reliable across repositories.

Use it when you want better planning discipline, lower regression risk, and more consistent multi-agent collaboration.

## Core Principle

High-quality agent output usually comes less from a stronger model and more from better context governance:

- explicit repository rules
- role-specific agent rules
- stable handoff artifacts
- validation and testing discipline
- clear boundaries between orchestration tools and remote LLMs

## Layer 1: Repository-Level `AGENTS.md`

Create one repo-level `AGENTS.md` that acts as the shared constitution.

It should define:

- mission and operating model
- human-in-the-loop rules
- canonical artifacts and audit trail
- engineering guardrails
- validation and test expectations
- data and metrics discipline
- prompt/tooling model

Recommended structure:

```md
# <Repo Name> Repository Rules

## Mission
...

## Global Workflow Rules
- ...

## Canonical Artifacts
- ...

## Engineering Guardrails
- ...

## Validation And Testing
- ...

## Data And Metrics Discipline
- ...

## Prompting And Tooling Model
- ...
```

## Layer 2: Agent-Specific `AGENTS.md`

Give each agent its own local rules file.

Recommended layout:

```text
agents/prompts/
  strategy_agent/AGENTS.md
  engineer_agent/AGENTS.md
  backtest_agent/AGENTS.md
  evaluator_agent/AGENTS.md
  reporter_agent/AGENTS.md
```

Each agent file should define:

- role
- primary inputs
- required behavior
- forbidden behavior
- success criteria

Example shape:

```md
# Engineer Agent Rules

## Role
You implement and revise strategy code with the smallest viable code change.

## Inputs
- strategy spec
- repo constraints
- validation failures
- human guidance

## Required Behavior
- produce complete executable code
- preserve strategy intent
- use approved dependencies only

## Forbidden Behavior
- do not emit fragments or TODO placeholders
- do not invent unsupported libraries
- do not claim success without validation
```

## Layer 3: Prompt Context Loader

Do not assume remote LLM calls can see local files or tools.

Use a context loader that assembles:

- repo-level rules
- agent-specific rules
- shared tool capability notes
- optional agent-specific workflow hints

Recommended logic:

```python
def build_agent_context(agent_name: str) -> str:
    return combine(
        load_repo_rules(),
        load_agent_rules(agent_name),
        load_tool_capabilities(),
        load_agent_workflow_hints(agent_name),
    )
```

## Layer 4: Canonical Handoff Artifacts

Keep multi-agent loops grounded in stable files, not only chat history.

For research and strategy workflows, define canonical artifacts such as:

- `strategy_spec.md`
- `implementation_note.md`
- `backtest_report.md`
- `backtest_report.json`
- `iteration_log.md`

Rules:

- each meaningful iteration updates artifacts
- failed runs are recorded
- human decisions are recorded
- reports are evidence-backed, not aspirational

## Layer 5: Tooling Model

Keep this distinction explicit:

- `AGENTS.md`: what the agent should do
- `Skills`: reusable workflow patterns and heuristics
- `MCP`: tools and external context access

This prevents a common mistake: assuming a remote LLM automatically has the same capabilities as the local orchestrator.

Recommended wording:

```md
- MCP and Skills are available to the local orchestrator, not directly to the remote LLM.
- Remote LLM agents are constrained by supplied context unless the orchestration layer explicitly executes tools for them.
```

## Layer 6: Validation Strategy

Agent quality improves when "success" is defined operationally.

Typical guardrails:

- syntax validation
- structural validation
- smoke test or smoke backtest
- canonical artifact write
- unit tests for prompt/context plumbing
- full test suite before closing substantial changes

## Anti-Patterns

Avoid these:

- one giant prompt for every agent
- mixing historical status notes with operational rules in the same `AGENTS.md`
- letting remote LLMs invent dependencies or architecture
- claiming improvements without fresh backtests
- treating console output as the audit trail
- skipping tests because "this is only prompt work"

## Adoption Checklist

Use this checklist when bringing the pattern into a new repo:

1. Create a repo-level `AGENTS.md` with operational rules only.
2. Create per-agent `AGENTS.md` files for each workflow role.
3. Implement a prompt/context loader.
4. Define canonical handoff artifacts.
5. Add unit tests for prompt loading and context inclusion.
6. Add deterministic smoke tests for the core workflow.
7. Keep runtime artifacts out of commits unless explicitly intended.

## Why This Works

This pattern improves outcomes because it reduces ambiguity in four places:

- what the system is trying to optimize
- what each agent is allowed to do
- what counts as evidence
- what must be validated before claiming completion

In practice, this often improves reliability more than switching to a slightly stronger model.
