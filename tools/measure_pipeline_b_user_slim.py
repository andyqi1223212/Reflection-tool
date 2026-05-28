#!/usr/bin/env python3
"""
Pipeline B 「user_slim_v1」字符量预实测（不依赖 builder doc_full 改造）。

按目标 frontmatter（lexicon 整文件 + brief §1/§4 + schema §2.5-§2.7）模拟装配：
- system = pipeline-b-style.prompt.md 正文
- user   = mock A draft + lexicon (doc_full) + brief §1/§4 + schema §2.5-§2.7

用法（仓库根）:
  venv/bin/python3 tools/measure_pipeline_b_user_slim.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents_runtime.context_builder import extract_doc_sections  # noqa: E402
from agents_runtime.loader import load_prompt  # noqa: E402


def _strip_section_after(body: str, heading_re: str) -> str:
    """Drop everything from a `## ` heading onwards (e.g. `## 6. Few-shot examples`)."""
    m = re.search(heading_re, body, flags=re.M)
    return body[: m.start()] if m else body


def main() -> int:
    prompt = load_prompt("pipeline-b-style")

    # System: prompt body, simulate v2.2 by stripping §6 Few-shot section
    system_body = prompt.body
    system_now = system_body
    system_target = _strip_section_after(system_body, r"^## 6\.\s+Few-shot examples")

    mock_a_draft = {
        "route": "new",
        "title": "课堂题没做出，害怕老师同学觉得自己装、笨",
        "patterns": ["P-EVAL", "P-FAMILY", "P-KNOW-DO"],
        "axis": "attention",
        "chain": {
            "trigger": "提前学过机器学习 / 线代，上课问老师问题、帮同学解释，但课堂练习题做不出来。",
            "questions": [
                "我听的时候理解了，做的时候想偏了，脑子紧焦虑",
                "我怕老师觉得我很菜、爱装",
            ],
        },
        "mechanism_sketch": (
            "你不是只在做题，你还在维护『提前学过 → 必须答得好』的人设。"
            "证明压力一进来，工作记忆就被它占满，剩下的算力解题不够用。"
        ),
        "source_refs": ["C12", "B11", "F07"],
    }
    a_draft_block = "# pipeline_a_draft\n" + json.dumps(
        mock_a_draft, ensure_ascii=False, indent=2
    ) + "\n\n"

    existing_card_block = "# existing_card_json\n{}\n\n"

    lexicon_path = ROOT / "context/pipeline-b-style-lexicon-v1.md"
    lexicon_block = "# style_lexicon\n" + lexicon_path.read_text(encoding="utf-8") + "\n\n"

    brief_block = "# style_brief\n" + extract_doc_sections(
        "context/crystallization-style-agent-brief.md",
        ["§1 沉淀摘要", "§4 执行清单"],
        field_name="style_brief",
        prompt=prompt,
    ) + "\n\n"

    schema_block = "# schema_lint\n" + extract_doc_sections(
        "context/crystallization-schema-v0.md",
        ["§2.5 mechanism", "§2.6 anchor", "§2.7 micro_steps"],
        field_name="schema_lint",
        prompt=prompt,
    ) + "\n\n"

    user_target = (
        a_draft_block + existing_card_block + lexicon_block + brief_block + schema_block
    )

    def _fmt(label: str, n: int) -> str:
        return f"  {label:<20} {n:>6,}"

    print("=== Pipeline B 字符量预实测（mock route=new）===")
    print()
    print("[当前 v2.1 system 全文（含 §5 反例 + §6 Few-shot）]")
    print(_fmt("system_now", len(system_now)))
    print()
    print("[v2.2 目标：删 §6 Few-shot 全段]")
    print(_fmt("system_target", len(system_target)))
    print(_fmt("(节省)", len(system_now) - len(system_target)))
    print()
    print("[v2.2 目标 user（lexicon + brief §1/§4 + schema §2.5-§2.7）]")
    print(_fmt("a_draft_mock", len(a_draft_block)))
    print(_fmt("existing_card={}", len(existing_card_block)))
    print(_fmt("style_lexicon", len(lexicon_block)))
    print(_fmt("style_brief", len(brief_block)))
    print(_fmt("schema_lint", len(schema_block)))
    print(_fmt("user_target 总", len(user_target)))
    print()
    total_target = len(system_target) + len(user_target)
    print(_fmt("system+user 总", total_target))
    print()
    print(f"参考: 当前 v2.1 实测 ~39k；v2.2 目标 ≤24k；硬上限 30k")
    if total_target <= 24_000:
        print("✅ 达标（含余量）")
    elif total_target <= 30_000:
        print("⚠️ 超目标但未破上限——可考虑再瘦 lexicon §3 锚句家族")
    else:
        print("❌ 超硬上限，回 Step 1 大幅瘦身 lexicon")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
