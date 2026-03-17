#!/usr/bin/env python3
"""Initialize a local autonomous task directory for long-running strategy work."""

from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestration_bootstrap import init_autonomous_task


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize .autonomous task workspace")
    parser.add_argument("task_name")
    parser.add_argument("description")
    parser.add_argument("--goal", action="append", default=[], help="Additional task checklist item")
    args = parser.parse_args()

    paths = init_autonomous_task(
        project_root=str(PROJECT_ROOT),
        task_name=args.task_name,
        description=args.description,
        goals=args.goal,
    )
    print(paths.root)


if __name__ == "__main__":
    main()
