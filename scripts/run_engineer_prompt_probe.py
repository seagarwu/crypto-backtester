#!/usr/bin/env python3
"""
Run prompt-focused A/B probes for the engineer agent on simple strategy specs.

Examples:
    python scripts/run_engineer_prompt_probe.py --spec simple_ma
    python scripts/run_engineer_prompt_probe.py --spec simple_rsi_macd --variant structured_system
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_agent_prompting = _load_module("_engineer_probe_agent_prompting", "agents/agent_prompting.py")
_strategy_developer = _load_module("_engineer_probe_strategy_developer", "agents/strategy_developer_agent.py")

build_engineer_system_prompt = _agent_prompting.build_engineer_system_prompt
StrategyDeveloperAgent = _strategy_developer.StrategyDeveloperAgent
StrategySpec = _strategy_developer.StrategySpec


PROBE_VARIANTS = (
    "legacy_inline",
    "structured_user_only",
    "structured_system",
    "structured_system_openhands",
)


def build_probe_specs() -> Dict[str, StrategySpec]:
    return {
        "simple_ma": StrategySpec(
            name="Simple MA Cross",
            description="Long-only moving average crossover strategy for BTCUSDT.",
            indicators=["SMA_20", "SMA_50"],
            entry_rules="Buy when SMA20 crosses above SMA50.",
            exit_rules="Exit when SMA20 crosses below SMA50.",
            parameters={"fast_period": 20, "slow_period": 50},
            timeframe="1h",
            risk_level="medium",
        ),
        "simple_rsi_macd": StrategySpec(
            name="Simple RSI MACD",
            description="Long-only RSI plus MACD confirmation strategy for BTCUSDT.",
            indicators=["RSI_14", "MACD_12_26_9"],
            entry_rules="Buy when RSI recovers above 30 and MACD line crosses above signal.",
            exit_rules="Exit when RSI exceeds 70 or MACD line crosses below signal.",
            parameters={"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
            timeframe="1h",
            risk_level="medium",
        ),
    }


def _parse_structured_result(agent: StrategyDeveloperAgent, raw: str) -> tuple[str, Optional[str]]:
    try:
        parsed = agent._parse_structured_response(raw)
        code = agent._normalize_structured_code(str(parsed.get("code", "")))
        if code:
            return code, None
        return "", "Structured response parsed but code block was empty"
    except Exception as exc:
        return "", str(exc)


def _parse_legacy_result(agent: StrategyDeveloperAgent, raw: str) -> tuple[str, Optional[str]]:
    code = agent._clean_code_block(raw)
    if code:
        return code, None
    return "", "No code extracted from legacy response"


def _check_generate_signals_contract(code: str) -> list[str]:
    if not code.strip():
        return []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    issues: list[str] = []
    strategy_class = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            base_names = {
                base.id
                for base in node.bases
                if isinstance(base, ast.Name)
            }
            if "BaseStrategy" in base_names:
                strategy_class = node
                break

    if strategy_class is None:
        return issues

    methods = {
        node.name: node
        for node in strategy_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    generate_signals = methods.get("generate_signals")
    if generate_signals is None:
        return issues

    has_return = any(isinstance(node, ast.Return) for node in ast.walk(generate_signals))
    if not has_return:
        issues.append("generate_signals has no return statement")

    if "signal" not in code:
        issues.append("Missing signal column handling")

    return issues


def analyze_probe_output(code: str, parse_error: Optional[str]) -> Dict[str, Any]:
    issues = []
    first_line = code.splitlines()[0].strip() if code.strip() else ""
    if parse_error:
        issues.append(parse_error)
    if not code.strip():
        issues.append("No code generated")
    if code and not first_line.startswith(("import ", "from ")):
        issues.append("First line is not import/from")
    if code and "BaseStrategy" not in code:
        issues.append("Missing BaseStrategy reference")
    if code and "generate_signals" not in code:
        issues.append("Missing generate_signals implementation")

    syntax_ok = False
    if code.strip():
        try:
            ast.parse(code)
            syntax_ok = True
        except SyntaxError as exc:
            issues.append(f"Syntax error: {exc.msg}")

    if syntax_ok:
        issues.extend(_check_generate_signals_contract(code))

    return {
        "success": not issues,
        "issues": issues,
        "syntax_ok": syntax_ok,
        "first_line": first_line,
        "code_line_count": len(code.splitlines()) if code else 0,
        "contains_base_strategy": "BaseStrategy" in code if code else False,
        "contains_generate_signals": "generate_signals" in code if code else False,
    }


def run_probe_variant(
    agent: StrategyDeveloperAgent,
    spec: StrategySpec,
    variant: str,
    md_context: str = "",
    llm: Any = None,
) -> Dict[str, Any]:
    if variant not in PROBE_VARIANTS:
        raise ValueError(f"Unknown probe variant: {variant}")

    llm = llm or agent._get_llm()
    context = agent._extract_strategy_context(md_context)
    system_prompt = build_engineer_system_prompt()

    if variant == "legacy_inline":
        prompt = agent._build_legacy_code_prompt(spec=spec, context=context)
        response = llm.invoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        code, parse_error = _parse_legacy_result(agent, raw)
        prompt_mode = "single_prompt"
    else:
        prompt = agent._build_structured_code_prompt(
            spec=spec,
            context=context,
            feedback_text="{}",
            previous_code="",
        )
        if variant == "structured_system":
            response = agent._invoke_engineer_llm(llm, system_prompt, prompt)
            prompt_mode = "system_plus_human"
        elif variant == "structured_system_openhands":
            response = agent._invoke_engineer_llm(
                llm,
                build_engineer_system_prompt(style="openhands_inspired"),
                prompt,
            )
            prompt_mode = "system_plus_human_openhands"
        else:
            response = llm.invoke(prompt)
            prompt_mode = "single_prompt"
        raw = response.content if hasattr(response, "content") else str(response)
        code, parse_error = _parse_structured_result(agent, raw)

    analysis = analyze_probe_output(code, parse_error=parse_error)
    return {
        "variant": variant,
        "prompt_mode": prompt_mode,
        "success": analysis["success"],
        "issues": analysis["issues"],
        "syntax_ok": analysis["syntax_ok"],
        "first_line": analysis["first_line"],
        "code_line_count": analysis["code_line_count"],
        "contains_base_strategy": analysis["contains_base_strategy"],
        "contains_generate_signals": analysis["contains_generate_signals"],
        "raw_response": raw,
        "code": code,
    }


def build_probe_report(
    spec_name: str,
    model: str,
    results: list[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_name": spec_name,
        "model": model,
        "results": results,
        "summary": {
            "total_variants": len(results),
            "successful_variants": [item["variant"] for item in results if item["success"]],
            "failed_variants": [item["variant"] for item in results if not item["success"]],
        },
    }


def default_output_path(spec_name: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("reports/engineer_prompt_probe") / f"{stamp}_{spec_name}.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run engineer prompt A/B probes")
    parser.add_argument(
        "--spec",
        choices=sorted(build_probe_specs().keys()),
        default="simple_ma",
        help="Preset strategy spec to probe.",
    )
    parser.add_argument(
        "--variant",
        action="append",
        choices=PROBE_VARIANTS,
        help="Specific variant(s) to run. Defaults to all variants.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("ENGINEER_MODEL", "gemini-2.5-pro"),
        help="Engineer model name.",
    )
    parser.add_argument(
        "--md-context-file",
        help="Optional markdown context file passed into the probe.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path. Defaults under reports/engineer_prompt_probe/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    specs = build_probe_specs()
    spec = specs[args.spec]
    variants = args.variant or list(PROBE_VARIANTS)
    md_context = ""
    if args.md_context_file:
        md_context = Path(args.md_context_file).read_text(encoding="utf-8")

    agent = StrategyDeveloperAgent(model=args.model)
    results = [
        run_probe_variant(agent=agent, spec=spec, variant=variant, md_context=md_context)
        for variant in variants
    ]
    report = build_probe_report(spec_name=args.spec, model=args.model, results=results)

    output_path = Path(args.output) if args.output else default_output_path(args.spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for item in results:
        status = "PASS" if item["success"] else "FAIL"
        issue_text = "; ".join(item["issues"]) if item["issues"] else "none"
        print(f"{item['variant']}: {status} | syntax_ok={item['syntax_ok']} | issues={issue_text}")
    print(f"saved_report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
