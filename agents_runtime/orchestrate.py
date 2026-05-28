"""Phase 2：单 case A→B→Judge→(push) 串链 CLI + `run_single_case` API。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from ._subprocess import interpret_merge_exit, run_merge, run_route_helper_json
from .run_state import (
    load_run,
    new_run_state,
    save_input_json,
    save_manifest,
    update_manifest_fields,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUNS_DIR = _REPO_ROOT / "runs"
_CHAINS_PATH = _REPO_ROOT / "data" / "chains.json"

STAGE_ORDER = ["route_helper", "a", "b", "judge", "push"]

_STAGE_ARTIFACTS: dict[str, list[str]] = {
    "route_helper": ["route_helper.json"],
    "a": ["a.json"],
    "b": ["b.json"],
    "judge": ["judge.json"],
    "push": ["push.json", "judge.accepted.json"],
}


def repo_root() -> Path:
    return _REPO_ROOT


def make_run_id(question_md_path: str, runs_dir: Path) -> str:
    today = date.today().isoformat()
    slug = Path(question_md_path).stem
    slug = re.sub(r"[^\w\u4e00-\u9fa5-]+", "-", slug).strip("-")[:40]
    for _ in range(20):
        short = hashlib.sha1(
            f"{today}_{slug}_{time.time()}".encode("utf-8")
        ).hexdigest()[:6]
        rid = f"{today}_{slug}_{short}"
        if not (runs_dir / rid).exists():
            return rid
        time.sleep(0.05)
    raise SystemExit("run_id 碰撞过多；请稍后重试")


def _load_existing_card(chains_path: Path, target_ic_id: str) -> dict[str, Any] | None:
    data = json.loads(chains_path.read_text(encoding="utf-8"))
    chains = data.get("chains")
    if not isinstance(chains, list):
        raise ValueError("chains.json 顶层缺少 .chains 列表")
    for card in chains:
        if isinstance(card, dict) and card.get("id") == target_ic_id:
            return card
    return None


def _read_fewshot_contents(paths: list[str]) -> list[str]:
    out: list[str] = []
    for rel in paths:
        p = Path(rel)
        if not p.is_absolute():
            p = _REPO_ROOT / p
        out.append(p.read_text(encoding="utf-8"))
    return out


def _route_context_from_a(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "route": a.get("route"),
        "target_ic_id": a.get("target_ic_id"),
        "update_directives": a.get("update_directives"),
        "raw_answer_seeds": a.get("raw_answer_seeds"),
        "meta_evidence": a.get("meta_evidence"),
    }


def _truncate_completed_for_resume(state: Any, from_stage: str) -> None:
    idx = STAGE_ORDER.index(from_stage)
    state.completed_stages = state.completed_stages[:idx]


def _delete_artifacts_from(run_dir: Path, from_stage: str) -> None:
    i = STAGE_ORDER.index(from_stage)
    for st in STAGE_ORDER[i:]:
        for name in _STAGE_ARTIFACTS.get(st, []):
            p = run_dir / name
            if p.is_file():
                p.unlink()


def _write_json(run_dir: Path, name: str, obj: Any) -> Path:
    p = run_dir / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _suggest_next_action(stage: str, err: BaseException) -> str:
    if "route_helper" in stage:
        return "检查 question_md 是否存在、chains.json 是否可读；查看 stderr"
    if stage in ("a", "b", "judge"):
        return "查看 runs/<id>/_debug/ 下 parse_fail；或重跑该 stage（--resume --from）"
    if stage == "push":
        return "对照 merge exit 表修复 md/schema；必要时手工 revert v3 md"
    return str(err)


def _extract_ui_url(merge_stdout: str) -> str | None:
    for line in merge_stdout.splitlines():
        if "UI:" in line and "file://" in line:
            return line.strip()
    return None


def run_stage_route_helper(state: Any) -> None:
    rh, dbg = run_route_helper_json(_REPO_ROOT, state.question_md)
    _write_json(state.run_dir, "route_helper.json", rh)
    if dbg.strip():
        dbg_path = state.run_dir / "_debug" / "route_helper_stderr.log"
        dbg_path.parent.mkdir(parents=True, exist_ok=True)
        dbg_path.write_text(dbg, encoding="utf-8")


def run_stage_a(state: Any, fewshot: list[str]) -> None:
    from .agents import run_a

    rh = json.loads((state.run_dir / "route_helper.json").read_text(encoding="utf-8"))
    debug_dir = str(state.run_dir / "_debug")
    out = run_a(
        state.question_md,
        route_helper_output=rh,
        fewshot=fewshot,
        debug_dir=debug_dir,
    )
    _write_json(state.run_dir, "a.json", out)


def run_stage_b(state: Any, fewshot: list[str]) -> None:
    from .agents import run_b

    a = json.loads((state.run_dir / "a.json").read_text(encoding="utf-8"))
    route = a.get("route", "new")
    existing: dict[str, Any] | None = None
    if route == "update":
        tid = a.get("target_ic_id")
        if not tid or not isinstance(tid, str):
            raise ValueError("route=update 但缺少 target_ic_id")
        existing = _load_existing_card(_CHAINS_PATH, tid)
        if existing is None:
            raise FileNotFoundError(
                f"existing_card_not_found: chains.json 中无 id={tid!r}"
            )
    out = run_b(
        a,
        existing_card=existing,
        fewshot=fewshot,
        debug_dir=str(state.run_dir / "_debug"),
    )
    _write_json(state.run_dir, "b.json", out)


def run_stage_judge(state: Any, fewshot: list[str]) -> None:
    from .agents import run_judge

    a = json.loads((state.run_dir / "a.json").read_text(encoding="utf-8"))
    b = json.loads((state.run_dir / "b.json").read_text(encoding="utf-8"))
    rc = _route_context_from_a(a)
    route = rc.get("route", b.get("route", "new"))
    existing: dict[str, Any] | None = None
    if route == "update":
        tid = a.get("target_ic_id")
        if tid:
            existing = _load_existing_card(_CHAINS_PATH, str(tid))
    out = run_judge(
        b,
        rc,
        existing_card=existing,
        fewshot=fewshot,
        debug_dir=str(state.run_dir / "_debug"),
    )
    _write_json(state.run_dir, "judge.json", out)


def run_stage_push(
    state: Any,
    *,
    no_push: bool,
    force_pass: bool,
) -> None:
    b = json.loads((state.run_dir / "b.json").read_text(encoding="utf-8"))
    judge_path = state.run_dir / "judge.json"
    judge = json.loads(judge_path.read_text(encoding="utf-8"))
    verdict = judge.get("verdict")
    raw_kind = b.get("output_kind")
    output_kind = raw_kind or "full_card"

    if raw_kind is not None and raw_kind not in (
        "full_card",
        "update_entry",
        "meta_card",
    ):
        update_manifest_fields(
            state,
            status="awaiting_human",
            verdict=verdict if isinstance(verdict, str) else None,
            next_action="B output_kind 异常；人工检查 b.json",
            push_result={"status": "schema_fail", "output_kind": raw_kind},
        )
        state.completed_stages.append("push")
        save_manifest(state)
        return

    merge_allowed = verdict == "pass" or (
        force_pass and verdict in ("conditional_pass", "fail")
    )
    if not merge_allowed:
        update_manifest_fields(
            state,
            status="awaiting_human",
            verdict=verdict if isinstance(verdict, str) else None,
            next_action="verdict 非 pass；前往 Phase 4 inbox 或手工 review judge.json",
        )
        state.completed_stages.append("push")
        save_manifest(state)
        return

    if no_push:
        update_manifest_fields(
            state,
            status="succeeded",
            verdict=verdict if isinstance(verdict, str) else None,
            push_result={"status": "skipped", "reason": "--no-push"},
        )
        state.completed_stages.append("push")
        save_manifest(state)
        return

    judge_for_merge = judge_path
    if force_pass and verdict != "pass":
        acc = dict(judge)
        acc["verdict"] = "pass"
        judge_for_merge = state.run_dir / "judge.accepted.json"
        judge_for_merge.write_text(
            json.dumps(acc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        state.human_override = "accept"
        state.original_verdict = str(verdict)
        save_manifest(state)

    mode_update = output_kind == "update_entry"
    mode_meta = output_kind == "meta_card"
    proc = run_merge(
        _REPO_ROOT,
        state.run_dir / "b.json",
        judge_for_merge,
        mode_update=mode_update,
        mode_meta=mode_meta,
    )
    args_list = [str(x) for x in proc.args] if proc.args else []
    info = interpret_merge_exit(proc.returncode, proc.stderr, proc.stdout, args_list)
    ui = _extract_ui_url(proc.stdout)
    if info["status"] == "succeeded":
        push_doc = {**info, "ui_line": ui}
        update_manifest_fields(
            state,
            status="succeeded",
            verdict=judge.get("verdict") if isinstance(judge.get("verdict"), str) else None,
            push_result=push_doc,
        )
        _write_json(state.run_dir, "push.json", push_doc)
        state.completed_stages.append("push")
        save_manifest(state)
    else:
        update_manifest_fields(
            state,
            status="failed",
            verdict=judge.get("verdict") if isinstance(judge.get("verdict"), str) else None,
            last_error=f"merge {info['status']} exit={proc.returncode}",
            next_action=str(info.get("next_action") or ""),
            push_result=info,
        )
        raise RuntimeError(info.get("next_action") or info["status"])


def _run_stage(
    stage: str,
    state: Any,
    *,
    fewshot: list[str],
    no_push: bool,
    force_pass: bool,
) -> None:
    state.current_stage = stage
    save_manifest(state)
    if stage == "route_helper":
        run_stage_route_helper(state)
    elif stage == "a":
        run_stage_a(state, fewshot)
    elif stage == "b":
        run_stage_b(state, fewshot)
    elif stage == "judge":
        run_stage_judge(state, fewshot)
    elif stage == "push":
        run_stage_push(state, no_push=no_push, force_pass=force_pass)
    else:
        raise ValueError(stage)
    if stage != "push":
        state.completed_stages.append(stage)
        save_manifest(state)


def run_single_case(
    question_md_path: str,
    *,
    no_push: bool = False,
    force_pass: bool = False,
    fewshot_md_paths: tuple[str, ...] | list[str] = (),
    runs_dir: Path | None = None,
    run_id: str | None = None,
    resume: bool = False,
    from_stage: str | None = None,
) -> dict[str, Any]:
    """Phase 2 主 API。返回 run_id、status、verdict、stages_completed、scores、ui_line、run_dir。"""
    rd = runs_dir or _RUNS_DIR
    rd.mkdir(parents=True, exist_ok=True)
    fewshot = _read_fewshot_contents(list(fewshot_md_paths))

    if resume:
        if not run_id:
            raise ValueError("resume 需要 run_id")
        state = load_run(rd, run_id)
        if from_stage:
            _truncate_completed_for_resume(state, from_stage)
            _delete_artifacts_from(state.run_dir, from_stage)
            save_manifest(state)
    else:
        rid = run_id or make_run_id(question_md_path, rd)
        state = new_run_state(rd, rid, question_md_path)
        state.run_dir.mkdir(parents=True, exist_ok=True)
        save_manifest(state)
        save_input_json(
            state.run_dir,
            {
                "question_md": question_md_path,
                "no_push": no_push,
                "force_pass": force_pass,
                "fewshot_md_paths": list(fewshot_md_paths),
            },
        )

    remaining = [s for s in STAGE_ORDER if s not in state.completed_stages]
    try:
        for stage in remaining:
            try:
                _run_stage(
                    stage,
                    state,
                    fewshot=fewshot,
                    no_push=no_push,
                    force_pass=force_pass,
                )
            except SystemExit:
                raise
            except BaseException as e:
                state.status = "failed"
                state.current_stage = stage
                state.last_stage = stage
                state.last_error = f"{type(e).__name__}: {e}"
                state.next_action = _suggest_next_action(stage, e)
                save_manifest(state)
                break
            if stage == "judge":
                j = json.loads(
                    (state.run_dir / "judge.json").read_text(encoding="utf-8")
                )
                state.verdict = j.get("verdict") if isinstance(j, dict) else None
                save_manifest(state)
            if stage == "push" and state.status == "awaiting_human":
                break
    except KeyboardInterrupt:
        state.status = "failed"
        state.last_stage = state.current_stage
        state.last_error = "KeyboardInterrupt"
        state.next_action = "子进程可能仍在运行；检查 v3 md 与 manifest"
        save_manifest(state)
        raise

    jscores: dict[str, Any] | None = None
    if (state.run_dir / "judge.json").is_file():
        j = json.loads((state.run_dir / "judge.json").read_text(encoding="utf-8"))
        jscores = j.get("scores") if isinstance(j, dict) else None

    ui_line = None
    if isinstance(state.push_result, dict):
        ui_line = state.push_result.get("ui_line")

    return {
        "run_id": state.run_id,
        "status": state.status,
        "verdict": state.verdict,
        "stages_completed": list(state.completed_stages),
        "scores": jscores,
        "ui_line": ui_line,
        "run_dir": str(state.run_dir),
        "next_action": state.next_action,
    }


def list_pending_human(runs_dir: Path | None = None) -> list[dict[str, Any]]:
    rd = runs_dir or _RUNS_DIR
    if not rd.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for mf in sorted(rd.glob("*/manifest.json")):
        try:
            raw = json.loads(mf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if raw.get("status") == "awaiting_human":
            out.append({"run_id": raw.get("run_id"), "manifest": str(mf)})
    return out


def _cli(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(prog="python -m agents_runtime.orchestrate")
    ap.add_argument(
        "question_md",
        nargs="?",
        default=None,
        help="question_md 相对/绝对路径（与 --resume 互斥）",
    )
    ap.add_argument("--resume", metavar="RUN_ID", default=None)
    ap.add_argument(
        "--from",
        dest="from_stage",
        metavar="STAGE",
        default=None,
        help="须配合 --resume；从该 stage 重跑并清后续产物",
    )
    ap.add_argument(
        "--force-pass",
        action="store_true",
        help="以 human_override 写 judge.accepted.json 再 merge（仅当你确认风险）",
    )
    ap.add_argument(
        "--no-push", action="store_true", help="verdict=pass 也不调用 merge"
    )
    ap.add_argument(
        "--fewshot-md",
        action="append",
        default=[],
        metavar="PATH",
        help="可重复；每个 md 全文作为 fewshot 串进 A/Judge",
    )
    ap.add_argument(
        "--list-pending",
        action="store_true",
        help="列出 status=awaiting_human 的 runs",
    )
    args = ap.parse_args(argv)

    if args.from_stage and not args.resume:
        ap.error("--from 必须配合 --resume")

    if args.list_pending:
        rows = list_pending_human()
        if not rows:
            print("(无 awaiting_human)")
            return
        for r in rows:
            print(f"{r['run_id']}\t{r['manifest']}")
        return

    if args.resume:
        if args.question_md:
            ap.error("--resume 模式下不要传 question_md 位置参数")
        if args.from_stage and args.from_stage not in STAGE_ORDER:
            ap.error(f"--from 必须是 {STAGE_ORDER} 之一")
        res = run_single_case(
            "",
            no_push=args.no_push,
            force_pass=args.force_pass,
            fewshot_md_paths=tuple(args.fewshot_md or []),
            resume=True,
            run_id=args.resume,
            from_stage=args.from_stage,
        )
        _print_summary(res)
        if res["status"] == "failed":
            raise SystemExit(1)
        return

    if not args.question_md:
        ap.error("请提供 question_md，或使用 --resume / --list-pending")

    if args.from_stage:
        ap.error("--from 仅允许与 --resume 同用")

    res = run_single_case(
        args.question_md,
        no_push=args.no_push,
        force_pass=args.force_pass,
        fewshot_md_paths=tuple(args.fewshot_md or []),
    )
    _print_summary(res)
    if res["status"] in ("failed",):
        raise SystemExit(1)


def _print_summary(res: dict[str, Any]) -> None:
    print(f"✓ run_id={res['run_id']}")
    print(f"  status={res['status']} verdict={res['verdict']!r}")
    print(f"  stages={res['stages_completed']}")
    if res.get("ui_line"):
        print(f"  {res['ui_line']}")
    if res.get("next_action"):
        print(f"  next_action: {res['next_action']}")
    print(f"  dir={res['run_dir']}")


if __name__ == "__main__":
    _cli()
