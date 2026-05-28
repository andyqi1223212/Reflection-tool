#!/usr/bin/env python3
"""兼容入口：请改用 tools/export_agentflow_context_chunks.py（含 A/B/Judge + crosscheck）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "tools" / "export_agentflow_context_chunks.py"


def main() -> None:
    print(
        "提示: export_pipeline_b_context_chunks.py 已合并为 export_agentflow_context_chunks.py",
        file=sys.stderr,
    )
    raise SystemExit(subprocess.call([sys.executable, str(NEW)], cwd=ROOT))


if __name__ == "__main__":
    main()
