"""orchestrator dry-run：mock LLM 与 merge / route_helper。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents_runtime.orchestrate import run_single_case


def test_pass_no_push_skips_merge(tmp_path: Path) -> None:
    rh = {"route_hint": "new", "candidates": []}
    a_out = {
        "route": "new",
        "axis": "attention",
        "patterns": ["P-EVAL"],
        "mechanism_sketch": "x",
    }
    b_out = {"output_kind": "full_card", "id": "IC-NEW", "title": "t"}
    j_out = {"verdict": "pass", "scores": {"mechanism": 5}}

    with (
        patch(
            "agents_runtime.orchestrate.run_route_helper_json",
            return_value=(rh, ""),
        ),
        patch("agents_runtime.agents.run_a", return_value=a_out),
        patch("agents_runtime.agents.run_b", return_value=b_out),
        patch("agents_runtime.agents.run_judge", return_value=j_out),
        patch("agents_runtime.orchestrate.run_merge") as m_merge,
    ):
        res = run_single_case(
            "外部source/球场垃圾话应对策略.md",
            no_push=True,
            runs_dir=tmp_path / "runs",
        )
    assert res["status"] == "succeeded"
    assert res["verdict"] == "pass"
    assert res["stages_completed"] == [
        "route_helper",
        "a",
        "b",
        "judge",
        "push",
    ]
    m_merge.assert_not_called()
    run_dir = Path(res["run_dir"])
    assert (run_dir / "manifest.json").is_file()
    man = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert man["push_result"]["status"] == "skipped"


def test_conditional_pass_awaiting_human(tmp_path: Path) -> None:
    rh: dict = {"route_hint": "new"}
    a_out = {"route": "new", "axis": "x", "patterns": [], "mechanism_sketch": "m"}
    b_out = {"output_kind": "full_card", "id": "IC-NEW", "title": "t"}
    j_out = {"verdict": "conditional_pass", "scores": {}}

    with (
        patch("agents_runtime.orchestrate.run_route_helper_json", return_value=(rh, "")),
        patch("agents_runtime.agents.run_a", return_value=a_out),
        patch("agents_runtime.agents.run_b", return_value=b_out),
        patch("agents_runtime.agents.run_judge", return_value=j_out),
    ):
        res = run_single_case(
            "外部source/x.md",
            runs_dir=tmp_path / "r2",
        )
    assert res["status"] == "awaiting_human"
    assert "push" in res["stages_completed"]


def test_merge_called_on_pass(tmp_path: Path) -> None:
    rh: dict = {}
    a_out = {"route": "new", "axis": "x", "patterns": [], "mechanism_sketch": "m"}
    b_out = {"output_kind": "full_card", "id": "IC-NEW", "title": "t"}
    j_out = {"verdict": "pass", "scores": {}}
    proc = MagicMock()
    proc.returncode = 0
    proc.stderr = ""
    proc.stdout = "✓ 新卡已入库: IC-099\n  UI: file:///tmp/proto/index.html\n"
    proc.args = ["py", "merge"]

    with (
        patch("agents_runtime.orchestrate.run_route_helper_json", return_value=(rh, "")),
        patch("agents_runtime.agents.run_a", return_value=a_out),
        patch("agents_runtime.agents.run_b", return_value=b_out),
        patch("agents_runtime.agents.run_judge", return_value=j_out),
        patch("agents_runtime.orchestrate.run_merge", return_value=proc),
    ):
        res = run_single_case("外部source/x.md", runs_dir=tmp_path / "r3")

    assert res["status"] == "succeeded"
    assert res["ui_line"] is not None
    assert "file://" in res["ui_line"]


def test_meta_card_merge_called_with_mode_meta(tmp_path: Path) -> None:
    rh: dict = {}
    a_out = {"route": "meta", "axis": "attention", "patterns": ["P-EFF"], "mechanism_sketch": "m"}
    b_out = {
        "output_kind": "meta_card",
        "id": "IC-NEW",
        "title": "t",
        "meta_relation": {"child_ic_ids": ["IC-003"]},
    }
    j_out = {"verdict": "pass", "scores": {}}
    proc = MagicMock()
    proc.returncode = 0
    proc.stderr = ""
    proc.stdout = "✓ 元锚卡已入库: IC-099\n  UI: file:///tmp/proto/index.html\n"
    proc.args = ["py", "merge", "--mode", "meta"]

    with (
        patch("agents_runtime.orchestrate.run_route_helper_json", return_value=(rh, "")),
        patch("agents_runtime.agents.run_a", return_value=a_out),
        patch("agents_runtime.agents.run_b", return_value=b_out),
        patch("agents_runtime.agents.run_judge", return_value=j_out),
        patch("agents_runtime.orchestrate.run_merge", return_value=proc) as m_merge,
    ):
        res = run_single_case("外部source/x.md", runs_dir=tmp_path / "r4")

    assert res["status"] == "succeeded"
    assert m_merge.call_args.kwargs.get("mode_meta") is True
    assert m_merge.call_args.kwargs.get("mode_update") is False
