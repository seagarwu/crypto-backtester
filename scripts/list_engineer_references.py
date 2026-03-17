#!/usr/bin/env python3
"""List curated engineer references from research/engineer_reference_cache.json."""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    cache_path = PROJECT_ROOT / "research" / "engineer_reference_cache.json"
    if not cache_path.exists():
        print(f"missing: {cache_path}")
        return
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"invalid json: {cache_path}")
        sys.exit(1)
    for idx, item in enumerate(payload, start=1):
        print(
            f"{idx}. {item.get('name', 'unnamed')} | "
            f"{item.get('source_type', 'unknown')} | "
            f"tags={','.join(item.get('tags', []) or [])}"
        )


if __name__ == "__main__":
    main()
