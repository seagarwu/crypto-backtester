#!/usr/bin/env python3
"""Ingest an MCP-derived summary into research/engineer_reference_cache.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_contracts import ResearchArtifactWriter


def load_summary(summary: str, summary_file: str) -> str:
    if summary:
        return summary
    if summary_file:
        return Path(summary_file).read_text(encoding="utf-8").strip()
    raise ValueError("Provide either --summary or --summary-file")


def load_metadata(metadata_json: str) -> dict:
    if not metadata_json:
        return {}
    return dict(json.loads(metadata_json))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest an MCP-derived engineer reference summary.")
    parser.add_argument("--name", required=True, help="Human-readable reference name")
    parser.add_argument("--server", required=True, help="MCP server name")
    parser.add_argument("--resource-uri", default="", help="Optional MCP resource URI or endpoint description")
    parser.add_argument("--summary", default="", help="Inline summary text")
    parser.add_argument("--summary-file", default="", help="Path to a file containing the summary")
    parser.add_argument("--metadata-json", default="", help="Optional JSON metadata blob")
    parser.add_argument("--tag", action="append", dest="tags", default=[], help="Tag used for matching")
    parser.add_argument("--pattern", action="append", dest="patterns", default=[], help="Pattern or family name")
    parser.add_argument("--constraint", action="append", dest="constraints", default=[], help="Implementation constraint")
    parser.add_argument(
        "--research-dir",
        default=str(PROJECT_ROOT / "research"),
        help="Research artifact directory",
    )
    args = parser.parse_args()

    summary = load_summary(args.summary, args.summary_file)
    metadata = load_metadata(args.metadata_json)

    writer = ResearchArtifactWriter(args.research_dir)
    writer.ensure_workspace()
    path = writer.append_engineer_reference(
        {
            "name": args.name,
            "source_type": "mcp",
            "mcp_server": args.server,
            "resource_uri": args.resource_uri,
            "summary": summary,
            "metadata": metadata,
            "tags": args.tags,
            "patterns": args.patterns,
            "constraints": args.constraints,
        }
    )
    print(path)


if __name__ == "__main__":
    main()
