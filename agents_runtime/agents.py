from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .context_builder import build_context
from .loader import load_prompt
from .llm_client import _DEFAULT_CHAT, _DEFAULT_REASONING, call_json


def _strip_meta(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if k != "_meta"}


def run_a(
    question_md_path: str,
    *,
    route_helper_output: dict[str, Any] | None = None,
    fewshot: list[str] | None = None,
    debug_dir: str | None = None,
) -> dict[str, Any]:
    prompt = load_prompt("pipeline-a-diagnose")
    inputs: dict[str, Any] = {
        "question_md": question_md_path,
        "route_helper_output": route_helper_output or {},
        "v3_fewshot": fewshot or [],
    }
    user = build_context(prompt, inputs)
    return call_json(
        system=prompt.body,
        user=user,
        model=_DEFAULT_REASONING,
        temperature=0.0,
        agent_id=prompt.agent_id,
        debug_dir=debug_dir,
    )


def run_b(
    a_output: dict[str, Any],
    *,
    existing_card: dict[str, Any] | None = None,
    fewshot: list[str] | None = None,
    lexicon_path: str | None = None,
    debug_dir: str | None = None,
) -> dict[str, Any]:
    """fewshot 预留与 Phase 5 对齐；B 当前 frontmatter 不消费 example_set。"""
    _ = fewshot
    prompt = load_prompt("pipeline-b-style")
    if lexicon_path:
        root = Path(__file__).resolve().parent.parent
        lp = Path(lexicon_path)
        if not lp.is_absolute():
            lp = (root / lp).resolve()
        rel = str(lp.relative_to(root)) if lp.is_relative_to(root) else str(lp)
        for spec in prompt.inputs:
            if spec.get("name") == "style_lexicon":
                spec["source"] = rel
                break
    d = _strip_meta(dict(a_output))
    if "route" not in d:
        d = {**d, "route": "new"}
    inputs: dict[str, Any] = {
        "pipeline_a_draft": d,
        "existing_card_json": existing_card if d.get("route") == "update" else {},
    }
    user = build_context(prompt, inputs)
    return call_json(
        system=prompt.body,
        user=user,
        model=_DEFAULT_CHAT,
        temperature=0.3,
        agent_id=prompt.agent_id,
        debug_dir=debug_dir,
    )


def run_judge(
    b_output: dict[str, Any],
    route_context: dict[str, Any],
    *,
    existing_card: dict[str, Any] | None = None,
    fewshot: list[str] | None = None,
    debug_dir: str | None = None,
) -> dict[str, Any]:
    prompt = load_prompt("judge")
    bd = _strip_meta(dict(b_output))
    rc = dict(route_context)
    route = rc.get("route", bd.get("route", "new"))
    inputs: dict[str, Any] = {
        "b_output": bd,
        "route_context": rc,
        "existing_card_json": existing_card if route == "update" else {},
        "v3_anchor": fewshot or [],
    }
    user = build_context(prompt, inputs)
    return call_json(
        system=prompt.body,
        user=user,
        model=_DEFAULT_REASONING,
        temperature=0.0,
        agent_id=prompt.agent_id,
        debug_dir=debug_dir,
    )


def _load_json(path: str) -> dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise SystemExit(f"JSON 根须为 object: {path}")
    return obj


def _cli(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(prog="python -m agents_runtime.agents")
    ap.add_argument("command", choices=["run_a", "run_b", "run_judge"])
    ap.add_argument(
        "paths",
        nargs="*",
        help=(
            "run_a: question_md [route_helper.json]；"
            "run_b: a.json [existing.json]；"
            "run_judge: b.json route.json [existing.json]"
        ),
    )
    ap.add_argument("--debug-dir", default=None, help="parse 失败时写入 raw 文本的目录（默认 ./ _debug）")
    args = ap.parse_args(argv)

    if args.command == "run_a":
        if len(args.paths) < 1:
            ap.error("run_a 至少需要 question_md 路径；可选第二个参数：route_helper 的 stdout JSON 文件")
        rh: dict[str, Any] | None = None
        if len(args.paths) > 1:
            rh = _load_json(args.paths[1])
        out = run_a(args.paths[0], route_helper_output=rh, debug_dir=args.debug_dir)
    elif args.command == "run_b":
        if len(args.paths) < 1:
            ap.error("run_b 至少需要 a_output.json")
        a_out = _load_json(args.paths[0])
        existing = _load_json(args.paths[1]) if len(args.paths) > 1 else None
        out = run_b(a_out, existing_card=existing, debug_dir=args.debug_dir)
    else:
        if len(args.paths) < 2:
            ap.error("run_judge 需要 b_output.json route_context.json [existing_card.json]")
        b_out = _load_json(args.paths[0])
        r_ctx = _load_json(args.paths[1])
        existing = _load_json(args.paths[2]) if len(args.paths) > 2 else None
        out = run_judge(b_out, r_ctx, existing_card=existing, debug_dir=args.debug_dir)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
