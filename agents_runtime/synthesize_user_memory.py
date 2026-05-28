#!/usr/bin/env python3
"""
读最近 succeeded runs + feedback + 当前 raw-questions-synthesis.md → 产 §2/§5/§6 patch 候选。

用法：
    ./venv/bin/python3 -m agents_runtime.synthesize_user_memory \\
        --synthesis context/raw-questions-synthesis.md \\
        --runs-dir runs/ \\
        --feedback users/$IC_USER/feedback.jsonl \\
        --since 2026-05-15 \\
        --out users/$IC_USER/synthesis_proposals/ \\
        [--min-runs 5] [--model deepseek-v4-pro] [--dry-run-no-llm]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._patch_utils import validate_patches
from .llm_client import _DEFAULT_REASONING, call_json
from .loader import _repo_root

ALLOWED_SECTION_NUMS = frozenset({2, 5, 6})


def _now_iso_compact() -> str:
    tz = datetime.now().astimezone().tzinfo or timezone.utc
    return datetime.now(tz).strftime("%Y-%m-%dT%H%M%S%z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _section_num(section: str) -> int | None:
    m = re.search(r"§\s*(\d+)", section or "")
    return int(m.group(1)) if m else None


def _extract_last_synced(text: str) -> str:
    m = re.search(r"最后更新[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m2 = re.search(r"文档版本[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    return m2.group(1) if m2 else ""


def _load_prompt() -> str:
    p = (
        Path(__file__).resolve().parent
        / "_prompts"
        / "synthesize-user-memory.prompt.md"
    )
    text = p.read_text(encoding="utf-8")
    if text.startswith("---"):
        sep = re.search(r"\n---\s*\n", text[3:])
        if sep:
            text = text[3 + sep.end() :].lstrip()
    return text


def _collect_succeeded_runs(
    root: Path, runs_dir: Path, since: str | None
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not runs_dir.is_dir():
        return out
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        manifest_path = d / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if manifest.get("status") != "succeeded":
            continue
        created = manifest.get("created_at") or ""
        if since and created < since:
            continue
        run_id = manifest.get("run_id") or d.name
        question_md = ""
        q_rel = manifest.get("question_md")
        if q_rel:
            q_path = Path(q_rel) if Path(q_rel).is_absolute() else root / q_rel
            if q_path.is_file():
                question_md = q_path.read_text(encoding="utf-8")
        if not question_md and (d / "question.md").is_file():
            question_md = (d / "question.md").read_text(encoding="utf-8")
        a_obj: dict[str, Any] = {}
        b_obj: dict[str, Any] = {}
        a_path = d / "a.json"
        b_path = d / "b.json"
        if a_path.is_file():
            try:
                a_raw = json.loads(a_path.read_text(encoding="utf-8"))
                a_obj = {
                    "patterns": a_raw.get("patterns"),
                    "axis": a_raw.get("axis"),
                    "route": a_raw.get("route"),
                    "title": a_raw.get("title"),
                }
            except json.JSONDecodeError:
                pass
        if b_path.is_file():
            try:
                b_raw = json.loads(b_path.read_text(encoding="utf-8"))
                cryst = b_raw.get("crystallization") or {}
                if b_raw.get("output_kind") == "update_entry":
                    cryst = (b_raw.get("update_entry") or {}).get("crystallization") or {}
                b_obj = {
                    "mechanism": cryst.get("mechanism"),
                    "anchor": cryst.get("anchor"),
                    "micro_steps": cryst.get("micro_steps") or [],
                    "output_kind": b_raw.get("output_kind"),
                }
            except json.JSONDecodeError:
                pass
        out.append(
            {
                "run_id": run_id,
                "created_at": created,
                "question_md": question_md,
                "a": a_obj,
                "b": b_obj,
            }
        )
    return out


def _feedback_for_runs(
    rows: list[dict[str, Any]], run_ids: set[str]
) -> dict[str, list[dict[str, Any]]]:
    by_run: dict[str, list[dict[str, Any]]] = {rid: [] for rid in run_ids}
    for idx, r in enumerate(rows):
        tid = r.get("target_id")
        if r.get("target_type") != "run" or tid not in run_ids:
            continue
        item = dict(r)
        item["row_index"] = idx
        by_run.setdefault(tid, []).append(item)
    return by_run


def _validate_proposal_shape(obj: Any) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "根节点不是 object"
    for k in ("base_path", "hypotheses", "patches"):
        if k not in obj:
            return False, f"缺少必备字段: {k}"
    if not isinstance(obj.get("hypotheses"), list):
        return False, "hypotheses 必须是数组"
    if not isinstance(obj.get("patches"), list):
        return False, "patches 必须是数组"
    return True, ""


def _validate_sections_and_evidence(proposal: dict[str, Any]) -> list[str]:
    """返回错误信息列表；空 = 通过。"""
    errs: list[str] = []
    for patch in proposal.get("patches") or []:
        sec = patch.get("section") or ""
        n = _section_num(sec)
        if n not in ALLOWED_SECTION_NUMS:
            errs.append(f"patch {patch.get('id')}: section {sec!r} 不在白名单 §2/§5/§6")
        runs = patch.get("evidence_runs") or []
        if len(runs) < 2:
            errs.append(f"patch {patch.get('id')}: evidence_runs 不足 2 个")
    return errs


def _check_anchor_match(
    proposal: dict[str, Any], synthesis_text: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid: list[dict[str, Any]] = []
    auto_withheld: list[dict[str, Any]] = []
    failed_ids = validate_patches(synthesis_text, proposal.get("patches") or [])
    failed_set = set(failed_ids)
    for patch in proposal.get("patches") or []:
        if patch.get("id") in failed_set:
            auto_withheld.append(
                {
                    "patch_id": patch.get("id"),
                    "section": patch.get("section"),
                    "reason": "anchor_text / section 预校验未通过",
                }
            )
        else:
            valid.append(patch)
    return valid, auto_withheld


def _render_md(proposal: dict[str, Any], synthesis_path: Path) -> str:
    lines: list[str] = []
    lines.append("# Synthesis proposal · 用户记忆库")
    lines.append("")
    lines.append(f"- 基准：`{synthesis_path}`")
    lines.append(f"- 上次同步：{proposal.get('last_synced_was') or '?'}")
    stats = proposal.get("meta_stats") or {}
    lines.append(f"- runs 窗口：{stats.get('runs_window_count', '?')} · patches：{stats.get('patches_count', '?')}")
    lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    for h in proposal.get("hypotheses") or []:
        lines.append(
            f"- **{h.get('id')}**：{h.get('text')} `runs={h.get('evidence_runs')}`"
        )
    lines.append("")
    lines.append("## Patches")
    lines.append("")
    for p in proposal.get("patches") or []:
        lines.append(f"### {p.get('id')} · {p.get('section')} · {p.get('action')}")
        lines.append("")
        lines.append(f"- evidence_runs: {p.get('evidence_runs')}")
        if p.get("anchor_text"):
            lines.append("")
            lines.append("**anchor_text**：")
            lines.append("```")
            lines.append(str(p.get("anchor_text")))
            lines.append("```")
        lines.append("")
        lines.append("**new_content**：")
        lines.append("```")
        lines.append(str(p.get("new_content") or ""))
        lines.append("```")
        lines.append("")
    if proposal.get("withheld") or proposal.get("_auto_withheld"):
        lines.append("## Withheld")
        lines.append("")
        for w in proposal.get("withheld") or []:
            lines.append(f"- {w.get('section')}: {w.get('reason')}")
        for w in proposal.get("_auto_withheld") or []:
            lines.append(f"- patch `{w.get('patch_id')}`: {w.get('reason')}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*由 `agents_runtime.synthesize_user_memory` 生成。*")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="读 runs 产 synthesis patch 候选")
    parser.add_argument("--synthesis", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--min-runs", type=int, default=5)
    parser.add_argument("--model", type=str, default=_DEFAULT_REASONING)
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--dry-run-no-llm", action="store_true")
    args = parser.parse_args()

    root = _repo_root()
    synthesis_path = args.synthesis if args.synthesis.is_absolute() else root / args.synthesis
    runs_dir = args.runs_dir if args.runs_dir.is_absolute() else root / args.runs_dir
    feedback_path = args.feedback if args.feedback.is_absolute() else root / args.feedback
    out_dir = args.out if args.out.is_absolute() else root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    if not synthesis_path.is_file():
        print(f"ERROR: synthesis 不存在 {synthesis_path}", file=sys.stderr)
        return 3

    recent_runs = _collect_succeeded_runs(root, runs_dir, args.since)
    if len(recent_runs) < args.min_runs:
        print(
            f"WARN: 仅 {len(recent_runs)} 个 succeeded run（阈值 {args.min_runs}）",
            file=sys.stderr,
        )
        if not args.dry_run_no_llm and len(recent_runs) == 0:
            return 2

    feedback_rows = _read_jsonl(feedback_path)
    if args.since:
        feedback_rows = [r for r in feedback_rows if (r.get("ts") or "") >= args.since]
    run_ids = {r["run_id"] for r in recent_runs}
    fb_by_run = _feedback_for_runs(feedback_rows, run_ids)
    for run in recent_runs:
        run["feedback"] = fb_by_run.get(run["run_id"], [])

    synthesis_text = synthesis_path.read_text(encoding="utf-8")
    last_synced = _extract_last_synced(synthesis_text)

    feedback_signals = []
    for idx, row in enumerate(feedback_rows):
        item = dict(row)
        item["row_index"] = idx
        feedback_signals.append(item)

    print(
        f"[synthesize_user_memory] {len(recent_runs)} runs · {len(feedback_signals)} feedback · last_synced={last_synced}",
        file=sys.stderr,
    )

    user_payload = {
        "recent_runs": recent_runs,
        "synthesis_current": synthesis_text,
        "feedback_signals": feedback_signals,
        "_hint": {"last_synced_was": last_synced},
    }

    if args.dry_run_no_llm:
        proposal = {
            "base_path": str(synthesis_path.relative_to(root)),
            "last_synced_was": last_synced,
            "hypotheses": [],
            "patches": [],
            "withheld": [{"section": "§2", "reason": "dry-run 未调 LLM"}],
            "meta_stats": {
                "runs_window_count": len(recent_runs),
                "feedback_used_count": len(feedback_signals),
                "patches_count": 0,
            },
        }
    else:
        try:
            proposal = call_json(
                system=_load_prompt(),
                user=json.dumps(user_payload, ensure_ascii=False),
                model=args.model,
                temperature=args.temperature,
                agent_id="synthesize-user-memory",
                debug_dir=str(out_dir / "_debug"),
            )
        except Exception as e:
            print(f"ERROR: LLM 调用失败 {e}", file=sys.stderr)
            return 4
        ok, msg = _validate_proposal_shape(proposal)
        if not ok:
            print(f"ERROR: proposal 不符 schema：{msg}", file=sys.stderr)
            return 5
        sec_errs = _validate_sections_and_evidence(proposal)
        if sec_errs:
            print(f"ERROR: {'; '.join(sec_errs)}", file=sys.stderr)
            return 6

    valid_patches, auto_withheld = _check_anchor_match(proposal, synthesis_text)
    proposal["patches"] = valid_patches
    if auto_withheld:
        proposal["_auto_withheld"] = auto_withheld
    proposal.setdefault("meta_stats", {})
    proposal["meta_stats"]["patches_count"] = len(valid_patches)
    proposal["meta_stats"]["runs_window_count"] = len(recent_runs)
    proposal["meta_stats"].setdefault(
        "feedback_used_count", len(feedback_signals)
    )
    proposal.setdefault("base_path", str(synthesis_path.relative_to(root)))
    proposal.setdefault("last_synced_was", last_synced)

    ts = _now_iso_compact()
    json_out = out_dir / f"{ts}_proposal.json"
    md_out = out_dir / f"{ts}_proposal.md"
    json_out.write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_out.write_text(_render_md(proposal, synthesis_path), encoding="utf-8")
    print(f"[synthesize_user_memory] 写 {json_out.relative_to(root)}", file=sys.stderr)
    print(ts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
