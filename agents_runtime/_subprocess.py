"""subprocess 薄壳：round2/route_helper.py 与 round2/run_pipeline.py merge。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_route_helper_json(
    repo_root: Path,
    question_md: str,
    *,
    python_exe: str | None = None,
) -> tuple[dict[str, Any], str]:
    """stdout JSON + stderr 全文（供 debug）。"""
    py = python_exe or sys.executable
    script = repo_root / "round2" / "route_helper.py"
    r = subprocess.run(
        [
            py,
            str(script),
            "--question",
            question_md,
            "--include-raw-answer-excerpt",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"route_helper failed exit={r.returncode} stderr_tail={r.stderr[-2000:]!r}"
        )
    return json.loads(r.stdout), r.stderr


def run_merge(
    repo_root: Path,
    b_json: Path,
    judge_json: Path,
    *,
    mode_update: bool = False,
    mode_meta: bool = False,
    python_exe: str | None = None,
) -> subprocess.CompletedProcess[str]:
    py = python_exe or sys.executable
    cmd: list[str] = [
        py,
        str(repo_root / "round2" / "run_pipeline.py"),
        "merge",
        "--b",
        str(b_json),
        "--judge",
        str(judge_json),
    ]
    if mode_meta:
        cmd.extend(["--mode", "meta"])
    elif mode_update:
        cmd.extend(["--mode", "update"])
    return subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)


def interpret_merge_exit(
    code: int, stderr: str, stdout: str, cmd: list[str]
) -> dict[str, Any]:
    """与 phase2-orchestrator §5.5 表对齐；未知码按 export_fail。"""
    table: dict[int, tuple[str, str | None]] = {
        0: ("succeeded", None),
        1: (
            "schema_fail",
            "B 输出不符 schema 或 update_entry 子 schema 失败；回 B 改 prompt 或重跑",
        ),
        2: (
            "judge_not_pass",
            "merge 闸门拒绝；orchestrator 不该走到这里——排查 verdict 闸门",
        ),
        4: (
            "md_collision",
            "v3 md 已含同 IC id；确认是否漏跑下一 id 或者已经入库过",
        ),
        5: (
            "anchor_missing",
            "v3 md 缺锚点 ## 3. 这版给产品的启发；需人工恢复",
        ),
        6: (
            "update_target_missing",
            "v3 md 中找不到 target_ic_id 或缺末尾分隔；确认 target_ic_id 与 ### 标题一致",
        ),
        7: (
            "update_entry_schema_fail",
            "update_entry 子 schema 校验失败；回 B 改 prompt",
        ),
        8: (
            "meta_child_missing",
            "meta_relation.child_ic_ids 中有 id 不在 chains.json；核对 A/B 或库内卡",
        ),
    }
    status, next_action = table.get(
        code,
        (
            "export_fail",
            f"export/validate 或其它失败 exit={code}；查 stderr/stdout；可能需人工 revert md",
        ),
    )
    return {
        "status": status,
        "exit_code": code,
        "stderr_excerpt": stderr[-2000:],
        "stdout_excerpt": stdout[-2000:],
        "cmd": cmd,
        "next_action": next_action,
    }
