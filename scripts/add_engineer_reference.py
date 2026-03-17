#!/usr/bin/env python3
"""Append a curated engineer reference summary into research/engineer_reference_cache.json."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_contracts import ResearchArtifactWriter


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a curated engineer reference entry.")
    parser.add_argument("--name", required=True, help="Human-readable reference name")
    parser.add_argument("--source-type", required=True, help="Reference source type, e.g. github, paper, manual")
    parser.add_argument("--summary", required=True, help="Short summary of what to borrow or avoid")
    parser.add_argument("--url", default="", help="Optional source URL")
    parser.add_argument("--tag", action="append", dest="tags", default=[], help="Tag used for matching indicators/families")
    parser.add_argument("--pattern", action="append", dest="patterns", default=[], help="Pattern or family name")
    parser.add_argument("--constraint", action="append", dest="constraints", default=[], help="Implementation constraint to preserve")
    parser.add_argument(
        "--research-dir",
        default=str(PROJECT_ROOT / "research"),
        help="Research artifact directory",
    )
    args = parser.parse_args()

    writer = ResearchArtifactWriter(args.research_dir)
    writer.ensure_workspace()
    path = writer.append_engineer_reference(
        {
            "name": args.name,
            "source_type": args.source_type,
            "url": args.url,
            "summary": args.summary,
            "tags": args.tags,
            "patterns": args.patterns,
            "constraints": args.constraints,
        }
    )
    print(path)


if __name__ == "__main__":
    main()
