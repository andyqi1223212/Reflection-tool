#!/usr/bin/env python3
"""
Round-2 trial：merge 子命令——读 Pipeline B + Judge 的 JSON，校验后写入 v3 md 并调用 export。

注意：本仓库 export_v3_chains.py 从 v3 markdown **全量**生成 data/chains.json，因此 merge 只追加 md，
不直接改 chains.json；export 后数据与 md 一致。

试运行结束后可将本文件迁到 tools/run_pipeline.py 并在 agents/README 中挂接。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
import export_v3_chains as _ev3  # noqa: E402

from jsonschema import Draft7Validator

from next_ic_id import next_ic_id_str, repo_root

INSERT_BEFORE = "## 3. 这版给产品的启发"


def _strip_card_payload(b_obj: dict) -> dict:
    out = {k: v for k, v in b_obj.items() if k != "_meta"}
    return out


def _card_to_markdown(card: dict, *, child_ic_ids: list[str] | None = None) -> str:
    cid = card["id"]
    title = card["title"]
    c = card["crystallization"]
    mechanism = c["mechanism"]
    anchor = c["anchor"]
    steps = c["micro_steps"]
    patterns = card["patterns"]
    axis = card["axis"]
    trig = card["chain"]["trigger"]
    questions = card["chain"]["questions"]

    lines: list[str] = [
        f"### {cid}：{title}",
        "",
        "**Crystallization**",
        "",
        f"机制：{mechanism}",
        "",
        "入口句：",
        "",
        f"> {anchor}",
        "",
        "小动作：",
        "",
    ]
    for i, s in enumerate(steps, start=1):
        lines.append(f"{i}. {s}")
    lines.append("")
    tags = " ".join(f"`{p}`" for p in patterns)
    lines.append(f"**Pattern tags**：{tags}")
    lines.append("")
    lines.append(f"**Axis**：`{axis}`")
    lines.append("")
    refs = card.get("source_refs")
    if refs:
        ref_line = " ".join(refs)
        lines.append(f"**Source refs**：{ref_line}")
        lines.append("")
    if child_ic_ids:
        kids = " ".join(f"`{c}`" for c in child_ic_ids)
        lines.append(f"**Meta 子卡**：{kids}")
        lines.append("")
    lines.append("<details>")
    lines.append("<summary>Trigger / 追问路径</summary>")
    lines.append("")
    lines.append(f"**Trigger**：{trig}")
    lines.append("")
    lines.append("**追问路径**：")
    lines.append("")
    for q in questions:
        lines.append(f"- {q}")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    lines.append("----")
    lines.append("")
    return "\n".join(lines)


def _validate_card(card: dict, schema: dict) -> None:
    v = Draft7Validator(schema)
    errs = sorted(v.iter_errors(card), key=lambda e: e.path)
    if errs:
        for e in errs:
            print(f"  {'/'.join(str(p) for p in e.path)}: {e.message}", file=sys.stderr)
        raise SystemExit(1)


def _payload_to_chain_card(payload: dict) -> dict:
    """B 的 full_card / meta_card → 可过 inquiry-chain schema 的卡对象。"""
    card = dict(payload)
    for k in ("output_kind", "target_ic_id", "update_entry", "meta_relation"):
        card.pop(k, None)
    return card


def _load_chain_ids(chains_path: Path) -> set[str]:
    data = json.loads(chains_path.read_text(encoding="utf-8"))
    chains = data.get("chains")
    if not isinstance(chains, list):
        raise SystemExit(f"[merge] invalid chains.json at {chains_path}")
    return {c["id"] for c in chains if isinstance(c, dict) and c.get("id")}


def _validate_update_entry(entry: dict, schema: dict) -> None:
    item_schema = schema["properties"]["updates"]["items"]
    v = Draft7Validator(item_schema)
    errs = sorted(v.iter_errors(entry), key=lambda e: e.path)
    if errs:
        for e in errs:
            print(
                f"  [update_entry] {'/'.join(str(p) for p in e.path)}: {e.message}",
                file=sys.stderr,
            )
        raise SystemExit(7)


def cmd_merge(args: argparse.Namespace) -> None:
    root = repo_root()
    b_path: Path = args.b
    j_path: Path = args.judge
    md_path: Path = args.md if args.md else root / "inquiry-chain-demo-v3-good-answer.md"
    chains_path: Path = args.chains if args.chains else root / "data" / "chains.json"
    schema_path = root / "data" / "inquiry-chain.schema.json"

    if not b_path.is_file():
        print(f"Missing B output: {b_path}", file=sys.stderr)
        raise SystemExit(1)
    if not j_path.is_file():
        print(f"Missing Judge output: {j_path}", file=sys.stderr)
        raise SystemExit(1)

    payload = _strip_card_payload(json.loads(b_path.read_text(encoding="utf-8")))
    judge = json.loads(j_path.read_text(encoding="utf-8"))

    verdict = judge.get("verdict")
    if verdict != "pass":
        print(f"[merge] aborted: judge verdict={verdict!r} (need pass)", file=sys.stderr)
        raise SystemExit(2)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    mode = args.mode

    if mode == "update":
        if payload.get("output_kind") != "update_entry":
            print(
                f"[merge] mode=update but B output_kind={payload.get('output_kind')!r} (need update_entry)",
                file=sys.stderr,
            )
            raise SystemExit(1)
        target_id = payload["target_ic_id"]
        update_entry = payload["update_entry"]
        print(f"[merge] mode=update target={target_id} (validate update_entry…)", file=sys.stderr)
        _validate_update_entry(update_entry, schema)
        new_frag = _ev3.update_entry_to_details_markdown(update_entry)
        md = md_path.read_text(encoding="utf-8")
        new_md = _ev3.append_update_entry_to_md(md, target_id, update_entry)
        if new_md is None:
            print(
                f"[merge] {target_id} not found in v3 md or card missing trailing ---/---- separator; abort",
                file=sys.stderr,
            )
            raise SystemExit(6)
        if args.dry_run:
            print("[merge] --dry-run: would append the following <details class=\"ic-update\"> block:", file=sys.stderr)
            print(new_frag, file=sys.stderr)
            print(f"[merge] --dry-run: would run: {sys.executable} tools/export_v3_chains.py --md {md_path}", file=sys.stderr)
            proto = root / "crystallization-prototype" / "index.html"
            print(f"✓ (dry-run) update 将追加到: {target_id}", file=sys.stderr)
            print(f"  UI: file://{proto.resolve()}", file=sys.stderr)
            return

        tmp_path = md_path.with_name(md_path.name + ".tmp.merge")
        tmp_path.write_text(new_md, encoding="utf-8")
        tmp_path.replace(md_path)
        print(f"[merge] appended update_entry to {target_id} in {md_path}", file=sys.stderr)

        export_script = root / "tools" / "export_v3_chains.py"
        r = subprocess.run([sys.executable, str(export_script), "--md", str(md_path)], cwd=str(root))
        if r.returncode != 0:
            print("[merge] export_v3_chains.py failed; you may need to revert md manually", file=sys.stderr)
            raise SystemExit(r.returncode)

        val = subprocess.run([sys.executable, str(root / "tools" / "validate_chains_json.py")], cwd=str(root))
        if val.returncode != 0:
            print("[merge] validate_chains_json.py reported errors", file=sys.stderr)

        proto = root / "crystallization-prototype" / "index.html"
        print(f"✓ update 已入库: {target_id}（已追加 1 条 update_entry）")
        print(f"  UI: file://{proto.resolve()}")
        return

    if mode == "meta":
        if payload.get("output_kind") != "meta_card":
            print(
                f"[merge] mode=meta but B output_kind={payload.get('output_kind')!r} (need meta_card)",
                file=sys.stderr,
            )
            raise SystemExit(1)
        meta_relation = payload.get("meta_relation") or {}
        child_ic_ids = list(meta_relation.get("child_ic_ids") or [])
        if not child_ic_ids:
            print("[merge] mode=meta requires meta_relation.child_ic_ids", file=sys.stderr)
            raise SystemExit(1)
        known = _load_chain_ids(chains_path)
        missing = [c for c in child_ic_ids if c not in known]
        if missing:
            print(
                f"[merge] child_ic_ids not in chains.json: {missing}",
                file=sys.stderr,
            )
            raise SystemExit(8)

        card = _payload_to_chain_card(payload)
        new_id = next_ic_id_str(chains_path)
        card["id"] = new_id
        if not card.get("created_at"):
            card["created_at"] = date.today().isoformat()

        print(
            f"[merge] mode=meta assigning id {new_id} children={child_ic_ids} (schema validate…)",
            file=sys.stderr,
        )
        _validate_card(card, schema)
        block = _card_to_markdown(card, child_ic_ids=child_ic_ids)
        if args.dry_run:
            print(
                "[merge] --dry-run: would append meta_card section before",
                INSERT_BEFORE,
                file=sys.stderr,
            )
            print(block)
            print(
                f"[merge] --dry-run: would run: {sys.executable} tools/export_v3_chains.py",
                file=sys.stderr,
            )
            proto = root / "crystallization-prototype" / "index.html"
            print(f"✓ (dry-run) 元锚卡将使用 id: {new_id}", file=sys.stderr)
            print(f"  UI: file://{proto.resolve()}", file=sys.stderr)
            return

        md = md_path.read_text(encoding="utf-8")
        if f"### {new_id}：" in md:
            print(f"[merge] md already contains {new_id}; abort", file=sys.stderr)
            raise SystemExit(4)
        marker = INSERT_BEFORE
        if marker not in md:
            print(f"[merge] md missing anchor {marker!r}; abort", file=sys.stderr)
            raise SystemExit(5)

        insertion = "\n" + block
        updated = md.replace(marker, insertion + "\n" + marker, 1)
        md_path.write_text(updated, encoding="utf-8")
        print(f"[merge] appended meta_card to {md_path}", file=sys.stderr)

        export_script = root / "tools" / "export_v3_chains.py"
        r = subprocess.run(
            [sys.executable, str(export_script), "--md", str(md_path)], cwd=str(root)
        )
        if r.returncode != 0:
            print(
                "[merge] export_v3_chains.py failed; you may need to revert md manually",
                file=sys.stderr,
            )
            raise SystemExit(r.returncode)

        val = subprocess.run(
            [sys.executable, str(root / "tools" / "validate_chains_json.py")],
            cwd=str(root),
        )
        if val.returncode != 0:
            print("[merge] validate_chains_json.py reported errors", file=sys.stderr)

        proto = root / "crystallization-prototype" / "index.html"
        print(f"✓ 元锚卡已入库: {new_id}（子卡 {len(child_ic_ids)} 张）")
        print(f"  UI: file://{proto.resolve()}")
        return

    # --- mode == new (default) ---
    card = _payload_to_chain_card(payload)
    new_id = next_ic_id_str(chains_path)

    card["id"] = new_id
    if not card.get("created_at"):
        card["created_at"] = date.today().isoformat()

    print(f"[merge] assigning id {new_id} (schema validate…)", file=sys.stderr)
    _validate_card(card, schema)

    block = _card_to_markdown(card)
    if args.dry_run:
        print("[merge] --dry-run: would append the following section before", INSERT_BEFORE, file=sys.stderr)
        print(block)
        print(f"[merge] --dry-run: would run: {sys.executable} tools/export_v3_chains.py", file=sys.stderr)
        proto = root / "crystallization-prototype" / "index.html"
        print(f"✓ (dry-run) 新卡将使用 id: {new_id}", file=sys.stderr)
        print(f"  UI: file://{proto.resolve()}", file=sys.stderr)
        return

    md = md_path.read_text(encoding="utf-8")
    if f"### {new_id}：" in md:
        print(f"[merge] md already contains {new_id}; abort", file=sys.stderr)
        raise SystemExit(4)
    marker = INSERT_BEFORE
    if marker not in md:
        print(f"[merge] md missing anchor {marker!r}; abort", file=sys.stderr)
        raise SystemExit(5)

    insertion = "\n" + block
    updated = md.replace(marker, insertion + "\n" + marker, 1)
    md_path.write_text(updated, encoding="utf-8")
    print(f"[merge] appended section to {md_path}", file=sys.stderr)

    export_script = root / "tools" / "export_v3_chains.py"
    r = subprocess.run([sys.executable, str(export_script), "--md", str(md_path)], cwd=str(root))
    if r.returncode != 0:
        print("[merge] export_v3_chains.py failed; you may need to revert md manually", file=sys.stderr)
        raise SystemExit(r.returncode)

    val = subprocess.run([sys.executable, str(root / "tools" / "validate_chains_json.py")], cwd=str(root))
    if val.returncode != 0:
        print("[merge] validate_chains_json.py reported errors", file=sys.stderr)

    proto = root / "crystallization-prototype" / "index.html"
    print(f"✓ 新卡已入库: {new_id}")
    print(f"  UI: file://{proto.resolve()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Round-2 pipeline helpers (trial)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("merge", help="Merge B JSON + Judge JSON into v3 md + export")
    m.add_argument("--b", type=Path, required=True, help="Pipeline B output JSON")
    m.add_argument("--judge", type=Path, required=True, help="Judge output JSON")
    m.add_argument("--md", type=Path, default=None, help="v3 markdown path")
    m.add_argument("--chains", type=Path, default=None, help="chains.json (for next id + duplicate check)")
    m.add_argument("--dry-run", action="store_true", help="Validate only; print section; do not write")
    m.add_argument(
        "--mode",
        choices=("new", "update", "meta"),
        default="new",
        help="new: full_card; update: update_entry; meta: meta_card（元锚 + child_ic_ids）",
    )
    m.set_defaults(func=cmd_merge)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
