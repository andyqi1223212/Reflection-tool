#!/usr/bin/env python3
"""
Parse inquiry-chain-demo-v3-good-answer.md → data/chains.json + crystallization-prototype/chains.data.js

Stdlib only. Run schema validation separately:
  venv/bin/python tools/validate_chains_json.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD = ROOT / "inquiry-chain-demo-v3-good-answer.md"
OUT_JSON = ROOT / "data" / "chains.json"
OUT_EMBED = ROOT / "crystallization-prototype" / "chains.data.js"

HEADER_RE = re.compile(r"^### (IC-\d{3})：(.+)$", re.MULTILINE)
PATTERNS_LINE_RE = re.compile(r"\*\*Pattern tags\*\*[：:]\s*((?:`P-[A-Z]+(?:-[A-Z]+)?`\s*)+)")
AXIS_RE = re.compile(r"\*\*Axis\*\*[：:]\s*`(judgment|attention)`")
SOURCE_LINE_RE = re.compile(r"\*\*Source refs\*\*[：:]\s*(.+)$", re.MULTILINE)
REF_TOKEN_RE = re.compile(r"\b([A-Z]\d{2})\b")

UPDATES_REGION_RE = re.compile(
    r"<!--\s*BEGIN UPDATES\s*-->(.*?)<!--\s*END UPDATES\s*-->",
    re.DOTALL | re.IGNORECASE,
)
IC_UPDATE_DETAILS_RE = re.compile(
    r"<details\s+class=\"ic-update\"[^>]*>(.*?)</details>",
    re.DOTALL | re.IGNORECASE,
)
UPDATE_SUMMARY_DATE_RE = re.compile(
    r"<summary>\s*更新\s+(\d{4}-\d{2}-\d{2})\s*</summary>",
    re.IGNORECASE,
)


def _split_cards(md: str) -> list[tuple[str, str, str]]:
    """Return list of (id, title, body_chunk)."""
    matches = list(HEADER_RE.finditer(md))
    out: list[tuple[str, str, str]] = []
    for i, m in enumerate(matches):
        cid = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        out.append((cid, title, md[start:end]))
    return out


def update_entry_to_details_markdown(entry: dict) -> str:
    """Serialize one schema `updates[]` item to v3 md `<details class=\"ic-update\">` block (no BEGIN/END markers)."""
    dt = entry["updated_at"]
    pr = entry["patch_reasoning"].replace("\n", " ").strip()
    lines: list[str] = [
        '<details class="ic-update">',
        f"<summary>更新 {dt}</summary>",
        "",
        f"> patch_reasoning：{pr}",
        "",
    ]
    cry = entry.get("crystallization") or {}
    if cry.get("mechanism"):
        lines.append(f"**新增机制**：{cry['mechanism']}")
        lines.append("")
    if cry.get("anchor"):
        lines.extend(["**新增入口句**：", "", f"> {cry['anchor']}", ""])
    steps = cry.get("micro_steps")
    if steps:
        lines.append("**新增小动作**：")
        lines.append("")
        for i, s in enumerate(steps, start=1):
            lines.append(f"{i}. {s}")
        lines.append("")
    if entry.get("patterns_added"):
        tags = " ".join(f"`{p}`" for p in entry["patterns_added"])
        lines.append(f"**新增 patterns**：{tags}")
        lines.append("")
    if entry.get("source_refs_added"):
        lines.append(f"**新增 source_refs**：{' '.join(entry['source_refs_added'])}")
        lines.append("")
    if entry.get("questions_appended"):
        lines.append("**追加问题**：")
        lines.append("")
        for q in entry["questions_appended"]:
            lines.append(f"- {q}")
        lines.append("")
    if entry.get("trigger_addendum"):
        lines.append(f"**trigger 补充**：{entry['trigger_addendum']}")
        lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def append_update_entry_to_md(md: str, target_ic_id: str, entry: dict) -> str | None:
    """
    Append one update_entry as md inside the target card's <!-- BEGIN/END UPDATES --> region,
    before that card's trailing ---- separator line. Returns None if target card or separator not found.
    """
    matches = list(HEADER_RE.finditer(md))
    idx: int | None = None
    for i, m in enumerate(matches):
        if m.group(1) == target_ic_id:
            idx = i
            break
    if idx is None:
        return None
    start = matches[idx].start()
    end = matches[idx + 1].start() if idx + 1 < len(matches) else len(md)
    before = md[:start]
    card = md[start:end]
    after = md[end:]
    pos = -1
    for sep in ("\n---\n", "\n----\n"):
        p = card.rfind(sep)
        if p >= 0:
            pos = p
            break
    if pos < 0:
        return None
    head = card[:pos]
    trail = card[pos:]
    frag = update_entry_to_details_markdown(entry)
    marker_begin = "<!-- BEGIN UPDATES -->"
    marker_end = "<!-- END UPDATES -->"
    if marker_begin in head and marker_end in head:
        ei = head.index(marker_end)
        head = head[:ei].rstrip() + "\n\n" + frag + "\n\n" + head[ei:]
    else:
        insert = f"\n\n{marker_begin}\n\n{frag}\n\n{marker_end}\n"
        head = head.rstrip() + insert
    return before + head + trail + after


def _parse_ic_update_inner(inner: str) -> dict:
    """Parse markdown body inside `<details class=\"ic-update\">` (inner HTML, no outer tags)."""
    inner_st = inner.strip()
    sm = UPDATE_SUMMARY_DATE_RE.search(inner_st)
    if not sm:
        raise ValueError("ic-update: missing <summary>更新 YYYY-MM-DD</summary>")
    updated_at = sm.group(1)
    rest = inner_st[sm.end() :].strip()
    pr_m = re.match(r">\s*patch_reasoning[：:]\s*(.+?)(?=\n\n\*\*|\n\n$|\Z)", rest, re.DOTALL)
    if not pr_m:
        raise ValueError("ic-update: missing > patch_reasoning line")
    patch_reasoning = pr_m.group(1).strip()
    tail = rest[pr_m.end() :].strip()

    out: dict = {"updated_at": updated_at, "patch_reasoning": patch_reasoning}
    cry: dict = {}

    mech_m = re.search(r"^\*\*新增机制\*\*[：:]\s*(.+)$", tail, re.MULTILINE)
    if mech_m:
        cry["mechanism"] = mech_m.group(1).strip()

    anch_sec = re.search(
        r"\*\*新增入口句\*\*[：:]*\s*\n+\s*>\s*(.+?)(?=\n\n\*\*|\Z)",
        tail,
        re.DOTALL,
    )
    if anch_sec:
        cry["anchor"] = anch_sec.group(1).strip()

    micro_m = re.search(
        r"\*\*新增小动作\*\*[：:]*\s*\n+((?:\d+\.\s*.+\n?)+)",
        tail,
        re.MULTILINE,
    )
    if micro_m:
        raw_steps = re.findall(r"^\d+\.\s*(.+)$", micro_m.group(1), re.MULTILINE)
        steps = [s.strip() for s in raw_steps]
        if steps:
            cry["micro_steps"] = steps

    if cry:
        out["crystallization"] = cry

    pm = re.search(r"\*\*新增 patterns\*\*[：:]\s*((?:`P-[A-Z]+(?:-[A-Z]+)?`\s*)+)", tail)
    if pm:
        out["patterns_added"] = re.findall(r"`(P-[A-Z]+(?:-[A-Z]+)?)`", pm.group(1))

    srm = re.search(r"\*\*新增 source_refs\*\*[：:]\s*(.+)$", tail, re.MULTILINE)
    if srm:
        line = srm.group(1).strip()
        out["source_refs_added"] = REF_TOKEN_RE.findall(line) or [w for w in line.split() if w]

    qm = re.search(r"\*\*追加问题\*\*[：:]*\s*\n+((?:-\s*.+\n?)+)", tail)
    if qm:
        qs = []
        for line in qm.group(1).split("\n"):
            line = line.strip()
            if line.startswith("- "):
                qs.append(line[2:].strip())
        if qs:
            out["questions_appended"] = qs

    tm = re.search(r"\*\*trigger 补充\*\*[：:]\s*(.+)$", tail, re.MULTILINE)
    if tm:
        out["trigger_addendum"] = tm.group(1).strip()

    return out


def _parse_updates_from_chunk(chunk: str) -> list[dict]:
    m = UPDATES_REGION_RE.search(chunk)
    if not m:
        return []
    region = m.group(1)
    blocks = IC_UPDATE_DETAILS_RE.findall(region)
    out: list[dict] = []
    for b in blocks:
        out.append(_parse_ic_update_inner(b))
    return out


def _parse_card(cid: str, title: str, chunk: str, created_at: str) -> dict:
    mech_m = re.search(r"^机制：(.+)$", chunk, re.MULTILINE)
    if not mech_m:
        raise ValueError(f"{cid}: missing 机制")
    mechanism = mech_m.group(1).strip()

    anchor_m = re.search(r"入口句：\s*\n+\s*>\s*(.+)", chunk)
    if not anchor_m:
        raise ValueError(f"{cid}: missing 入口句 blockquote")
    anchor = anchor_m.group(1).strip()

    micro_m = re.search(r"小动作：\s*\n((?:\d+\.\s*.+\n?)+)", chunk)
    if not micro_m:
        raise ValueError(f"{cid}: missing 小动作")
    raw_steps = re.findall(r"^\d+\.\s*(.+)$", micro_m.group(1), re.MULTILINE)
    micro_steps = [s.strip() for s in raw_steps]
    if not micro_steps:
        raise ValueError(f"{cid}: no micro_steps")

    pm = PATTERNS_LINE_RE.search(chunk)
    if not pm:
        raise ValueError(f"{cid}: missing Pattern tags")
    patterns = re.findall(r"`(P-[A-Z]+(?:-[A-Z]+)?)`", pm.group(1))
    if len(patterns) != len(set(patterns)):
        raise ValueError(f"{cid}: duplicate patterns")
    if not patterns:
        raise ValueError(f"{cid}: empty patterns")

    am = AXIS_RE.search(chunk)
    if not am:
        raise ValueError(f"{cid}: missing Axis")
    axis = am.group(1)

    source_refs: list[str] = []
    sm = SOURCE_LINE_RE.search(chunk)
    if sm:
        source_refs = REF_TOKEN_RE.findall(sm.group(1))

    det = re.search(r"<details>(.*?)</details>", chunk, re.DOTALL)
    if not det:
        raise ValueError(f"{cid}: missing <details>")
    inner = det.group(1)
    if "**追问路径**" not in inner:
        raise ValueError(f"{cid}: missing 追问路径 in details")
    trig_part, q_part = inner.split("**追问路径**", 1)
    trig_m = re.search(r"\*\*Trigger\*\*[：:]\s*(.*)", trig_part, re.DOTALL)
    if not trig_m:
        raise ValueError(f"{cid}: missing Trigger")
    trigger = trig_m.group(1).strip()
    questions = []
    for line in q_part.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            questions.append(line[2:].strip())
    if len(questions) < 2:
        raise ValueError(f"{cid}: need ≥2 questions, got {len(questions)}")

    obj = {
        "id": cid,
        "title": title,
        "patterns": patterns,
        "axis": axis,
        "crystallization": {
            "mechanism": mechanism,
            "anchor": anchor,
            "micro_steps": micro_steps,
        },
        "chain": {"trigger": trigger, "questions": questions},
        "created_at": created_at,
    }
    if source_refs:
        obj["source_refs"] = source_refs
    updates = _parse_updates_from_chunk(chunk)
    if updates:
        obj["updates"] = updates
    return obj


def export(md_path: Path, dry_run: bool) -> dict:
    md = md_path.read_text(encoding="utf-8")
    created_at = date.today().isoformat()
    cards = []
    for cid, title, chunk in _split_cards(md):
        cards.append(_parse_card(cid, title, chunk, created_at))
    cards.sort(key=lambda c: c["id"])
    if len(cards) < 1:
        print("[warn] no cards parsed", file=sys.stderr)
    else:
        print(f"[info] exported {len(cards)} chains", file=sys.stderr)

    payload = {
        "meta": {
            "exported_from": str(md_path.relative_to(ROOT)),
            "schema": "data/inquiry-chain.schema.json (crystallization-schema-v0 §3)",
            "generated_at": created_at,
            "utc_hint": date.today().strftime("%Y-%m-%d"),
        },
        "chains": cards,
    }

    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    OUT_EMBED.parent.mkdir(parents=True, exist_ok=True)
    embed_body = json.dumps(payload, ensure_ascii=False)
    OUT_EMBED.write_text(
        "// AUTO-GENERATED by tools/export_v3_chains.py — edit v3 md + re-run export\n"
        f"window.__CHAINS_BOOTSTRAP__ = {embed_body};\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT_JSON}", file=sys.stderr)
    print(f"Wrote {OUT_EMBED}", file=sys.stderr)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Export v3 Inquiry Chain markdown to JSON + embedded JS")
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    md_path = args.md if args.md.is_absolute() else (ROOT / args.md)
    md_path = md_path.resolve()
    if not md_path.is_file():
        print(f"Missing {md_path}", file=sys.stderr)
        sys.exit(1)
    export(md_path, args.dry_run)


if __name__ == "__main__":
    main()
