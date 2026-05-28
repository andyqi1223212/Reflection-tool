#!/usr/bin/env python3
"""Validate data/chains.json items against data/inquiry-chain.schema.json (draft-07)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    schema_path = ROOT / "data" / "inquiry-chain.schema.json"
    data_path = ROOT / "data" / "chains.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(data_path.read_text(encoding="utf-8"))
    chains = data.get("chains")
    if not isinstance(chains, list):
        print("chains.json missing .chains array", file=sys.stderr)
        sys.exit(1)

    v = Draft7Validator(schema)
    errors = False
    for item in chains:
        errs = sorted(v.iter_errors(item), key=lambda e: e.path)
        if errs:
            errors = True
            print(f"\n=== {item.get('id', '?')} ===", file=sys.stderr)
            for e in errs:
                print(f"  {'/'.join(str(p) for p in e.path)}: {e.message}", file=sys.stderr)

    if errors:
        sys.exit(1)
    print(f"OK: {len(chains)} chains validated against draft-07 schema.", file=sys.stderr)
    for item in chains:
        ups = item.get("updates")
        if isinstance(ups, list) and len(ups) > 0:
            print(
                f"[info] {item.get('id', '?')}: {len(ups)} 条 update 历史（append-only）",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
