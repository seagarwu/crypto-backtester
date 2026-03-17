#!/usr/bin/env python3
"""Initialize a local deep-research run directory for strategy exploration."""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestration_bootstrap import init_deep_research_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize .research run workspace")
    parser.add_argument("topic")
    parser.add_argument("question")
    parser.add_argument("--dimension", action="append", default=[], help="Research dimension")
    args = parser.parse_args()

    paths = init_deep_research_run(
        project_root=str(PROJECT_ROOT),
        topic=args.topic,
        question=args.question,
        dimensions=args.dimension,
    )
    print(paths.root)


if __name__ == "__main__":
    main()
