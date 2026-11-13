#!/usr/bin/env python3
"""Strictly parse checked-in design/config JSON, rejecting duplicate keys and NaN."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_NAMES = {
    "study_config.json",
    "input_parameters.json",
    "lane_design.json",
    "spring_strip.json",
}


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def reject_nonstandard_constant(value):
    raise ValueError(f"non-standard JSON numeric constant: {value}")


def is_candidate(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if {"archive", "results", "reports"} & set(rel.parts):
        return False
    return path.name.endswith("_config.json") or path.name in CONFIG_NAMES


def main() -> int:
    files = sorted(path for path in ROOT.rglob("*.json") if is_candidate(path))
    if not files:
        print("ERROR: no configuration JSON files found", file=sys.stderr)
        return 1

    failures = []
    for path in files:
        try:
            with path.open(encoding="utf-8") as stream:
                json.load(
                    stream,
                    object_pairs_hook=reject_duplicate_keys,
                    parse_constant=reject_nonstandard_constant,
                )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            failures.append((path, exc))

    for path, exc in failures:
        print(f"FAIL {path.relative_to(ROOT)}: {exc}", file=sys.stderr)
    if failures:
        print(f"{len(failures)} of {len(files)} configuration files failed.", file=sys.stderr)
        return 1

    print(f"Validated {len(files)} configuration JSON files (UTF-8, unique keys, standard numbers).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
