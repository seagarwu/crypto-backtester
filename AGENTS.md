# Crypto Backtester Repository Rules

## Mission

This repository implements a human-in-the-loop multi-agent workflow for crypto strategy research, code generation, backtesting, evaluation, and reporting.

The workflow must favor reproducibility over speed and explicit evidence over optimistic claims.

## Global Workflow Rules

- Keep the human as the final decision-maker for `accept`, `continue`, `revise`, `pivot`, or `stop`.
- Treat strategy ideation, engineering, backtesting, evaluation, and reporting as separate responsibilities.
- Preserve strategy intent across iterations unless the human or strategy spec explicitly changes direction.
- Prefer deterministic templates and validated repo patterns over speculative free-form code generation.
- Never claim a strategy is improved without a fresh backtest tied to the current code and configuration.

## Canonical Research Artifacts

The following files are the canonical handoff surface for the strategy R&D loop:

- `research/strategy_spec.md`
- `research/implementation_note.md`
- `research/backtest_report.md`
- `research/backtest_report.json`
- `research/iteration_log.md`

Rules:

- Every meaningful iteration must update the canonical artifacts.
- Failed runs must still be recorded with the failure reason.
- Human checkpoint decisions and config overrides must be captured in the iteration history.
- Do not present ad-hoc console output as a substitute for the canonical artifacts.

## Engineering Guardrails

- Keep changes small, reviewable, and aligned with the current strategy spec.
- Preserve existing invariants unless the task explicitly requires changing them.
- Prefer repo-local modules and existing strategy base classes.
- Use only approved dependencies already declared by the repository unless the human explicitly authorizes a new one.
- Generated strategy code must be complete and executable, not fragments or pseudocode.

## Validation And Testing

- New or revised strategy code must pass syntax checks and smoke validation before being treated as usable.
- Backtest claims must come from an actual run, not reasoning alone.
- When modifying workflow, contracts, or prompt loading, add or update unit tests.
- Before closing substantial work, run the relevant test suite; if full-suite validation is possible, prefer it.

## Data And Metrics Discipline

- Record the dataset, symbol, timeframe, and date window used for a backtest.
- Treat negative return, excessive drawdown, low trade count, and overfitting risk as first-class concerns.
- Do not hide in-sample weakness behind one good metric.
- If the human overrides timeframe, symbol, or date window, subsequent iterations must respect that override.

## Prompting And Tooling Model

- The local orchestrator may read repository files, `AGENTS.md`, and skill guidance, then inject distilled context into remote LLM prompts.
- Remote LLM agents should be treated as text generators constrained by supplied context, not as agents with direct tool access.
- MCP and Skills are orchestration-side capabilities. They improve context quality and workflow discipline but are not implicitly available inside every remote LLM call.

## Current Focus

- Keep the Engineer-driven strategy loop stable.
- Reduce malformed code generation and improve recovery from failed iterations.
- Maintain deterministic smoke tests for the workflow and artifact contracts.
