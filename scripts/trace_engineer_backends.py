#!/usr/bin/env python3
"""Run the real engineer workflow against multiple backends and capture trace metadata."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.strategy_developer_agent import StrategyDeveloperAgent
from scripts.run_engineer_prompt_probe import analyze_probe_output, build_probe_specs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace engineer workflow across backends")
    parser.add_argument(
        "--spec",
        choices=sorted(build_probe_specs().keys()),
        default="simple_ma",
        help="Preset strategy spec to trace.",
    )
    parser.add_argument(
        "--backend",
        action="append",
        choices=["openai_compatible", "google_genai", "third_party_mcp_stdio"],
        help="Specific backend(s) to run. Defaults to all.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path for JSON report.",
    )
    parser.add_argument(
        "--style",
        choices=["default", "compact", "openhands_inspired"],
        default="default",
        help="Engineer system prompt style.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2000,
        help="Engineer max tokens passed to the backend.",
    )
    return parser.parse_args()


def default_output_path(spec_name: str, style: str, max_tokens: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("reports/engineer_backend_trace") / f"{stamp}_{spec_name}_{style}_{max_tokens}.json"


def build_trace_report(spec_name: str, style: str, max_tokens: int, results: list[dict]) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_name": spec_name,
        "style": style,
        "max_tokens": max_tokens,
        "results": results,
    }


def run_trace(spec_name: str, backends: list[str], style: str, max_tokens: int) -> list[dict]:
    spec = build_probe_specs()[spec_name]
    results: list[dict] = []
    for backend_name in backends:
        agent = StrategyDeveloperAgent(
            engineer_backend=backend_name,
            engineer_system_prompt_style=style,
            engineer_max_tokens=max_tokens,
        )
        result = agent.generate_strategy_code_structured(spec)
        analysis = analyze_probe_output(result.code, parse_error=None)
        results.append(
            {
                "backend_name": backend_name,
                "success": analysis["success"],
                "issues": analysis["issues"],
                "syntax_ok": analysis["syntax_ok"],
                "code_line_count": analysis["code_line_count"],
                "first_line": analysis["first_line"],
                "raw_response": result.raw_response,
                "backend_result_name": result.backend_name,
                "request_metadata": result.request_metadata,
                "response_metadata": result.response_metadata,
                "summary": result.summary,
                "assumptions": result.assumptions,
                "code": result.code,
            }
        )
    return results


def main() -> int:
    args = parse_args()
    backends = args.backend or ["openai_compatible", "google_genai", "third_party_mcp_stdio"]
    report = build_trace_report(
        args.spec,
        args.style,
        args.max_tokens,
        run_trace(args.spec, backends, args.style, args.max_tokens),
    )
    output_path = Path(args.output) if args.output else default_output_path(args.spec, args.style, args.max_tokens)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for item in report["results"]:
        status = "PASS" if item["success"] else "FAIL"
        issues = "; ".join(item["issues"]) if item["issues"] else "none"
        print(
            f"{item['backend_name']}: {status} | syntax_ok={item['syntax_ok']} | "
            f"code_lines={item['code_line_count']} | issues={issues}"
        )
    print(f"saved_report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
