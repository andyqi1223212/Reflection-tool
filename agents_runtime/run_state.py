"""RunState：orchestrator 单次 run 的 manifest / 目录读写。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class RunState:
    run_id: str
    run_dir: Path
    created_at: str
    question_md: str
    status: str = "running"
    completed_stages: list[str] = field(default_factory=list)
    current_stage: str | None = None
    last_stage: str | None = None
    verdict: str | None = None
    human_override: str | None = None
    original_verdict: str | None = None
    last_error: str | None = None
    next_action: str | None = None
    push_result: dict[str, Any] | None = None

    def manifest_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["run_dir"] = str(self.run_dir)
        return d


def load_run(runs_dir: Path, run_id: str) -> RunState:
    run_dir = runs_dir / run_id
    mf = run_dir / "manifest.json"
    if not mf.is_file():
        raise FileNotFoundError(f"manifest not found: {mf}")
    raw = json.loads(mf.read_text(encoding="utf-8"))
    return RunState(
        run_id=raw["run_id"],
        run_dir=run_dir,
        created_at=raw.get("created_at", ""),
        question_md=raw.get("question_md", ""),
        status=raw.get("status", "running"),
        completed_stages=list(raw.get("completed_stages") or []),
        current_stage=raw.get("current_stage"),
        last_stage=raw.get("last_stage"),
        verdict=raw.get("verdict"),
        human_override=raw.get("human_override"),
        original_verdict=raw.get("original_verdict"),
        last_error=raw.get("last_error"),
        next_action=raw.get("next_action"),
        push_result=raw.get("push_result"),
    )


def save_manifest(state: RunState) -> None:
    state.run_dir.mkdir(parents=True, exist_ok=True)
    path = state.run_dir / "manifest.json"
    d = state.manifest_dict()
    del d["run_dir"]
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_input_json(run_dir: Path, payload: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "input.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update_manifest_fields(
    state: RunState,
    *,
    status: str | None = None,
    verdict: str | None = None,
    push_result: dict[str, Any] | None = None,
    human_override: str | None = None,
    original_verdict: str | None = None,
    last_error: str | None = None,
    next_action: str | None = None,
) -> None:
    if status is not None:
        state.status = status
    if verdict is not None:
        state.verdict = verdict
    if push_result is not None:
        state.push_result = push_result
    if human_override is not None:
        state.human_override = human_override
    if original_verdict is not None:
        state.original_verdict = original_verdict
    if last_error is not None:
        state.last_error = last_error
    if next_action is not None:
        state.next_action = next_action
    save_manifest(state)


def new_run_state(
    runs_dir: Path,
    run_id: str,
    question_md: str,
) -> RunState:
    run_dir = runs_dir / run_id
    return RunState(
        run_id=run_id,
        run_dir=run_dir,
        created_at=_now_iso(),
        question_md=question_md,
        status="running",
    )
