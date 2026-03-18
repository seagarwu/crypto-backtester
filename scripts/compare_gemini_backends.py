#!/usr/bin/env python3
"""
Compare engineer-code generation across Gemini backends using the same model/spec/prompt style.

Examples:
    python scripts/compare_gemini_backends.py --spec simple_ma
    python scripts/compare_gemini_backends.py --spec simple_rsi_macd --style openhands_inspired
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents.agent_prompting import build_engineer_system_prompt
from agents.strategy_developer_agent import StrategyDeveloperAgent
from scripts.run_engineer_prompt_probe import analyze_probe_output, build_probe_specs

try:
    genai = importlib.import_module("google.genai")
    types = importlib.import_module("google.genai.types")
except ImportError:
    genai = None
    types = None

try:
    mcp_module = importlib.import_module("mcp")
    mcp_stdio = importlib.import_module("mcp.client.stdio")
    ClientSession = getattr(mcp_module, "ClientSession")
    StdioServerParameters = getattr(mcp_module, "StdioServerParameters")
    stdio_client = getattr(mcp_stdio, "stdio_client")
except ImportError:
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Gemini backend outputs for engineer generation")
    parser.add_argument(
        "--spec",
        choices=sorted(build_probe_specs().keys()),
        default="simple_ma",
        help="Preset strategy spec to probe.",
    )
    parser.add_argument(
        "--style",
        choices=["default", "openhands_inspired"],
        default="default",
        help="Engineer system prompt style to test.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("ENGINEER_MODEL", "gemini-2.5-pro"),
        help="Gemini model to use for both backends.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip the third-party Gemini MCP backend.",
    )
    return parser.parse_args()


def _build_prompt(agent: StrategyDeveloperAgent, spec) -> tuple[str, str]:
    system_prompt = build_engineer_system_prompt(style="default")
    user_prompt = agent._build_structured_code_prompt(
        spec=spec,
        context="",
        feedback_text="{}",
        previous_code="",
    )
    return system_prompt, user_prompt


def _build_prompt_with_style(agent: StrategyDeveloperAgent, spec, style: str) -> tuple[str, str]:
    system_prompt = build_engineer_system_prompt(style=style)
    user_prompt = agent._build_structured_code_prompt(
        spec=spec,
        context="",
        feedback_text="{}",
        previous_code="",
    )
    return system_prompt, user_prompt


def _analyze_raw_response(agent: StrategyDeveloperAgent, raw: str) -> Dict[str, Any]:
    try:
        parsed = agent._parse_structured_response(raw)
        code = agent._normalize_structured_code(str(parsed.get("code", "")))
        parse_error = None
    except Exception as exc:
        code = ""
        parse_error = str(exc)

    analysis = analyze_probe_output(code, parse_error=parse_error)
    return {
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


def _invoke_current_backend(agent: StrategyDeveloperAgent, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    llm = agent._get_llm()
    response = agent._invoke_engineer_llm(llm, system_prompt, user_prompt)
    raw = response.content if hasattr(response, "content") else str(response)
    result = _analyze_raw_response(agent, raw)
    result["backend"] = "openai_compatible_adapter"
    return result


def _invoke_google_genai_backend(
    agent: StrategyDeveloperAgent,
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> Dict[str, Any]:
    if genai is None or types is None:
        raise RuntimeError("google-genai is not installed")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=agent.temperature,
            top_p=0.95,
            max_output_tokens=2000,
        ),
    )
    raw = getattr(response, "text", "") or ""
    result = _analyze_raw_response(agent, raw)
    result["backend"] = "google_genai_sdk"
    return result


async def _invoke_gemini_mcp_backend_async(
    agent: StrategyDeveloperAgent,
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> Dict[str, Any]:
    if ClientSession is None or StdioServerParameters is None or stdio_client is None:
        raise RuntimeError("mcp SDK is not installed")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    params = StdioServerParameters(
        command="npx",
        args=["-y", "github:aliargun/mcp-server-gemini"],
        env={"GEMINI_API_KEY": api_key},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "generate_text",
                arguments={
                    "prompt": user_prompt,
                    "model": model,
                    "systemInstruction": system_prompt,
                    "temperature": agent.temperature,
                    "maxTokens": 2000,
                    "topP": 0.95,
                },
            )
            raw = ""
            metadata = getattr(result, "metadata", None)
            if getattr(result, "content", None):
                first_item = result.content[0]
                raw = getattr(first_item, "text", "") or ""
            analysis = _analyze_raw_response(agent, raw)
            analysis["backend"] = "third_party_mcp_stdio"
            analysis["metadata"] = metadata
            return analysis


def _invoke_gemini_mcp_backend(
    agent: StrategyDeveloperAgent,
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> Dict[str, Any]:
    return asyncio.run(_invoke_gemini_mcp_backend_async(agent, system_prompt, user_prompt, model))


def default_output_path(spec_name: str, style: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("reports/gemini_backend_compare") / f"{stamp}_{spec_name}_{style}.json"


def build_report(spec_name: str, model: str, style: str, results: list[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_name": spec_name,
        "model": model,
        "style": style,
        "results": results,
    }


def main() -> int:
    args = _parse_args()
    agent = StrategyDeveloperAgent(model=args.model)
    spec = build_probe_specs()[args.spec]
    system_prompt, user_prompt = _build_prompt_with_style(agent, spec, args.style)

    results = [
        _invoke_current_backend(agent, system_prompt, user_prompt),
        _invoke_google_genai_backend(agent, system_prompt, user_prompt, model=args.model),
    ]
    if not args.skip_mcp:
        results.append(_invoke_gemini_mcp_backend(agent, system_prompt, user_prompt, model=args.model))

    report = build_report(spec_name=args.spec, model=args.model, style=args.style, results=results)
    output_path = Path(args.output) if args.output else default_output_path(args.spec, args.style)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for item in results:
        status = "PASS" if item["success"] else "FAIL"
        issue_text = "; ".join(item["issues"]) if item["issues"] else "none"
        print(
            f"{item['backend']}: {status} | syntax_ok={item['syntax_ok']} | "
            f"code_lines={item['code_line_count']} | issues={issue_text}"
        )
    print(f"saved_report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
