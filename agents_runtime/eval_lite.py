#!/usr/bin/env python3
"""Lexicon trial：复用 runs/<id>/a.json，用指定 lexicon 版本重跑 B，产出 diff。"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import run_b
from .orchestrate import _load_existing_card

_REPO = Path(__file__).resolve().parent.parent
_CHAINS = _REPO / "data" / "chains.json"
_RUNS = _REPO / "runs"
_OUT_BASE = _REPO / "eval" / "lexicon_trials"

_PICK_CHOICES = ("last5_accepted", "last5_pushed", "judge_top5")

# 前端 chains.json 卡 → 有 orchestrate run 时复用其 a.json
_CHAIN_A_FROM_RUN: dict[str, str] = {
    "IC-026": "2026-05-21_觉醒_0f898d",
    "IC-024": "2026-05-19_球场垃圾话应对策略_182433",
}


def _now_iso() -> str:
    tz = datetime.now().astimezone().tzinfo or timezone.utc
    return datetime.now(tz).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return obj if isinstance(obj, dict) else None


def _lexicon_path(version: int) -> Path:
    p = _REPO / "context" / f"pipeline-b-style-lexicon-v{version}.md"
    if not p.is_file():
        raise SystemExit(f"ERROR: lexicon 不存在: {p}")
    return p


def _extract_cryst(b: dict[str, Any]) -> dict[str, Any]:
    kind = b.get("output_kind")
    if kind == "update_entry":
        ue = b.get("update_entry") or {}
        c = ue.get("crystallization") if isinstance(ue, dict) else {}
    else:
        c = b.get("crystallization") or {}
    if not isinstance(c, dict):
        c = {}
    steps = c.get("micro_steps")
    if not isinstance(steps, list):
        steps = []
    return {
        "mechanism": (c.get("mechanism") or "").strip(),
        "anchor": (c.get("anchor") or "").strip(),
        "micro_steps": [str(s).strip() for s in steps if s],
    }


def _title_from_b(b: dict[str, Any], a: dict[str, Any]) -> str:
    if b.get("title"):
        return str(b["title"])
    if a.get("title"):
        return str(a["title"])
    ue = b.get("update_entry") or {}
    if isinstance(ue, dict) and ue.get("patch_reasoning"):
        return str(ue["patch_reasoning"])[:40]
    return b.get("target_ic_id") or a.get("target_ic_id") or "?"


def _diff_note(old_s: str, new_s: str) -> str:
    o, n = len(old_s), len(new_s)
    if old_s == new_s:
        return "无变化"
    return f"字数 {o}→{n}（{'+' if n >= o else ''}{n - o}）"


def _render_diff_md(
    *,
    run_id: str,
    title: str,
    route: str,
    axis: str,
    lexicon_version: int,
    old_label: str,
    cryst_old: dict[str, Any],
    cryst_new: dict[str, Any],
) -> str:
    lines = [
        f"# Trial Diff · {title} · route={route} · axis={axis}",
        "",
        f"> lexicon trial: {old_label} (旧 b.json) → v{lexicon_version} (新跑)",
        f"> trial ts: {_now_iso()}",
        f"> run_id: `{run_id}`",
        "",
        "## mechanism",
        "",
        f"### {old_label} (旧)",
        f"> {cryst_old['mechanism'] or '（空）'}",
        f"（{_diff_note(cryst_old['mechanism'], cryst_new['mechanism'])}）",
        "",
        f"### v{lexicon_version} (新)",
        f"> {cryst_new['mechanism'] or '（空）'}",
        "",
        "## anchor",
        "",
        "| 旧 | 新 |",
        "|---|---|",
        f"| {cryst_old['anchor'] or '—'} | {cryst_new['anchor'] or '—'} |",
        "",
        "## micro_steps",
        "",
        "| # | 旧 | 新 |",
        "|---|---|---|",
    ]
    max_rows = max(len(cryst_old["micro_steps"]), len(cryst_new["micro_steps"]), 1)
    for i in range(max_rows):
        o = cryst_old["micro_steps"][i] if i < len(cryst_old["micro_steps"]) else "—"
        n = cryst_new["micro_steps"][i] if i < len(cryst_new["micro_steps"]) else "—"
        lines.append(f"| {i + 1} | {o} | {n} |")
    lines.append("")
    return "\n".join(lines)


def _run_has_ab(run_dir: Path) -> bool:
    return (run_dir / "a.json").is_file() and (run_dir / "b.json").is_file()


def _ic_from_run(run_dir: Path, a: dict[str, Any], b: dict[str, Any], manifest: dict[str, Any]) -> str | None:
    push = manifest.get("push_result") or {}
    if push.get("merged_ic_id"):
        return str(push["merged_ic_id"])
    if b.get("id") and b.get("id") != "IC-NEW":
        return str(b["id"])
    if b.get("target_ic_id"):
        return str(b["target_ic_id"])
    if a.get("target_ic_id"):
        return str(a["target_ic_id"])
    return None


def _scan_runs() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for manifest_path in sorted(_RUNS.glob("*/manifest.json")):
        parent = manifest_path.parent
        if parent.name.startswith("_") or parent.name.startswith("sample_"):
            continue
        if not _run_has_ab(parent):
            continue
        m = _read_json(manifest_path) or {}
        a = _read_json(parent / "a.json") or {}
        b = _read_json(parent / "b.json") or {}
        judge = _read_json(parent / "judge.json") or {}
        scores = judge.get("scores") if isinstance(judge.get("scores"), dict) else {}
        overall = scores.get("overall")
        try:
            overall_f = float(overall) if overall is not None else None
        except (TypeError, ValueError):
            overall_f = None
        items.append(
            {
                "run_id": m.get("run_id") or parent.name,
                "run_dir": parent,
                "created_at": m.get("created_at") or "",
                "status": m.get("status"),
                "verdict": m.get("verdict") or judge.get("verdict"),
                "judge_overall": overall_f,
                "ic_id": _ic_from_run(parent, a, b, m),
                "a": a,
                "b": b,
            }
        )
    return items


def _map_ic_to_run(items: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in sorted(items, key=lambda x: x["created_at"], reverse=True):
        ic = it.get("ic_id")
        if ic and ic not in out:
            out[ic] = it["run_id"]
    return out


def _load_chains() -> list[dict[str, Any]]:
    if not _CHAINS.is_file():
        raise SystemExit(f"ERROR: 找不到 {_CHAINS}")
    data = json.loads(_CHAINS.read_text(encoding="utf-8"))
    chains = data.get("chains")
    if not isinstance(chains, list):
        raise SystemExit("ERROR: chains.json 缺少 chains 列表")
    return [c for c in chains if isinstance(c, dict) and c.get("id")]


def _get_chain_card(ic_id: str) -> dict[str, Any]:
    for card in _load_chains():
        if card.get("id") == ic_id:
            return card
    raise SystemExit(f"ERROR: chains.json 无 {ic_id}")


def _chain_to_b_old(card: dict[str, Any]) -> dict[str, Any]:
    """前端 chains.json 单卡 → 旧 b 基准（与主站入库形态一致）。"""
    ic = str(card["id"])
    updates = card.get("updates") or []
    if updates and isinstance(updates[-1], dict):
        ue = dict(updates[-1])
        return {
            "output_kind": "update_entry",
            "target_ic_id": ic,
            "title": card.get("title"),
            "update_entry": ue,
            "_trial_note": "b_old=chains 最新 update_entry（前端可见增量层）",
        }
    child_ids = []
    for ref in card.get("source_refs") or []:
        if isinstance(ref, str) and ref.startswith("child:"):
            child_ids = [x.strip() for x in ref.split(":", 1)[-1].split(",") if x.strip()]
    out: dict[str, Any] = {
        "output_kind": "meta_card" if ic == "IC-026" else "full_card",
        "id": ic,
        "title": card.get("title"),
        "patterns": card.get("patterns") or [],
        "axis": card.get("axis"),
        "crystallization": dict(card.get("crystallization") or {}),
        "chain": dict(card.get("chain") or {}),
        "source_refs": list(card.get("source_refs") or []),
        "_trial_note": "b_old=chains.json 主卡 crystallization（前端 SSOT）",
    }
    if ic == "IC-026":
        out["meta_relation"] = {"child_ic_ids": child_ids} if child_ids else {
            "child_ic_ids": ["IC-003", "IC-010", "IC-011", "IC-012", "IC-023"]
        }
    return out


def _chain_to_a_draft(card: dict[str, Any]) -> dict[str, Any]:
    ic = str(card["id"])
    mapped_run = _CHAIN_A_FROM_RUN.get(ic)
    if mapped_run:
        a = _read_json(_RUNS / mapped_run / "a.json")
        if a:
            print(f"[eval_lite] {ic} a.json ← runs/{mapped_run}", file=sys.stderr)
            return a

    updates = card.get("updates") or []
    last_ue = updates[-1] if updates else {}
    pr = (last_ue.get("patch_reasoning") or "") if isinstance(last_ue, dict) else ""
    route = "meta" if ic == "IC-026" else "update" if updates else "new"
    a: dict[str, Any] = {
        "route": route,
        "title": card.get("title"),
        "patterns": list(card.get("patterns") or []),
        "axis": card.get("axis"),
        "chain": dict(card.get("chain") or {}),
        "source_refs": list(card.get("source_refs") or []),
    }
    if route == "update":
        a["target_ic_id"] = ic
        a["update_directives"] = {
            "mechanism": pr or "在既有机制上追加一层，与主卡并存；勿整卡重写。",
            "anchor": "短锚候选，≤20 字，可从用户走通句里抽。",
            "micro_steps": "1-3 步身体可执行动作；勿抽象规劝。",
            "patterns": "按情境补 pattern，勿删原卡。",
            "source_refs": "补 source_refs。",
            "chain.questions": "可尾部追加原话。",
            "chain.trigger": "可补 trigger 物理线。",
        }
    elif route == "meta":
        a["mechanism_sketch"] = (card.get("crystallization") or {}).get("mechanism", "")
        a["meta_evidence"] = {
            "child_ic_ids": ["IC-003", "IC-010", "IC-011", "IC-012", "IC-023"],
            "cross_cutting_reason": "横切自我监控→执行崩溃类场景，独立元锚。",
        }
    else:
        a["mechanism_sketch"] = (card.get("crystallization") or {}).get("mechanism", "")
    print(f"[eval_lite] {ic} a.json ← chains 合成（无对应 run）", file=sys.stderr)
    return a


def _resolve_trial_cases(
    *,
    pick: str,
    run_ids: list[str] | None,
    chain_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """每项: trial_id, a, b_old, source_chain_id, pick_label。"""
    cases: list[dict[str, Any]] = []
    if chain_ids:
        for ic in chain_ids:
            card = _get_chain_card(ic)
            cases.append(
                {
                    "trial_id": ic,
                    "a": _chain_to_a_draft(card),
                    "b_old": _chain_to_b_old(card),
                    "source_chain_id": ic,
                    "pick": f"chains:{ic}",
                }
            )
        return cases

    for run_id in pick_run_ids(pick, run_ids):
        run_dir = _RUNS / run_id
        a = _read_json(run_dir / "a.json")
        b_old = _read_json(run_dir / "b.json")
        if not a or not b_old:
            continue
        manifest = _read_json(run_dir / "manifest.json") or {}
        cases.append(
            {
                "trial_id": run_id,
                "a": a,
                "b_old": b_old,
                "source_chain_id": _ic_from_run(run_dir, a, b_old, manifest),
                "pick": pick,
            }
        )
    return cases


def pick_run_ids(pick: str, explicit: list[str] | None) -> list[str]:
    if explicit:
        return explicit
    items = _scan_runs()
    if pick == "last5_pushed":
        pushed = [
            it
            for it in items
            if it.get("status") == "succeeded" or (it.get("verdict") == "pass")
        ]
        pushed.sort(key=lambda x: x["created_at"], reverse=True)
        return [it["run_id"] for it in pushed[:5]]

    if pick == "judge_top5":
        ranked = [it for it in items if it.get("judge_overall") is not None]
        ranked.sort(key=lambda x: x["judge_overall"], reverse=True)
        return [it["run_id"] for it in ranked[:5]]

    # last5_accepted: chains.json created_at desc → 映射到 run_id
    if not _CHAINS.is_file():
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return [it["run_id"] for it in items[:5]]
    data = json.loads(_CHAINS.read_text(encoding="utf-8"))
    chains = data.get("chains") or []
    if not isinstance(chains, list):
        chains = []
    sorted_chains = sorted(
        [c for c in chains if isinstance(c, dict) and c.get("id")],
        key=lambda c: str(c.get("created_at") or ""),
        reverse=True,
    )
    ic_to_run = _map_ic_to_run(items)
    run_ids: list[str] = []
    for card in sorted_chains[:5]:
        ic = str(card["id"])
        rid = ic_to_run.get(ic)
        if rid and rid not in run_ids:
            run_ids.append(rid)
    if len(run_ids) < 5:
        for it in sorted(items, key=lambda x: x["created_at"], reverse=True):
            if it["run_id"] not in run_ids:
                run_ids.append(it["run_id"])
            if len(run_ids) >= 5:
                break
    return run_ids


def _summary_row(
    run_id: str,
    title: str,
    route: str,
    co: dict[str, Any],
    cn: dict[str, Any],
    status: str,
    note: str,
) -> str:
    return (
        f"| `{run_id}` | {title[:24]} | {route} | "
        f"{len(co['mechanism'])}→{len(cn['mechanism'])} | "
        f"{len(co['anchor'])}→{len(cn['anchor'])} | "
        f"{len(co['micro_steps'])}→{len(cn['micro_steps'])} | "
        f"{status} | {note} |"
    )


def _clean_out_dir(out_dir: Path) -> None:
    if not out_dir.is_dir():
        return
    for child in out_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
            print(f"[eval_lite] 已删除旧 trial 目录 {child.name}", file=sys.stderr)


def run_trial(
    *,
    lexicon_version: int,
    pick: str,
    run_ids: list[str] | None,
    chain_ids: list[str] | None = None,
    out_base: Path | None = None,
    replace_out: bool = False,
) -> dict[str, Any]:
    lex_path = _lexicon_path(lexicon_version)
    rel_lex = str(lex_path.relative_to(_REPO))
    out_dir = (out_base or _OUT_BASE) / f"v{lexicon_version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if replace_out:
        _clean_out_dir(out_dir)

    cases = _resolve_trial_cases(pick=pick, run_ids=run_ids, chain_ids=chain_ids)
    if not cases:
        raise SystemExit("ERROR: 没有可跑的 trial 用例")

    pick_label = (
        f"chains={','.join(chain_ids)}"
        if chain_ids
        else (pick if not run_ids else f"run_ids={','.join(run_ids)}")
    )
    trial_ids = [c["trial_id"] for c in cases]

    summary_lines = [
        f"# Lexicon v{lexicon_version} trial 汇总",
        "",
        f"> pick=`{pick_label}` · n={len(cases)} · ts={_now_iso()}",
        f"> lexicon: `{rel_lex}`",
        f"> b_old 来源：chains.json（前端 SSOT）" if chain_ids else "",
        "",
        "| run_id | title | route | mech字数 旧→新 | anchor字数 旧→新 | steps数 旧→新 | 状态 | 备注 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    errors: list[dict[str, str]] = []

    for case in cases:
        trial_id = case["trial_id"]
        a = case["a"]
        b_old = case["b_old"]
        route = str(a.get("route") or "?")
        axis = str(a.get("axis") or "?")
        title = _title_from_b(b_old, a)
        trial_run_dir = out_dir / trial_id
        trial_run_dir.mkdir(parents=True, exist_ok=True)

        (trial_run_dir / "b_old.json").write_text(
            json.dumps(b_old, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (trial_run_dir / "a.json").write_text(
            json.dumps(a, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        existing: dict[str, Any] | None = None
        if route == "update":
            tid = a.get("target_ic_id") or case.get("source_chain_id")
            if not tid:
                note = "update 路由缺 target_ic_id"
                (trial_run_dir / "error.json").write_text(
                    json.dumps({"error": note}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                summary_lines.append(
                    _summary_row(
                        trial_id, title, route, _extract_cryst(b_old), _extract_cryst({}), "FAIL", note
                    )
                )
                errors.append({"run_id": trial_id, "error": note})
                continue
            existing = _load_existing_card(_CHAINS, str(tid))
            if not existing:
                note = f"chains.json 无 {tid}"
                (trial_run_dir / "error.json").write_text(
                    json.dumps({"error": note}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                summary_lines.append(
                    _summary_row(
                        trial_id, title, route, _extract_cryst(b_old), _extract_cryst({}), "SKIP", note
                    )
                )
                errors.append({"run_id": trial_id, "error": note})
                continue

        try:
            b_new = run_b(a, existing_card=existing, lexicon_path=rel_lex)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"[eval_lite] FAIL {trial_id}: {e}", file=sys.stderr)
            (trial_run_dir / "error.json").write_text(
                json.dumps({"error": str(e), "traceback": tb}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            summary_lines.append(
                _summary_row(
                    trial_id, title, route, _extract_cryst(b_old), _extract_cryst({}), "FAIL", str(e)[:80]
                )
            )
            errors.append({"run_id": trial_id, "error": str(e)})
            continue

        (trial_run_dir / "b_new.json").write_text(
            json.dumps(b_new, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        co, cn = _extract_cryst(b_old), _extract_cryst(b_new)
        old_ver = lexicon_version - 1
        diff_md = _render_diff_md(
            run_id=trial_id,
            title=title,
            route=route,
            axis=axis,
            lexicon_version=lexicon_version,
            old_label="chains（前端）" if chain_ids else (f"v{old_ver}" if old_ver >= 1 else "baseline"),
            cryst_old=co,
            cryst_new=cn,
        )
        (trial_run_dir / "diff.md").write_text(diff_md, encoding="utf-8")

        meta = {
            "run_id": trial_id,
            "lexicon_version": lexicon_version,
            "lexicon_path": rel_lex,
            "ts": _now_iso(),
            "route": route,
            "axis": axis,
            "title": title,
            "source_chain_id": case.get("source_chain_id"),
            "pick": case.get("pick"),
            "b_old_source": "chains.json" if chain_ids else "runs/b.json",
        }
        (trial_run_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if co == cn:
            note = "晶体字段与旧版完全相同"
        elif co["mechanism"] == cn["mechanism"]:
            note = "mechanism 未变；anchor/steps 有变"
        else:
            note = "mechanism 有改写"
        summary_lines.append(_summary_row(trial_id, title, route, co, cn, "OK", note))
        print(f"[eval_lite] OK {trial_id}", file=sys.stderr)

    summary_lines.append("")
    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    batch_meta = {
        "lexicon_version": lexicon_version,
        "lexicon_path": rel_lex,
        "ts": _now_iso(),
        "pick": pick_label,
        "run_ids": trial_ids,
        "chain_ids": chain_ids or [],
        "errors": errors,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(batch_meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "out_dir": str(out_dir.relative_to(_REPO)),
        "summary_path": str(summary_path.relative_to(_REPO)),
        "run_count": len(cases),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lexicon trial：复用 a.json 重跑 B")
    ap.add_argument("--lexicon-version", type=int, required=True)
    ap.add_argument("--pick", choices=_PICK_CHOICES, default="last5_accepted")
    ap.add_argument("--run-ids", default="", help="逗号分隔 run_id，覆盖 --pick")
    ap.add_argument(
        "--chain-ids",
        default="",
        help="逗号分隔 IC-xxx：b_old 取自 data/chains.json（前端 SSOT），优先于 --run-ids",
    )
    ap.add_argument(
        "--replace",
        action="store_true",
        help="跑前清空 eval/lexicon_trials/v<N>/ 下所有子目录",
    )
    ap.add_argument("--out", type=Path, default=_OUT_BASE)
    args = ap.parse_args(argv)

    chain_ids = [x.strip() for x in args.chain_ids.split(",") if x.strip()] or None
    explicit = None if chain_ids else ([x.strip() for x in args.run_ids.split(",") if x.strip()] or None)
    result = run_trial(
        lexicon_version=args.lexicon_version,
        pick=args.pick,
        run_ids=explicit,
        chain_ids=chain_ids,
        out_base=args.out,
        replace_out=args.replace,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
