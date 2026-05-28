#!/usr/bin/env python3
"""可选：在拿到 run_a 的 JSON 文件后，与黄金 A 对比 axis / patterns（集合）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        print("用法: compare_a_ball_trash.py <live_a.json> <golden_a.json>", file=sys.stderr)
        sys.exit(2)
    live = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    gold = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    for k in ("_meta",):
        live.pop(k, None)
        gold.pop(k, None)
    axis_ok = live.get("axis") == gold.get("axis")
    p_live = set(live.get("patterns") or [])
    p_gold = set(gold.get("patterns") or [])
    pat_ok = p_live == p_gold
    print("axis_match", axis_ok, "live", live.get("axis"), "gold", gold.get("axis"))
    print("patterns_set_match", pat_ok, "live", sorted(p_live), "gold", sorted(p_gold))
    if "route" in live and "route" in gold:
        print("route_match", live.get("route") == gold.get("route"))
    else:
        print("route_note", "一方缺 route 字段（黄金为 v1 时预期）", "live_has", "route" in live, "gold_has", "route" in gold)
    sys.exit(0 if axis_ok and pat_ok else 1)


if __name__ == "__main__":
    main()
