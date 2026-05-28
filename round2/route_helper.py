#!/usr/bin/env python3
"""
Retrieval helper：读 question_md + data/chains.json，按字符 trigram 重叠排序 top-K，
输出 JSON（含 route_hint / confidence），供 Pipeline A 参考。

第一性原理与 CLI 形态见同目录 `round2/route_helper.spec.md` §1–§2.1。
不调 LLM、不写文件，仅 stdout 打印 JSON；stderr 仅 [debug] / FAIL。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RESPONSE_HEADING = re.compile(r"^#\s+.+\sresponse\s*$", re.IGNORECASE)
YOU_ASKED_HEADING = re.compile(r"^#\s*you\s+asked\s*$", re.IGNORECASE)
TITLE_SPLIT = re.compile(r"[，。、,.;:！？!?/／|\s]+")
TITLE_SUB_SPLIT = re.compile(r"[的与和]+")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\s\u3000]+", " ", text)
    text = re.sub(
        r"[、，。；：！？,.;:!?\"'`~（）()\[\]【】<>《》—\-_/\\|*#@%&=+]",
        " ",
        text,
    )
    return text.strip()


def char_trigrams(text: str) -> set[str]:
    text = normalize(text)
    if len(text) < 3:
        return set()
    return {text[i : i + 3] for i in range(len(text) - 2)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    u = a | b
    if not u:
        return 0.0
    return len(a & b) / len(u)


def overlap_coefficient(query: set[str], card: set[str]) -> float:
    if not card:
        return 0.0
    return len(query & card) / len(card)


def extract_question_text(md_path: Path) -> str:
    raw = md_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    skip_response = False
    parts: list[str] = []
    for line in lines:
        if line.strip() == "---":
            continue
        if RESPONSE_HEADING.match(line):
            skip_response = True
            continue
        if YOU_ASKED_HEADING.match(line):
            skip_response = False
            continue
        if skip_response:
            continue
        parts.append(line)
    return "\n".join(parts)


def extract_raw_answer_text(md_path: Path) -> str | None:
    raw = md_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    in_response = False
    parts: list[str] = []
    for line in lines:
        if RESPONSE_HEADING.match(line):
            in_response = True
            continue
        if YOU_ASKED_HEADING.match(line):
            in_response = False
            continue
        if not in_response:
            continue
        if line.strip() == "---":
            continue
        parts.append(line)
    text = "\n".join(parts).strip()
    return text if text else None


def _collect_title_fragments(title: str) -> list[str]:
    """2–8 字片段：先按标点/斜杠切，再对超长段按「的/与/和」二次切（仅 title，无第三方分词）。"""
    out: list[str] = []
    for seg in TITLE_SPLIT.split(title):
        s = seg.strip()
        if not s:
            continue
        if 2 <= len(s) <= 8:
            out.append(s)
            continue
        for sub in TITLE_SUB_SPLIT.split(s):
            t = sub.strip()
            if 2 <= len(t) <= 8:
                out.append(t)
    seen: set[str] = set()
    deduped: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped[:5]


def title_keywords(title: str) -> list[str]:
    return _collect_title_fragments(title)


def card_feature(card: dict) -> tuple[str, list[str]]:
    title = card.get("title") or ""
    chain = card.get("chain") or {}
    trigger = chain.get("trigger") or ""
    qs = chain.get("questions")
    if not isinstance(qs, list):
        qs = []
    q_join = " ".join(str(q) for q in qs)
    feature = f"{title} {trigger} {q_join}".strip()
    kws = title_keywords(str(title))
    return feature, kws


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    root = repo_root()
    ap = argparse.ArgumentParser(
        description="Char-trigram retrieval over chains.json; stdout JSON for Pipeline A."
    )
    ap.add_argument("--question", type=Path, required=True, help="Path to question_md")
    ap.add_argument(
        "--chains",
        type=Path,
        default=None,
        help="Path to chains.json (default: <repo>/data/chains.json)",
    )
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--update-high", type=float, default=0.40)
    ap.add_argument("--update-medium", type=float, default=0.13)
    ap.add_argument("--meta-min-cross-axis", type=float, default=0.10)
    ap.add_argument(
        "--include-raw-answer-excerpt",
        action="store_true",
        help="Append raw_answer_present + raw_answer_excerpt when raw segment exists",
    )
    args = ap.parse_args()

    qpath = args.question
    if not qpath.is_absolute():
        qpath = root / qpath
    if not qpath.is_file():
        fail(f"question_md not found: {qpath}")

    chains_path = args.chains if args.chains else root / "data" / "chains.json"
    if not chains_path.is_file():
        fail(f"chains.json not found: {chains_path}")

    question_body = extract_question_text(qpath)
    if not question_body.strip():
        fail("no user text extracted from question_md (empty after stripping response blocks)")

    q_norm_for_kw = normalize(question_body)
    q_trigrams = char_trigrams(question_body)

    data = json.loads(chains_path.read_text(encoding="utf-8"))
    chains = data.get("chains")
    if not isinstance(chains, list):
        fail("chains.json has no .chains list")

    rows: list[dict] = []
    for card in chains:
        if not isinstance(card, dict):
            continue
        cid = card.get("id")
        if not isinstance(cid, str):
            continue
        feature, kws = card_feature(card)
        c_trigrams = char_trigrams(feature)
        ov = overlap_coefficient(q_trigrams, c_trigrams)
        jac = jaccard(q_trigrams, c_trigrams)
        sc = round(ov * 0.85 + jac * 0.15, 4)
        ov_r = round(ov, 4)
        jac_r = round(jac, 4)

        matched: list[str] = []
        for kw in kws:
            nk = normalize(kw)
            if nk and nk in q_norm_for_kw and kw not in matched:
                matched.append(kw)
            if len(matched) >= 5:
                break

        chain = card.get("chain") or {}
        trigger_excerpt = str(chain.get("trigger") or "")

        rows.append(
            {
                "ic_id": cid,
                "title": str(card.get("title") or ""),
                "axis": str(card.get("axis") or ""),
                "patterns": card.get("patterns") if isinstance(card.get("patterns"), list) else [],
                "score": sc,
                "overlap": ov_r,
                "jaccard": jac_r,
                "trigger_excerpt": trigger_excerpt,
                "matched_keywords": matched,
            }
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    top_k = max(1, args.top_k)
    top = rows[:top_k]

    axes_in_top = {r["axis"] for r in top if r.get("axis")}
    cross_axis = len(axes_in_top) >= 2

    top1 = top[0]["score"] if top else 0.0
    top2 = top[1]["score"] if len(top) > 1 else 0.0

    uh, um, mm = args.update_high, args.update_medium, args.meta_min_cross_axis

    if top1 >= uh:
        hint = "update"
        confidence = "high"
        reason = (
            f"top1={top[0]['ic_id']} score={top1:.4f} ≥ update_high={uh} → update, high confidence"
        )
    elif top1 >= um:
        hint = "update"
        confidence = "medium"
        reason = (
            f"top1={top[0]['ic_id']} score={top1:.4f} ∈ [update_medium={um}, update_high={uh}) "
            "→ update, medium（A 须复核 top-3）"
        )
    elif cross_axis and top2 >= mm:
        hint = "meta"
        confidence = "medium"
        reason = (
            f"top-K 含 ≥2 种 axis（cross_axis）且 top2 score={top2:.4f} ≥ meta_min_cross_axis={mm} "
            f"→ meta；top1={top[0]['ic_id']} score={top1:.4f}"
        )
    else:
        hint = "new"
        if top1 < mm:
            confidence = "high"
            reason = (
                f"top1={top[0]['ic_id']} score={top1:.4f} < update_medium={um} 且未触发 meta 分支；"
                f"top1 < meta_min_cross_axis={mm} → new, high confidence"
            )
        else:
            confidence = "low"
            reason = (
                f"top1={top[0]['ic_id']} score={top1:.4f} < update_medium={um}，"
                f"meta 未满足（cross_axis={cross_axis} 或 top2={top2:.4f} < {mm}）→ new, low confidence"
            )

    rel_q = str(args.question)
    if not Path(args.question).is_absolute():
        rel_q = str(Path(args.question).as_posix())

    q_ex_base = question_body.strip()
    question_excerpt = q_ex_base[:240].strip()

    out: dict = {
        "question_md": rel_q,
        "question_excerpt": question_excerpt,
        "candidates": top,
        "route_hint": hint,
        "confidence": confidence,
        "route_hint_reason": reason[:240],
        "thresholds": {
            "update_high": uh,
            "update_medium": um,
            "meta_min_cross_axis": mm,
        },
    }

    if args.include_raw_answer_excerpt:
        raw_txt = extract_raw_answer_text(qpath)
        out["raw_answer_present"] = bool(raw_txt)
        if raw_txt:
            out["raw_answer_excerpt"] = raw_txt[:1200]

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
