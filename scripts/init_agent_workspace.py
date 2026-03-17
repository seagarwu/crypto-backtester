#!/usr/bin/env python3
"""Initialize canonical research workspace files for agent collaboration."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_contracts import ResearchArtifactWriter


def main() -> None:
    writer = ResearchArtifactWriter(str(PROJECT_ROOT / "research"))
    files = writer.ensure_workspace()
    for name, path in files.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
