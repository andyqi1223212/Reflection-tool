#!/usr/bin/env python3
"""
Round-2 trial: 扫描 data/chains.json 中最大 IC-NNN，打印下一个 id（如 IC-025）。

仓库正式版计划迁至 tools/next_ic_id.py；本脚本以 round2 为家，repo 根为 parents[1]。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

IC_RE = re.compile(r"^IC-(\d{3})$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def max_ic_suffix(chains_path: Path) -> int | None:
    if not chains_path.is_file():
        print(f"[debug] chains file missing: {chains_path}", file=sys.stderr)
        return None
    data = json.loads(chains_path.read_text(encoding="utf-8"))
    chains = data.get("chains")
    if not isinstance(chains, list):
        print("[debug] chains.json has no .chains list", file=sys.stderr)
        return None
    best: int | None = None
    for item in chains:
        cid = item.get("id")
        if not isinstance(cid, str):
            continue
        m = IC_RE.match(cid)
        if not m:
            print(f"[debug] skip non-standard id: {cid!r}", file=sys.stderr)
            continue
        n = int(m.group(1))
        best = n if best is None else max(best, n)
    return best


def next_ic_id_str(chains_path: Path) -> str:
    m = max_ic_suffix(chains_path)
    n = (m + 1) if m is not None else 1
    return f"IC-{n:03d}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Print next IC-NNN from data/chains.json max id + 1")
    ap.add_argument(
        "--chains",
        type=Path,
        default=None,
        help="Path to chains.json (default: <repo>/data/chains.json)",
    )
    args = ap.parse_args()
    root = repo_root()
    chains_path = args.chains if args.chains else root / "data" / "chains.json"
    nxt = next_ic_id_str(chains_path)
    print(nxt)


if __name__ == "__main__":
    main()
