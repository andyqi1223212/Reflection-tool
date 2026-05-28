"""Markdown patch 工具：lexicon / synthesis apply 共用。"""
from __future__ import annotations

import re
from typing import Any


def locate_section_bounds(text: str, section_label: str) -> tuple[int, int]:
    """按 ## N. 标题切 section；section_label 含 §N 或标题片段。"""
    if not section_label:
        raise ValueError("section_label 为空")
    label = section_label.strip()
    pat = None
    sec_num = re.search(r"§\s*(\d+)", label)
    if sec_num:
        n = sec_num.group(1)
        pat = re.compile(rf"^#{{1,6}}\s*{re.escape(n)}\.\s", re.M)
    else:
        pat = re.compile(rf"^#{{1,6}}\s+.*{re.escape(label)}", re.M)
    m = pat.search(text)
    if not m:
        raise ValueError(f"section 找不到: {section_label!r}")
    start = m.start()
    next_pat = re.compile(r"^##\s", re.M)
    m2 = next_pat.search(text, m.end())
    end = m2.start() if m2 else len(text)
    return start, end


def _normalize_action(action: str | None) -> str:
    a = (action or "").strip()
    if a == "append":
        return "append_to_section"
    return a


def _insert_at_section_table_end(text: str, section: str, new: str) -> str:
    start, end = locate_section_bounds(text, section)
    section_text = text[start:end]
    lines = section_text.splitlines(keepends=True)
    last_row = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("|"):
            last_row = i
    if last_row < 0:
        raise ValueError(f"section_table_end: § 内无表格行 ({section!r})")
    insert_at = sum(len(lines[j]) for j in range(last_row + 1))
    abs_pos = start + insert_at
    addition = new if new.endswith("\n") else new + "\n"
    return text[:abs_pos] + addition + text[abs_pos:]


def apply_patch(text: str, patch: dict[str, Any]) -> str:
    """单条 patch；支持 insert_row / replace_line / append|append_to_section / replace_block。"""
    action = _normalize_action(patch.get("action"))
    anchor = patch.get("anchor_text") or ""
    new = patch.get("new_content") or ""
    section = patch.get("section") or ""
    position = (patch.get("position") or "after").lower()

    if action == "replace_line":
        if not anchor or anchor not in text:
            raise ValueError(f"replace_line: anchor_text 未命中 {anchor!r}")
        return text.replace(anchor, new, 1)

    if action == "insert_row":
        if position == "section_table_end":
            if not section:
                raise ValueError("insert_row section_table_end 需要 section")
            return _insert_at_section_table_end(text, section, new)
        if not anchor or anchor not in text:
            raise ValueError(f"insert_row: anchor_text 未命中 {anchor!r}")
        idx = text.find(anchor)
        line_end = text.find("\n", idx)
        if line_end == -1:
            line_end = len(text)
        if position == "before":
            line_start = text.rfind("\n", 0, idx) + 1
            return text[:line_start] + new + ("\n" if not new.endswith("\n") else "") + text[line_start:]
        prefix = text[: line_end + 1]
        suffix = text[line_end + 1 :]
        addition = new if new.endswith("\n") else new + "\n"
        return prefix + addition + suffix

    if action == "append_to_section":
        start, end = locate_section_bounds(text, section)
        section_body = text[start:end]
        trimmed = section_body.rstrip("\n")
        addition = "\n\n" + new.rstrip("\n") + "\n\n"
        return text[:start] + trimmed + addition + text[end:]

    if action == "replace_block":
        if not anchor or anchor not in text:
            raise ValueError(f"replace_block: anchor_text 未命中 {anchor!r}")
        anchor_idx = text.find(anchor)
        next_pat = re.compile(r"^##\s", re.M)
        m2 = next_pat.search(text, anchor_idx + len(anchor))
        end = m2.start() if m2 else len(text)
        return text[:anchor_idx] + new.rstrip("\n") + "\n\n" + text[end:]

    raise ValueError(f"未知 action: {patch.get('action')}")


def validate_patches(text: str, patches: list[dict[str, Any]]) -> list[str]:
    """返回 anchor_text 找不到的 patch id 列表（append_to_section / section_table_end 除外）。"""
    failed: list[str] = []
    for patch in patches:
        pid = str(patch.get("id") or "?")
        action = _normalize_action(patch.get("action"))
        anchor = patch.get("anchor_text") or ""
        position = (patch.get("position") or "").lower()
        if action == "append_to_section":
            try:
                locate_section_bounds(text, patch.get("section") or "")
            except ValueError:
                failed.append(pid)
            continue
        if action == "insert_row" and position == "section_table_end":
            try:
                locate_section_bounds(text, patch.get("section") or "")
            except ValueError:
                failed.append(pid)
            continue
        if not anchor:
            failed.append(pid)
            continue
        if anchor not in text:
            failed.append(pid)
    return failed


def apply_patches_safely(
    text: str, patches: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    """全部成功才返回新 text；任一失败回滚并返回失败 patch id 列表。"""
    working = text
    for patch in patches:
        pid = str(patch.get("id") or "?")
        try:
            working = apply_patch(working, patch)
        except Exception:
            return text, [pid]
    return working, []
