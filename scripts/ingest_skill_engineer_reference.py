#!/usr/bin/env python3
"""Ingest a local SKILL.md summary into research/engineer_reference_cache.json."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_contracts import ResearchArtifactWriter


def extract_skill_summary(skill_path: Path, max_chars: int = 1200) -> str:
    content = skill_path.read_text(encoding="utf-8").strip()
    lines = [line.rstrip() for line in content.splitlines()]
    in_frontmatter = False
    cleaned = []
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        cleaned.append(line)
    filtered = [line for line in cleaned if line]
    summary = " ".join(filtered)
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3] + "..."


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a local SKILL.md as an engineer reference.")
    parser.add_argument("skill_path", help="Path to the SKILL.md file")
    parser.add_argument("--name", default="", help="Override reference name")
    parser.add_argument("--tag", action="append", dest="tags", default=[], help="Tag used for matching")
    parser.add_argument("--pattern", action="append", dest="patterns", default=[], help="Pattern or family name")
    parser.add_argument("--constraint", action="append", dest="constraints", default=[], help="Implementation constraint")
    parser.add_argument(
        "--research-dir",
        default=str(PROJECT_ROOT / "research"),
        help="Research artifact directory",
    )
    args = parser.parse_args()

    skill_path = Path(args.skill_path).resolve()
    summary = extract_skill_summary(skill_path)
    writer = ResearchArtifactWriter(args.research_dir)
    writer.ensure_workspace()
    path = writer.append_engineer_reference(
        {
            "name": args.name or skill_path.parent.name,
            "source_type": "skill",
            "skill_path": str(skill_path),
            "summary": summary,
            "tags": args.tags,
            "patterns": args.patterns,
            "constraints": args.constraints,
        }
    )
    print(path)


if __name__ == "__main__":
    main()
