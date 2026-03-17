#!/usr/bin/env python3
"""Ingest a GitHub repository summary into research/engineer_reference_cache.json."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_contracts import ResearchArtifactWriter


DEFAULT_GITMCP_SCRIPT_CANDIDATES = [
    os.environ.get("GITMCP_SCRIPT", ""),
    "/media/nexcom/data/alan/codex-devpack/skills/codex-skills/skills/read-github/scripts/gitmcp.py",
]


def resolve_gitmcp_script(explicit_path: str = "") -> Path:
    candidates = [explicit_path, *DEFAULT_GITMCP_SCRIPT_CANDIDATES]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    raise FileNotFoundError("Unable to locate gitmcp.py. Pass --gitmcp-script or set GITMCP_SCRIPT.")


def run_gitmcp(script_path: Path, command: str, repo: str, query: str = "") -> str:
    cmd = [sys.executable, str(script_path), command, repo]
    if query:
        cmd.append(query)
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def condense_text(text: str, limit: int = 800) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a GitHub repo summary for engineer reference-guided synthesis.")
    parser.add_argument("repo", help="GitHub repo in owner/repo format or full URL")
    parser.add_argument("--query", default="", help="Optional code search query for relevant implementation patterns")
    parser.add_argument("--name", default="", help="Override human-readable reference name")
    parser.add_argument("--summary", default="", help="Manual summary prefix for what to borrow or avoid")
    parser.add_argument("--tag", action="append", dest="tags", default=[], help="Tag used for matching")
    parser.add_argument("--pattern", action="append", dest="patterns", default=[], help="Pattern or family name")
    parser.add_argument("--constraint", action="append", dest="constraints", default=[], help="Implementation constraint")
    parser.add_argument("--gitmcp-script", default="", help="Path to read-github skill gitmcp.py")
    parser.add_argument(
        "--research-dir",
        default=str(PROJECT_ROOT / "research"),
        help="Research artifact directory",
    )
    args = parser.parse_args()

    script_path = resolve_gitmcp_script(args.gitmcp_script)
    docs_excerpt = condense_text(run_gitmcp(script_path, "fetch-docs", args.repo))
    code_excerpt = condense_text(run_gitmcp(script_path, "search-code", args.repo, args.query)) if args.query else ""

    summary_parts = [part for part in [args.summary, docs_excerpt, code_excerpt] if part]
    writer = ResearchArtifactWriter(args.research_dir)
    writer.ensure_workspace()
    path = writer.append_engineer_reference(
        {
            "name": args.name or args.repo,
            "source_type": "github",
            "repo": args.repo,
            "query": args.query,
            "summary": "\n\n".join(summary_parts),
            "url": args.repo if args.repo.startswith("http") else f"https://github.com/{args.repo}",
            "tags": args.tags,
            "patterns": args.patterns,
            "constraints": args.constraints,
            "docs_excerpt": docs_excerpt,
            "code_excerpt": code_excerpt,
        }
    )
    print(path)


if __name__ == "__main__":
    main()
