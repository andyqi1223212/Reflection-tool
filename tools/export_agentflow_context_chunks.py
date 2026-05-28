#!/usr/bin/env python3
"""
从 agents_runtime 实际装配逻辑导出 A/B/Judge 上下文审阅块。
单一事实来源：agent第二轮/*.prompt.md frontmatter + build_context()。

用法（仓库根）:
  venv/bin/python3 tools/export_agentflow_context_chunks.py
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "pipeline-b-context-curator"
OUT_JS = OUT_DIR / "chunks.data.js"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents_runtime.context_builder import (  # noqa: E402
    _extract_bcfh_block,
    _extract_cjk_section,
    build_context,
    extract_doc_sections,
)
from agents_runtime.loader import load_prompt  # noqa: E402

PROMPT_PATHS = {
    "pipeline-a-diagnose": "agent第二轮/pipeline-a-diagnose.prompt.md",
    "pipeline-b-style": "agent第二轮/pipeline-b-style.prompt.md",
    "judge": "agent第二轮/judge.prompt.md",
}

DEFAULT_QUESTION_MD = "外部source/球场垃圾话应对策略.md"


def _split_prompt_body(body: str) -> list[tuple[str, str]]:
    stop = re.search(r"^## Notes\b", body, flags=re.M)
    if stop:
        body = body[: stop.start()]
    parts: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in body.splitlines(keepends=True):
        if re.match(r"^## ", line):
            if current_lines:
                parts.append((current_title, "".join(current_lines)))
            current_title = line.strip().removeprefix("## ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        parts.append((current_title, "".join(current_lines)))
    return parts


def _system_body_text(prompt: Any) -> str:
    return "\n".join(block for _, block in _split_prompt_body(prompt.body))


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _first_json(paths: list[str]) -> dict[str, Any] | None:
    for rel in paths:
        p = ROOT / rel
        if p.is_file():
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                return obj
    return None


def _extract_v3_cards(*ic_ids: str) -> list[str]:
    v3 = _read("inquiry-chain-demo-v3-good-answer.md")
    out: list[str] = []
    for ic in ic_ids:
        m = re.search(
            rf"(### {re.escape(ic)}[\s\S]*?)(?=\n### IC-|\n---\n### IC-|\Z)",
            v3,
        )
        if m:
            out.append(m.group(1).strip())
    return out


@dataclass
class ChunkBuilder:
    pipeline_id: str
    prompt_rel: str
    order: int = 0
    chunks: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.chunks = []


def _add_chunk(
    cb: ChunkBuilder,
    *,
    cid: str,
    layer: str,
    group: str,
    label: str,
    content: str,
    source: str,
    default_on: bool,
    status: str,
    input_name: str = "",
    overlap_tags: list[str] | None = None,
    note: str = "",
) -> None:
    if layer == "system":
        stored = content.strip() + "\n"
        char_count = len(stored)
    else:
        # user 块正文不含 build_context 块尾 \\n；重组时由 _reconstruct_user_from_chunks 追加
        stored = content
        char_count = len(content) + 1
    assert cb.chunks is not None
    cb.chunks.append(
        {
            "id": cid,
            "pipelineId": cb.pipeline_id,
            "layer": layer,
            "group": group,
            "label": label,
            "source": source,
            "content": stored,
            "chars": char_count,
            "defaultOn": default_on,
            "order": cb.order,
            "status": status,
            "inputName": input_name,
            "overlapTags": overlap_tags or [],
            "note": note,
            "runtime": "yes" if status == "active" else "no",
        }
    )
    cb.order += 1


def _content_for_spec(prompt: Any, spec: dict[str, Any]) -> str:
    typ = spec.get("type", "")
    name = str(spec.get("name", ""))
    if typ == "doc_full":
        from agents_runtime.context_builder import _read_text_file

        return _read_text_file(str(spec["source"]), field_name=name, prompt=prompt)
    if typ == "doc_section_set":
        return extract_doc_sections(
            str(spec["source"]),
            [str(s) for s in spec.get("sections") or []],
            field_name=name,
            prompt=prompt,
        )
    return ""


def _strip_excerpt_wrapper(text: str) -> str:
    return re.sub(r"^### 摘录区块:.*?\n\n", "", text, count=1, flags=re.S)


def _build_system_chunks(cb: ChunkBuilder, prompt: Any) -> None:
    for title, block in _split_prompt_body(prompt.body):
        tid = re.sub(r"\W+", "-", title)[:48].strip("-").lower() or "intro"
        note = ""
        if "few" in title.lower():
            note = "占位说明（非旧版长 fewshot）" if cb.pipeline_id == "pipeline-b-style" else ""
        _add_chunk(
            cb,
            cid=f"{cb.pipeline_id}.system.{tid}",
            layer="system",
            group="① 正在使用 · system",
            label=f"## {title}",
            content=block,
            source=cb.prompt_rel,
            default_on=True,
            status="active",
            note=note,
        )


def _build_inputs_from_frontmatter(
    cb: ChunkBuilder, prompt: Any, sample_values: dict[str, Any]
) -> set[str]:
    """按 frontmatter 生成 active user 块；返回已覆盖的 input name。"""
    covered: set[str] = set()
    prefix = cb.pipeline_id.replace("pipeline-", "").replace("-style", "-b")[:2]
    if cb.pipeline_id == "pipeline-a-diagnose":
        prefix = "a"
    elif cb.pipeline_id == "pipeline-b-style":
        prefix = "b"
    elif cb.pipeline_id == "judge":
        prefix = "judge"

    for spec in prompt.inputs:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", ""))
        typ = spec.get("type", "")
        covered.add(name)

        if typ == "markdown_file":
            path = sample_values.get(name)
            if not path:
                raise ValueError(f"{cb.pipeline_id}: 缺少 sample {name}")
            from agents_runtime.context_builder import _read_text_file

            content = _read_text_file(str(path), field_name=name, prompt=prompt)
            _add_chunk(
                cb,
                cid=f"{prefix}.user.{name}",
                layer="user",
                group="① 正在使用 · user",
                label=f"{name} ← {Path(str(path)).name}",
                content=content,
                source=str(path),
                default_on=True,
                status="active",
                input_name=name,
                note=(spec.get("description") or "")[:180],
            )
            continue

        if typ == "json":
            val = sample_values.get(name)
            if val is None:
                val = {}
            if isinstance(val, str):
                body = val
            else:
                body = json.dumps(val, ensure_ascii=False, indent=2)
            _add_chunk(
                cb,
                cid=f"{prefix}.user.{name}",
                layer="user",
                group="① 正在使用 · user",
                label=name,
                content=body,
                source="（运行时 JSON）",
                default_on=True,
                status="active",
                input_name=name,
                note=(spec.get("description") or "")[:180],
            )
            continue

        if typ == "example_set":
            items = sample_values.get(name) or []
            if not isinstance(items, list):
                items = []
            for i, block in enumerate(items):
                if not isinstance(block, str):
                    continue
                _add_chunk(
                    cb,
                    cid=f"{prefix}.user.{name}.{i}",
                    layer="user",
                    group="① 正在使用 · user",
                    label=f"{name}[{i}]",
                    content=block,
                    source=str(spec.get("source", "v3")),
                    default_on=True,
                    status="active",
                    input_name=name,
                    note=str(spec.get("count", "")),
                )
            if not items:
                _add_chunk(
                    cb,
                    cid=f"{prefix}.user.{name}.empty",
                    layer="user",
                    group="① 正在使用 · user",
                    label=f"{name}（空列表，与 orchestrate fewshot=[] 一致）",
                    content="(未提供 example_set；调用方可传 fewshot 列表)",
                    source="",
                    default_on=True,
                    status="active",
                    input_name=name,
                    note="orchestrate 默认 fewshot=[]",
                )
            continue

        if typ == "doc_full":
            raw = _content_for_spec(prompt, spec)
            _add_chunk(
                cb,
                cid=f"{prefix}.user.{name}",
                layer="user",
                group="① 正在使用 · user",
                label=f"{name} ← {Path(str(spec.get('source'))).name}",
                content=raw,
                source=str(spec.get("source")),
                default_on=True,
                status="active",
                input_name=name,
            )
            continue

        if typ == "doc_section_set":
            src = str(spec.get("source", ""))
            for sec in spec.get("sections") or []:
                block = _strip_excerpt_wrapper(
                    extract_doc_sections(
                        src, [str(sec)], field_name=name, prompt=prompt
                    )
                )
                sid = re.sub(r"[\s§]+", "-", str(sec)).strip("-")
                _add_chunk(
                    cb,
                    cid=f"{prefix}.user.{name}.{sid}",
                    layer="user",
                    group="① 正在使用 · user",
                    label=f"{name} · {sec}",
                    content=block,
                    source=src,
                    default_on=True,
                    status="active",
                    input_name=name,
                )
    return covered


def _system_chunked_text(prompt: Any) -> str:
    """与导出 system 块一致：按 ## 分节、strip 后各加 \\n，不含 ## Notes 之后正文。"""
    return "".join(block.strip() + "\n" for _, block in _split_prompt_body(prompt.body))


def _reconstruct_user_from_chunks(
    prompt: Any, active: list[dict[str, Any]]
) -> str:
    """按 build_context 规则从 active user 块重组。"""
    recon_parts: list[str] = []
    for spec in prompt.inputs:
        if not isinstance(spec, dict):
            continue
        name = str(spec.get("name", ""))
        typ = spec.get("type", "")
        recon_parts.append(f"# {name}\n")
        if typ == "doc_section_set":
            src = spec.get("source")
            secs = spec.get("sections") or []
            recon_parts.append(
                extract_doc_sections(
                    str(src), [str(s) for s in secs], field_name=name, prompt=prompt
                )
            )
        elif typ == "doc_full":
            recon_parts.append(_content_for_spec(prompt, spec))
        elif typ == "example_set":
            parts = [
                c["content"]
                for c in sorted(active, key=lambda x: x["order"])
                if c["layer"] == "user" and c.get("inputName") == name
            ]
            if len(parts) > 1:
                joined = "\n\n---\n\n".join(p.strip() for p in parts)
            elif len(parts) == 1:
                joined = parts[0].strip()
            else:
                joined = "(未提供 example_set；调用方可传 fewshot 列表)"
            if not joined.strip():
                joined = "(未提供 example_set；调用方可传 fewshot 列表)"
            recon_parts.append(joined)
        else:
            parts = [
                c["content"]
                for c in sorted(active, key=lambda x: x["order"])
                if c["layer"] == "user" and c.get("inputName") == name
            ]
            recon_parts.append("".join(parts))
        recon_parts.append("\n")
    return "".join(recon_parts).rstrip() + "\n"


def _crosscheck(
    pipeline_id: str,
    prompt: Any,
    sample_inputs: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """用 build_context / prompt.body 实测 vs 导出块重组，输出 crosscheck 报告。"""
    built_user = build_context(prompt, sample_inputs)
    built_system_runtime = prompt.body
    built_system_chunked = _system_chunked_text(prompt)

    active = [c for c in chunks if c.get("status") == "active"]
    recon_system = "".join(
        c["content"] for c in sorted(active, key=lambda x: x["order"]) if c["layer"] == "system"
    )
    recon_user = _reconstruct_user_from_chunks(prompt, active)

    issues: list[str] = []
    sys_ok = recon_system == built_system_chunked
    if not sys_ok:
        issues.append(
            f"system(chunked) 不一致: chunked={len(built_system_chunked)} recon={len(recon_system)}"
        )
    user_ok = recon_user == built_user
    if not user_ok:
        issues.append(
            f"user 不一致: build_context={len(built_user)} recon={len(recon_user)}"
        )

    input_names = {s["name"] for s in prompt.inputs if isinstance(s, dict) and s.get("name")}
    active_inputs = {c.get("inputName") for c in active if c.get("inputName")}
    missing_chunks = sorted(input_names - active_inputs)
    if missing_chunks:
        issues.append(f"frontmatter input 无对应 active 块: {missing_chunks}")

    notes_tail = len(built_system_runtime) - len(built_system_chunked)
    return {
        "ok": sys_ok and user_ok and not missing_chunks,
        "systemMatch": sys_ok,
        "userMatch": user_ok,
        "measuredSystem": len(built_system_chunked),
        "measuredSystemRuntime": len(built_system_runtime),
        "measuredUser": len(built_user),
        "reconstructedSystem": len(recon_system),
        "reconstructedUser": len(recon_user),
        "systemNotesTailChars": notes_tail if notes_tail > 0 else 0,
        "issues": issues,
        "codeRef": {
            "pipeline-a-diagnose": "agents_runtime.agents.run_a → build_context",
            "pipeline-b-style": "agents_runtime.agents.run_b → build_context",
            "judge": "agents_runtime.agents.run_judge → build_context",
        }.get(pipeline_id, "build_context"),
        "orchestrateRef": "agents_runtime.orchestrate run_stage_a/b/judge",
    }


def _manifest_for(prompt: Any, prompt_rel: str, crosscheck: dict[str, Any]) -> dict[str, Any]:
    ppath = ROOT / prompt_rel
    active_inputs = []
    for spec in prompt.inputs:
        if not isinstance(spec, dict):
            continue
        active_inputs.append(
            {
                "name": spec.get("name"),
                "type": spec.get("type"),
                "source": spec.get("source"),
                "sections": spec.get("sections"),
                "required": spec.get("required"),
                "description": (spec.get("description") or "").strip()[:220],
            }
        )
    return {
        "agentId": prompt.agent_id,
        "promptVersion": prompt.version,
        "promptPath": prompt_rel,
        "promptMtime": datetime.fromtimestamp(ppath.stat().st_mtime).isoformat(
            timespec="seconds"
        ),
        "modelTier": prompt.model_tier,
        "activeInputs": active_inputs,
        "forbiddenInputs": list(prompt.forbidden_inputs),
        "measuredChars": {
            "system": crosscheck["measuredSystem"],
            "user": crosscheck["measuredUser"],
            "total": crosscheck["measuredSystem"] + crosscheck["measuredUser"],
        },
        "crosscheck": crosscheck,
    }


def _sample_inputs_pipeline_a() -> dict[str, Any]:
    q = ROOT / DEFAULT_QUESTION_MD
    rh: dict[str, Any] = {}
    try:
        from agents_runtime._subprocess import run_route_helper_json

        rh, _stderr = run_route_helper_json(ROOT, str(q))
    except Exception as e:
        rh = {
            "_export_note": f"route_helper 未跑通，用空对象占位: {e}",
            "candidates": [],
            "route_hint": "new",
            "confidence": "low",
        }
    fewshot = _extract_v3_cards("IC-004", "IC-017", "IC-024")
    return {
        "question_md": str(q),
        "route_helper_output": rh,
        "v3_fewshot": fewshot,
    }


def _sample_inputs_pipeline_b() -> dict[str, Any]:
    a = _first_json(
        [
            "agents/runs/dogfood-2026-05-20/run_a.json",
            "agentflow3-tocode/phase1产出/run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json",
            "agents/runs/run_2026-05-11_pipeline-a_ball-trash-talk.json",
        ]
    )
    if not a:
        a = {"route": "new", "title": "示例", "patterns": ["P-EVAL"], "axis": "attention",
             "chain": {"trigger": "t", "questions": ["q1", "q2"]}, "mechanism_sketch": "x" * 40}
    if "route" not in a:
        a = {**a, "route": "new"}
    d = {k: v for k, v in a.items() if k != "_meta"}
    return {
        "pipeline_a_draft": d,
        "existing_card_json": {},
    }


def _sample_inputs_judge() -> dict[str, Any]:
    b = _first_json(
        [
            "agents/runs/dogfood-2026-05-20/run_b_v2_2.json",
            "agents/runs/run_2026-05-12_pipeline-b_ball-trash-talk.json",
        ]
    )
    a = _first_json(
        [
            "agents/runs/dogfood-2026-05-20/run_a.json",
            "agents/runs/run_2026-05-11_pipeline-a_ball-trash-talk.json",
        ]
    )
    if not b:
        b = {"output_kind": "full_card", "route": "new", "id": "IC-NEW"}
    if not a:
        a = {"route": "new"}
    rc = {
        "route": a.get("route"),
        "target_ic_id": a.get("target_ic_id"),
        "update_directives": a.get("update_directives"),
        "raw_answer_seeds": a.get("raw_answer_seeds"),
        "meta_evidence": a.get("meta_evidence"),
    }
    bd = {k: v for k, v in b.items() if k != "_meta"}
    return {
        "b_output": bd,
        "route_context": rc,
        "existing_card_json": {},
        "v3_anchor": _extract_v3_cards("IC-004")[:1],
    }


def _archive_chunks_b(cb: ChunkBuilder, prompt: Any) -> None:
    """v2.2 已停用但仍可对照的块。"""
    style_path = "context/crystallization-style-agent-brief.md"
    for sec in ["§5 禁忌替代", "§8 实证归纳"]:
        if sec not in ("§1 沉淀摘要", "§4 执行清单"):
            block = _strip_excerpt_wrapper(
                extract_doc_sections(style_path, [sec], field_name="style_brief", prompt=prompt)
            )
            _add_chunk(
                cb,
                cid=f"b.archive.brief.{sec.replace('§', '')}",
                layer="user",
                group="② 已停用",
                label=f"brief {sec}",
                content=block,
                source=style_path,
                default_on=False,
                status="inactive",
                note="已迁入 style_lexicon",
            )
    schema_path = "context/crystallization-schema-v0.md"
    for sec in ["§4 内容 lint", "§6 反例"]:
        block = _strip_excerpt_wrapper(
            extract_doc_sections(schema_path, [sec], field_name="schema_lint", prompt=prompt)
        )
        _add_chunk(
            cb,
            cid=f"b.archive.schema.{sec.replace('§', '').replace(' ', '-')}",
            layer="user",
            group="② 已停用",
            label=f"schema {sec}",
            content=block,
            source=schema_path,
            default_on=False,
            status="inactive",
        )
    annot_path = "回答版本explore/良质回答标注册.md"
    text = _read(annot_path)
    for label, fn in [
        ("§〇", lambda t: _extract_cjk_section(t, "〇")),
        ("§八", lambda t: _extract_cjk_section(t, "八")),
        ("B/C/F/H", lambda t: _extract_bcfh_block(t)),
    ]:
        _add_chunk(
            cb,
            cid=f"b.archive.annot.{label}",
            layer="user",
            group="② 已停用 · forbidden",
            label=f"标注册 {label}",
            content=fn(text),
            source=annot_path,
            default_on=False,
            status="forbidden",
            note="v2.2 forbidden；lexicon §3 承接锚句",
        )


def build_pipeline(pipeline_id: str, sample_fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    prompt_rel = PROMPT_PATHS[pipeline_id]
    loader_name = {
        "pipeline-a-diagnose": "pipeline-a-diagnose",
        "pipeline-b-style": "pipeline-b-style",
        "judge": "judge",
    }[pipeline_id]
    prompt = load_prompt(loader_name)

    cb = ChunkBuilder(pipeline_id, prompt_rel)
    _build_system_chunks(cb, prompt)
    sample = sample_fn()
    build_inputs: dict[str, Any] = {}
    for spec in prompt.inputs:
        if not isinstance(spec, dict):
            continue
        n = spec.get("name")
        t = spec.get("type")
        if t == "markdown_file":
            build_inputs[n] = sample[n]
        elif t == "json":
            build_inputs[n] = sample.get(n, {})
        elif t == "example_set":
            build_inputs[n] = sample.get(n, [])
        # doc_full / doc_section_set：build_context 只读 frontmatter source，不读 inputs 值

    _build_inputs_from_frontmatter(cb, prompt, sample)

    if pipeline_id == "pipeline-b-style":
        _archive_chunks_b(cb, prompt)

    assert cb.chunks is not None
    crosscheck = _crosscheck(pipeline_id, prompt, build_inputs, cb.chunks)
    if not crosscheck["ok"]:
        print(f"[crosscheck WARN] {pipeline_id}: {crosscheck['issues']}", file=sys.stderr)

    active_ids = [c["id"] for c in cb.chunks if c["status"] == "active"]
    return {
        "manifest": _manifest_for(prompt, prompt_rel, crosscheck),
        "chunks": cb.chunks,
        "presets": {
            "current_runtime": active_ids,
        },
    }


def build_all() -> dict[str, Any]:
    pipelines = {
        "pipeline-a-diagnose": build_pipeline("pipeline-a-diagnose", _sample_inputs_pipeline_a),
        "pipeline-b-style": build_pipeline("pipeline-b-style", _sample_inputs_pipeline_b),
        "judge": build_pipeline("judge", _sample_inputs_judge),
    }
    all_chunks: list[dict] = []
    for pid, pdata in pipelines.items():
        for c in pdata["chunks"]:
            all_chunks.append(c)

    crosschecks = {pid: pdata["manifest"]["crosscheck"] for pid, pdata in pipelines.items()}
    all_ok = all(c.get("ok") for c in crosschecks.values())

    return {
        "meta": {
            "generated_at": date.today().isoformat(),
            "generated_at_iso": datetime.now().isoformat(timespec="seconds"),
            "pipeline_count": len(pipelines),
            "chunk_count": len(all_chunks),
            "crosscheckAllOk": all_ok,
            "orchestrateFlow": [
                "route_helper (plumbing)",
                "run_a → a.json",
                "run_b(a, existing?) → b.json",
                "run_judge(b, route_context) → judge.json",
                "push / merge",
            ],
        },
        "pipelines": pipelines,
        "defaultPipeline": "pipeline-b-style",
    }


def main() -> None:
    data = build_all()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    js = (
        "window.AGENTFLOW_CONTEXT_CHUNKS = "
        + json.dumps(data, ensure_ascii=False, indent=2)
        + ";\n"
        "window.PIPELINE_B_CONTEXT_CHUNKS = window.AGENTFLOW_CONTEXT_CHUNKS.pipelines['pipeline-b-style'];\n"
    )
    OUT_JS.write_text(js, encoding="utf-8")
    for pid, pdata in data["pipelines"].items():
        m = pdata["manifest"]["measuredChars"]
        cc = pdata["manifest"]["crosscheck"]
        flag = "OK" if cc.get("ok") else "WARN"
        print(
            f"[{flag}] {pid}: {len(pdata['chunks'])} chunks, "
            f"active={len(pdata['presets']['current_runtime'])}, "
            f"runtime≈{m['total']} chars",
            file=sys.stderr,
        )
        if cc.get("issues"):
            for iss in cc["issues"]:
                print(f"       - {iss}", file=sys.stderr)


if __name__ == "__main__":
    main()
