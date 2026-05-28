"""RunState 序列化与 resume 截断逻辑。"""

from __future__ import annotations

import json
from pathlib import Path

from agents_runtime.orchestrate import STAGE_ORDER, _delete_artifacts_from, _truncate_completed_for_resume
from agents_runtime.run_state import load_run, new_run_state, save_manifest


def test_manifest_roundtrip(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    st = new_run_state(runs, "2026-01-01_test_abc123", "外部source/x.md")
    st.completed_stages = ["route_helper", "a"]
    st.verdict = None
    save_manifest(st)
    st2 = load_run(runs, "2026-01-01_test_abc123")
    assert st2.question_md == "外部source/x.md"
    assert st2.completed_stages == ["route_helper", "a"]


def test_resume_from_truncates_and_deletes(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "rid"
    run_dir.mkdir(parents=True)
    for name in ("route_helper.json", "a.json", "b.json", "judge.json"):
        (run_dir / name).write_text("{}", encoding="utf-8")
    st = new_run_state(tmp_path / "runs", "rid", "q.md")
    st.run_dir = run_dir
    st.completed_stages = ["route_helper", "a", "b", "judge"]
    save_manifest(st)
    st = load_run(tmp_path / "runs", "rid")
    _truncate_completed_for_resume(st, "b")
    assert st.completed_stages == ["route_helper", "a"]
    _delete_artifacts_from(run_dir, "b")
    assert (run_dir / "route_helper.json").is_file()
    assert (run_dir / "a.json").is_file()
    assert not (run_dir / "b.json").is_file()
    assert not (run_dir / "judge.json").is_file()
    assert STAGE_ORDER.index("b") == 2
