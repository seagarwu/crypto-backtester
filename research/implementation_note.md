# Implementation Note

- Strategy ID: c71ff178-843d-4aa1-a55c-78be100edf57
- Iteration ID: 0ac6136b-d694-4973-88f7-8185fd61b7c2
- Iteration: 1
- Strategy: BTCUSDT_BBand_Reversion
- Files changed: reports/test_engineer_retry/iterations/iteration_01_attempt_03_BTCUSDT_BBand_Reversion.py
- Strategy behaviors implemented: attempt 3
- Assumptions: none
- Known gaps: Syntax error: invalid syntax
- Reference inputs used: multi_timeframe_bband_reversion, single_timeframe_bband_reversion
- Validation performed: failed

## Smoke Metrics
- None

## Engineer Backend Decision

- Decision date: 2026-03-18
- Decision: set the engineer workflow default backend to `third_party_mcp_stdio`
- Reason:
  - repeated workflow-level traces showed `third_party_mcp_stdio` was materially more reliable than both `openai_compatible` and `google_genai`
  - on the same `gemini-2.5-pro` model, MCP repeatedly returned complete repo-valid strategy code while the other paths often returned empty, truncated, or fallback-only output
- Evidence:
  - `reports/engineer_backend_trace/20260318_185521_simple_ma.json`
  - `reports/engineer_backend_trace/20260318_185520_simple_rsi_macd.json`
  - `reports/gemini_backend_compare/20260318_152618_simple_ma_default.json`
  - `reports/gemini_backend_compare/20260318_152637_simple_rsi_macd_default.json`
- Implementation changes:
  - `agents/engineer_backends.py`
  - `agents/strategy_developer_agent.py`
  - `agents/strategy_rd_workflow.py`
  - `agents/conversation.py`
- Remaining risk:
  - root cause is not fully closed yet; MCP is now the operational default because it is the most reliable measured path, not because the native Gemini paths have been fully explained
