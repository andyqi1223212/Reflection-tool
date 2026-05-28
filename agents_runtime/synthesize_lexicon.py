#!/usr/bin/env python3
"""
读 feedback.jsonl + 当前 lexicon + 涉及卡 / b.json 摘要 → 调 flagship 模型产 lexicon patch 候选。

只输出候选，不直接改 lexicon。落两份文件到 users/<uid>/lexicon_proposals/：
- <ts>_proposal.json：结构化（给 apply 用）
- <ts>_proposal.md：人类可读（给 review UI 渲染）

用法：
    ./venv/bin/python3 -m agents_runtime.synthesize_lexicon \\
        --feedback users/$IC_USER/feedback.jsonl \\
        --lexicon  context/pipeline-b-style-lexicon-v4.md \\
        --out      users/$IC_USER/lexicon_proposals/ \\
        [--min-feedback 20] [--since 2026-05-15] [--model deepseek-v4-pro]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm_client import call_json, _DEFAULT_REASONING
from .loader import _repo_root

# 可在写卡 / 卡更新时拿到的字段子集
_CARD_FIELDS = ("title", "mechanism", "anchor", "micro_steps")


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


def _filter_since(rows: list[dict[str, Any]], since: str | None) -> list[dict[str, Any]]:
    if not since:
        return rows
    return [r for r in rows if (r.get("ts") or "") >= since]


def _extract_card_snapshot(
    root: Path, target_type: str, target_id: str
) -> dict[str, Any] | None:
    if not target_id:
        return None
    if target_type == "run":
        b_path = root / "runs" / target_id / "b.json"
        if not b_path.is_file():
            return None
        try:
            obj = json.loads(b_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        # b.json schema 有两种：full_card / meta_card / update_entry
        if obj.get("output_kind") == "update_entry":
            cryst = (obj.get("update_entry") or {}).get("crystallization") or {}
            return {
                "title": f"<update for {obj.get('target_ic_id')}>",
                "mechanism": cryst.get("mechanism"),
                "anchor": cryst.get("anchor"),
                "micro_steps": cryst.get("micro_steps") or [],
                "output_kind": "update_entry",
                "target_ic_id": obj.get("target_ic_id"),
            }
        cryst = obj.get("crystallization") or {}
        return {
            "title": obj.get("title"),
            "mechanism": cryst.get("mechanism"),
            "anchor": cryst.get("anchor"),
            "micro_steps": cryst.get("micro_steps") or [],
            "output_kind": obj.get("output_kind"),
        }
    if target_type == "card":
        chains_path = root / "data" / "chains.json"
        if not chains_path.is_file():
            return None
        try:
            data = json.loads(chains_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        chains = data.get("chains") if isinstance(data, dict) else data
        if not isinstance(chains, list):
            return None
        for card in chains:
            if isinstance(card, dict) and card.get("id") == target_id:
                # 主卡 + updates 拼接，给模型完整画面
                updates = card.get("updates") or []
                update_summaries: list[dict[str, Any]] = []
                for u in updates:
                    if not isinstance(u, dict):
                        continue
                    ucryst = u.get("crystallization") or {}
                    update_summaries.append(
                        {
                            "updated_at": u.get("updated_at"),
                            "mechanism": ucryst.get("mechanism"),
                            "anchor": ucryst.get("anchor"),
                            "micro_steps": ucryst.get("micro_steps") or [],
                            "patch_reasoning": u.get("patch_reasoning"),
                        }
                    )
                return {
                    "title": card.get("title"),
                    "mechanism": card.get("mechanism"),
                    "anchor": card.get("anchor"),
                    "micro_steps": card.get("micro_steps") or [],
                    "updates": update_summaries,
                }
        return None
    return None


def _enrich_card_snapshots_from_v3(
    root: Path, snapshots: dict[str, dict[str, Any]]
) -> None:
    """data/chains.json 里部分卡正文字段为 None；从 v3 md 兜底抽 mechanism / anchor / micro_steps。"""
    v3_path = root / "inquiry-chain-demo-v3-good-answer.md"
    if not v3_path.is_file():
        return
    text = v3_path.read_text(encoding="utf-8")
    # 按 ### IC-XXX 切；每段抽机制 / 入口句 / 小动作
    blocks = re.split(r"\n### (IC-\d{3})[：:]", text)
    # blocks = ["<前言>", "IC-001", "<内容>", "IC-002", ...]
    for i in range(1, len(blocks), 2):
        ic_id = blocks[i].strip()
        body = blocks[i + 1] if i + 1 < len(blocks) else ""
        snap = snapshots.get(ic_id)
        if not snap:
            continue
        # 机制：取 "机制：" 后到下一个空行 / "入口句" 之前
        m = re.search(r"机制[：:]\s*(.+?)(?:\n\n|\n入口句)", body, re.S)
        if m and not snap.get("mechanism"):
            snap["mechanism"] = m.group(1).strip()
        # 入口句：在 "> " 行
        a = re.search(r"入口句[：:]\s*\n+>\s*(.+?)\n", body)
        if a and not snap.get("anchor"):
            snap["anchor"] = a.group(1).strip()
        # 小动作：取 "小动作：" 后到下方第一个 "**Pattern" 之间的有序列表
        s = re.search(r"小动作[：:]\s*\n+((?:\d+\..+\n?)+)", body)
        if s and not snap.get("micro_steps"):
            items = re.findall(r"\d+\.\s*(.+)", s.group(1))
            snap["micro_steps"] = [it.strip() for it in items if it.strip()]


def _build_card_snapshots(
    root: Path, rows: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """从 feedback rows 收集所有 target_id，去重后抽 snapshot。"""
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        tid = r.get("target_id")
        ttype = r.get("target_type")
        if not tid or ttype not in ("run", "card"):
            continue
        if tid in seen:
            continue
        snap = _extract_card_snapshot(root, ttype, tid)
        if snap:
            seen[tid] = snap
    _enrich_card_snapshots_from_v3(root, seen)
    return seen


def _extract_lexicon_version(text: str, lexicon_path: Path) -> tuple[str, str]:
    """返回 (base_version, next_version)。优先看文件名 v\\d+，回落 frontmatter。"""
    m = re.search(r"lexicon-v(\d+)\.md", lexicon_path.name)
    if m:
        n = int(m.group(1))
        return f"v{n}", f"v{n + 1}"
    m = re.search(r"^file:\s*pipeline-b-style-lexicon-v(\d+)\.md", text, re.M)
    if m:
        n = int(m.group(1))
        return f"v{n}", f"v{n + 1}"
    return "v?", "v?+1"


def _load_prompt() -> str:
    p = (
        Path(__file__).resolve().parent
        / "_prompts"
        / "synthesize-lexicon.prompt.md"
    )
    text = p.read_text(encoding="utf-8")
    # 简单去掉 frontmatter（用 --- ... --- 包裹的头部）
    if text.startswith("---"):
        sep = re.search(r"\n---\s*\n", text[3:])
        if sep:
            text = text[3 + sep.end() :].lstrip()
    return text


def _validate_proposal_shape(obj: Any) -> tuple[bool, str]:
    if not isinstance(obj, dict):
        return False, "根节点不是 object"
    for k in ("base_version", "next_version", "hypotheses", "patches"):
        if k not in obj:
            return False, f"缺少必备字段: {k}"
    if not isinstance(obj.get("hypotheses"), list):
        return False, "hypotheses 必须是数组"
    if not isinstance(obj.get("patches"), list):
        return False, "patches 必须是数组"
    return True, ""


def _check_anchor_match(
    proposal: dict[str, Any], lexicon_text: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把 anchor_text 找不到的 patch 移到 withheld，并打 reason；返回 (valid_patches, auto_withheld)。"""
    valid: list[dict[str, Any]] = []
    auto_withheld: list[dict[str, Any]] = []
    for patch in proposal.get("patches") or []:
        action = patch.get("action")
        anchor = patch.get("anchor_text") or ""
        if action == "append_to_section" and not anchor:
            # append_to_section 允许 anchor 为空：靠 section 切
            valid.append(patch)
            continue
        if not anchor:
            auto_withheld.append(
                {
                    "patch_id": patch.get("id"),
                    "section": patch.get("section"),
                    "reason": "anchor_text 为空且 action 非 append_to_section",
                }
            )
            continue
        if anchor in lexicon_text:
            valid.append(patch)
        else:
            auto_withheld.append(
                {
                    "patch_id": patch.get("id"),
                    "section": patch.get("section"),
                    "reason": f"anchor_text 在 lexicon 里字符串未命中 (前 40 字: {anchor[:40]!r})",
                }
            )
    return valid, auto_withheld


def _render_md(proposal: dict[str, Any], lexicon_path: Path) -> str:
    lines: list[str] = []
    lines.append(f"# Lexicon proposal · {proposal.get('base_version')} → {proposal.get('next_version')}")
    lines.append("")
    win = proposal.get("feedback_window") or {}
    lines.append(f"- 基准 lexicon：`{lexicon_path}`")
    lines.append(
        f"- feedback 窗口：{win.get('first_ts', '?')} → {win.get('last_ts', '?')}（{win.get('rows', '?')} 行）"
    )
    stats = proposal.get("meta_stats") or {}
    lines.append(f"- patches：{stats.get('patches_count', len(proposal.get('patches') or []))} 条")
    lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    for h in proposal.get("hypotheses") or []:
        lines.append(
            f"- **{h.get('id')}** · `{h.get('axis')}`：{h.get('text')} `evidence_rows={h.get('evidence_rows')}`"
        )
    lines.append("")
    lines.append("## Patches")
    lines.append("")
    for p in proposal.get("patches") or []:
        lines.append(f"### {p.get('id')} · {p.get('section')} · {p.get('action')}")
        lines.append("")
        if p.get("rationale"):
            lines.append(f"> {p.get('rationale')}")
            lines.append("")
        lines.append(f"- hypotheses: {p.get('hypotheses')}")
        lines.append(f"- evidence_rows: {p.get('evidence_rows')}")
        if p.get("position"):
            lines.append(f"- position: `{p.get('position')}`")
        lines.append("")
        if p.get("anchor_text"):
            lines.append("**anchor_text**：")
            lines.append("")
            lines.append("```")
            lines.append(str(p.get("anchor_text")))
            lines.append("```")
            lines.append("")
        lines.append("**new_content**：")
        lines.append("")
        lines.append("```")
        lines.append(str(p.get("new_content") or ""))
        lines.append("```")
        lines.append("")
    if proposal.get("withheld"):
        lines.append("## Withheld（未提的改动）")
        lines.append("")
        for w in proposal["withheld"]:
            lines.append(f"- {w.get('section')}：{w.get('reason')}")
        lines.append("")
    if proposal.get("_auto_withheld"):
        lines.append("## 自动 withheld（anchor_text 未命中 / 校验失败）")
        lines.append("")
        for w in proposal["_auto_withheld"]:
            lines.append(f"- patch `{w.get('patch_id')}` · {w.get('section')}：{w.get('reason')}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*由 `agents_runtime.synthesize_lexicon` 生成；apply 时按 `<ts>_proposal.json` 的 patches 走。*")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="读 feedback 产 lexicon patch 候选")
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-feedback", type=int, default=20)
    parser.add_argument("--since", type=str, default=None, help="ts >= 该 ISO 字符串")
    parser.add_argument("--model", type=str, default=_DEFAULT_REASONING)
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument(
        "--dry-run-no-llm",
        action="store_true",
        help="不调 LLM，写空 proposal（仅用于联调前端）",
    )
    args = parser.parse_args()

    root = _repo_root()
    feedback_path = args.feedback if args.feedback.is_absolute() else root / args.feedback
    lexicon_path = args.lexicon if args.lexicon.is_absolute() else root / args.lexicon
    out_dir = args.out if args.out.is_absolute() else root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_jsonl(feedback_path)
    rows = _filter_since(rows, args.since)
    if len(rows) < args.min_feedback:
        print(
            f"WARN: 仅 {len(rows)} 条 feedback (阈值 {args.min_feedback})；建议先攒到 ≥ {args.min_feedback} 再 synthesize",
            file=sys.stderr,
        )
        if not args.dry_run_no_llm:
            return 2

    if not lexicon_path.is_file():
        print(f"ERROR: lexicon 文件不存在 {lexicon_path}", file=sys.stderr)
        return 3
    lexicon_text = lexicon_path.read_text(encoding="utf-8")
    base_version, next_version = _extract_lexicon_version(lexicon_text, lexicon_path)

    # 装配 row_index（apply 时也按这个编号回看）
    rows_with_index = []
    for idx, r in enumerate(rows):
        item = dict(r)
        item["row_index"] = idx
        rows_with_index.append(item)

    card_snapshots = _build_card_snapshots(root, rows_with_index)
    print(f"[synthesize_lexicon] {len(rows_with_index)} rows · {len(card_snapshots)} cards · base={base_version}", file=sys.stderr)

    user_payload = {
        "feedback_rows": rows_with_index,
        "lexicon_current": lexicon_text,
        "card_snapshots": card_snapshots,
        "_hint": {
            "base_version": base_version,
            "next_version": next_version,
        },
    }

    if args.dry_run_no_llm:
        proposal = {
            "base_version": base_version,
            "next_version": next_version,
            "feedback_window": {
                "first_ts": rows_with_index[0]["ts"] if rows_with_index else "",
                "last_ts": rows_with_index[-1]["ts"] if rows_with_index else "",
                "rows": len(rows_with_index),
            },
            "hypotheses": [],
            "patches": [],
            "withheld": [],
            "meta_stats": {"patches_count": 0, "evidence_min_per_patch": 0, "anchor_match_check": "client_side"},
        }
    else:
        system_prompt = _load_prompt()
        try:
            proposal = call_json(
                system=system_prompt,
                user=json.dumps(user_payload, ensure_ascii=False),
                model=args.model,
                temperature=args.temperature,
                agent_id="synthesize-lexicon",
                debug_dir=str(out_dir / "_debug"),
            )
        except Exception as e:
            print(f"ERROR: LLM 调用失败 {e}", file=sys.stderr)
            return 4
        ok, msg = _validate_proposal_shape(proposal)
        if not ok:
            print(f"ERROR: proposal 不符 schema：{msg}", file=sys.stderr)
            return 5

    # anchor_text 字符串校验
    valid_patches, auto_withheld = _check_anchor_match(proposal, lexicon_text)
    proposal["patches"] = valid_patches
    if auto_withheld:
        proposal["_auto_withheld"] = auto_withheld
    proposal.setdefault("meta_stats", {})
    proposal["meta_stats"]["patches_count"] = len(valid_patches)

    # 兜底 feedback_window
    if "feedback_window" not in proposal or not isinstance(proposal["feedback_window"], dict):
        proposal["feedback_window"] = {
            "first_ts": rows_with_index[0]["ts"] if rows_with_index else "",
            "last_ts": rows_with_index[-1]["ts"] if rows_with_index else "",
            "rows": len(rows_with_index),
        }
    proposal.setdefault("base_version", base_version)
    proposal.setdefault("next_version", next_version)

    ts = _now_iso_compact()
    json_out = out_dir / f"{ts}_proposal.json"
    md_out = out_dir / f"{ts}_proposal.md"
    json_out.write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_out.write_text(_render_md(proposal, lexicon_path), encoding="utf-8")

    print(f"[synthesize_lexicon] 写 {json_out.relative_to(root)}", file=sys.stderr)
    print(f"[synthesize_lexicon] 写 {md_out.relative_to(root)}", file=sys.stderr)
    print(
        f"[synthesize_lexicon] patches={len(valid_patches)} · auto_withheld={len(auto_withheld)} · base={base_version} → next={next_version}",
        file=sys.stderr,
    )
    # 把 ts 打到 stdout 方便 shell 接管
    print(ts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
