from __future__ import annotations

from pathlib import Path

import pytest

from agents_runtime.context_builder import build_context
from agents_runtime.errors import ForbiddenInputError
from agents_runtime.loader import load_prompt

FIX_DIR = Path(__file__).resolve().parent / "fixtures"


def test_forbidden_question_md_raises() -> None:
    p = load_prompt("mini", prompts_dir=str(FIX_DIR))
    with pytest.raises(ForbiddenInputError) as ei:
        build_context(p, {"question_md": "外部source/whatever.md"})
    assert ei.value.field == "question_md"
    assert "外部source" in (ei.value.path or "")


def test_doc_full_reads_whole_file() -> None:
    p = load_prompt("mini-doc-full", prompts_dir=str(FIX_DIR))
    u = build_context(p, {})
    assert "# lexicon" in u
    assert "LEXICON_FIXTURE_MARKER_LINE_1" in u
    assert "LEXICON_FIXTURE_MARKER_LINE_2" in u
    assert "口语承接，书面拆解" in u


def test_doc_full_forbidden_lint_still_runs(tmp_path: Path) -> None:
    """doc_full source 命中 forbidden_inputs 时应抛 ForbiddenInputError。"""
    bad_prompt = tmp_path / "mini-bad.prompt.md"
    bad_prompt.write_text(
        """---
agent_id: mini-bad
version: v0
model_tier: plumbing
inputs:
  - { name: src, type: doc_full, source: "外部source/should-be-blocked.md", required: true }
outputs:
  - { name: out, type: json }
forbidden_inputs:
  - "外部source/*.md"
single_responsibility: "fixture"
---

## Body
""",
        encoding="utf-8",
    )
    p = load_prompt("mini-bad", prompts_dir=str(tmp_path))
    with pytest.raises(ForbiddenInputError) as ei:
        build_context(p, {})
    assert ei.value.field == "src"


def test_pipeline_a_question_allowed_under_exemption() -> None:
    p = load_prompt("pipeline-a-diagnose")
    u = build_context(
        p,
        {
            "question_md": "外部source/球场垃圾话应对策略.md",
            "route_helper_output": {},
            "v3_fewshot": [],
        },
    )
    assert "# question_md" in u
    assert len(u) > 1000
