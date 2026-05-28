from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any

from .errors import ForbiddenInputError, PromptLoadError
from .loader import Prompt, _repo_root


def _clean_glob_token(tok: str) -> str:
    t = tok.strip()
    t = re.sub(r"[（(][^）)]*[）)]$", "", t).strip()
    t = t.rstrip("。，、")
    return t


def _forbidden_line_exempts_question_md(line: str) -> bool:
    return "除当前" in line and "question_md" in line


def _lint_path_forbidden(
    *,
    path: Path,
    field_name: str,
    forbidden_lines: list[str],
    exempt_question_md: bool,
) -> None:
    root = _repo_root()
    px = path.resolve().as_posix()
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = None
    candidates = [px, rel, path.name] if rel else [px, path.name]
    for line in forbidden_lines:
        if exempt_question_md and field_name == "question_md" and _forbidden_line_exempts_question_md(line):
            continue
        for raw_tok in line.split():
            tok = _clean_glob_token(raw_tok)
            if not tok:
                continue
            for cand in candidates:
                if not cand:
                    continue
                if fnmatch.fnmatch(cand, tok) or fnmatch.fnmatch(cand, tok.replace("\\", "/")):
                    raise ForbiddenInputError(
                        f"禁止读取的文件命中 forbidden_inputs: {tok}",
                        field=field_name,
                        path=px,
                    )


def _read_text_file(rel_or_abs: str, *, field_name: str, prompt: Prompt) -> str:
    root = _repo_root()
    p = Path(rel_or_abs)
    if not p.is_absolute():
        p = (root / p).resolve()
    _lint_path_forbidden(
        path=p,
        field_name=field_name,
        forbidden_lines=prompt.forbidden_inputs,
        exempt_question_md=prompt.agent_id == "pipeline-a-diagnose",
    )
    if not p.is_file():
        raise PromptLoadError(f"找不到文件（{field_name}）: {p}")
    return p.read_text(encoding="utf-8")


def _heading_level(line: str) -> int | None:
    m = re.match(r"^(#{2,6})\s", line)
    return len(m.group(1)) if m else None


def _heading_cjk_section_mark(rest: str) -> str | None:
    """匹配 `## 八、` 或 `### 〇-b、` 行首的章节标."""
    rest = rest.strip()
    m = re.match(r"^([〇一二三四五六七八九十]+)(?:[、．.]|$)", rest)
    if m:
        return m.group(1)
    m2 = re.match(r"^(〇-b|[〇一二三四五六七八九十]+-b)", rest)
    if m2:
        return m2.group(1)
    return None


def _slice_by_heading_levels(
    lines: list[str], start_idx: int, start_level: int
) -> str:
    out = [lines[start_idx]]
    i = start_idx + 1
    while i < len(lines):
        line = lines[i]
        lv = _heading_level(line)
        if lv is not None and lv <= start_level:
            break
        out.append(line)
        i += 1
    return "".join(out)


def _find_numeric_section(text: str, want: tuple[int, ...]) -> str | None:
    lines = text.splitlines(keepends=True)
    if len(want) == 2:
        pat = re.compile(rf"^###\s+{want[0]}\.{want[1]}\b")
    elif len(want) == 1:
        pat = re.compile(rf"^##\s+{want[0]}\.")
    else:
        return None
    for i, line in enumerate(lines):
        if not pat.match(line):
            continue
        lv = _heading_level(line) or 2
        return _slice_by_heading_levels(lines, i, lv)
    return None


def _find_cjk_heading_line(lines: list[str], mark: str) -> int | None:
    """mark 如 '八' 或 '〇' 或 '〇-b'。"""
    for i, line in enumerate(lines):
        if _heading_level(line) is None:
            continue
        rest = re.sub(r"^#{2,6}\s+", "", line)
        cm = _heading_cjk_section_mark(rest)
        if cm == mark:
            return i
    return None


def _extract_bcfh_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    s = _find_cjk_heading_line(lines, "三")
    if s is None:
        raise PromptLoadError("未找到 ## 三、（B/C/F/H 高分句区）")
    e = _find_cjk_heading_line(lines, "四")
    if e is None:
        return "".join(lines[s:])
    return "".join(lines[s:e])


def _extract_cjk_section(text: str, mark: str) -> str:
    lines = text.splitlines(keepends=True)
    idx = _find_cjk_heading_line(lines, mark)
    if idx is None:
        raise PromptLoadError(f"未找到章节标「{mark}」对应 heading")
    lv = _heading_level(lines[idx]) or 2
    return _slice_by_heading_levels(lines, idx, lv)


def _extract_ob_subsection(text: str) -> str:
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if _heading_level(line) != 3:
            continue
        rest = re.sub(r"^###\s+", "", line)
        if rest.startswith("〇-b"):
            return _slice_by_heading_levels(lines, i, 3)
    raise PromptLoadError("未找到 ### 〇-b")


def _numeric_id_from_section_label(label: str) -> tuple[int, ...] | None:
    m = re.search(r"§\s*(\d+(?:\.\d+)*)", label)
    if not m:
        return None
    return tuple(int(x) for x in m.group(1).split("."))


def _cjk_mark_from_section_label(label: str) -> str | None:
    m = re.search(r"§\s*([〇一二三四五六七八九十]+)(?:-b)?", label)
    if not m:
        return None
    base = m.group(1)
    if "-b" in label or "〇-b" in label:
        if base == "〇":
            return "〇-b"
        return f"{base}-b"
    return base


def extract_doc_sections(source_rel: str, sections: list[str], *, field_name: str, prompt: Prompt) -> str:
    body = _read_text_file(source_rel, field_name=field_name, prompt=prompt)
    chunks: list[str] = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        if "B/C" in sec:
            chunks.append(f"### 摘录区块: {sec}\n\n" + _extract_bcfh_block(body))
            continue
        if "〇-b" in sec or "§〇-b" in sec or re.search(r"〇\s*[-–]b", sec):
            chunks.append(f"### 摘录区块: {sec}\n\n" + _extract_ob_subsection(body))
            continue
        cjk = _cjk_mark_from_section_label(sec)
        if cjk and cjk != "〇-b" and re.search(r"§\s*[〇一二三四五六七八九十]", sec):
            chunks.append(f"### 摘录区块: {sec}\n\n" + _extract_cjk_section(body, cjk))
            continue
        nid = _numeric_id_from_section_label(sec)
        if nid:
            block = _find_numeric_section(body, nid)
            if block is None:
                raise PromptLoadError(f"在 {source_rel} 中未找到章节 {sec}（解析 id={nid}）")
            chunks.append(f"### 摘录区块: {sec}\n\n" + block)
            continue
        raise PromptLoadError(f"无法解析 sections 标签: {sec!r}（{source_rel}）")
    return "\n\n".join(chunks)


def _format_example_set(name: str, items: list[str] | Any) -> str:
    if not isinstance(items, list):
        raise PromptLoadError(f"{name} 必须是字符串列表（fewshot / v3 卡 md）")
    parts = []
    for i, block in enumerate(items):
        if not isinstance(block, str):
            raise PromptLoadError(f"{name}[{i}] 必须是 str")
        parts.append(block.strip())
    return "\n\n---\n\n".join(parts) if parts else "(未提供 example_set；调用方可传 fewshot 列表)"


def build_context(prompt: Prompt, inputs: dict[str, Any]) -> str:
    """
    按 prompt.inputs 顺序拼接 user message；
    对会触发读盘的字段执行 forbidden_inputs lint。
    """
    blocks: list[str] = []
    for spec in prompt.inputs:
        if not isinstance(spec, dict):
            raise PromptLoadError("inputs[] 每项必须是 mapping")
        name = spec.get("name")
        if not name:
            raise PromptLoadError("input 缺少 name")
        typ = spec.get("type", "")
        blocks.append(f"# {name}\n")
        if typ == "markdown_file":
            path = inputs.get(name)
            if not path:
                raise PromptLoadError(f"缺少必填 markdown_file: {name}")
            content = _read_text_file(str(path), field_name=str(name), prompt=prompt)
            blocks.append(content)
        elif typ == "json":
            val = inputs.get(name)
            if val is None:
                raise PromptLoadError(f"缺少必填 json: {name}")
            if isinstance(val, str):
                blocks.append(val)
            else:
                blocks.append(json.dumps(val, ensure_ascii=False, indent=2))
        elif typ == "doc_section_set":
            src = spec.get("source")
            secs = spec.get("sections") or []
            if not src or not isinstance(secs, list):
                raise PromptLoadError(f"{name}: doc_section_set 需要 source + sections")
            blocks.append(
                extract_doc_sections(str(src), [str(s) for s in secs], field_name=str(name), prompt=prompt)
            )
        elif typ == "doc_full":
            src = spec.get("source")
            if not src:
                raise PromptLoadError(f"{name}: doc_full 需要 source（整文件喂入）")
            blocks.append(_read_text_file(str(src), field_name=str(name), prompt=prompt))
        elif typ == "example_set":
            blocks.append(_format_example_set(str(name), inputs.get(name) or []))
        else:
            raise PromptLoadError(f"暂不支持的 input type: {typ!r}（{name}）")
        blocks.append("\n")
    return "".join(blocks).rstrip() + "\n"
