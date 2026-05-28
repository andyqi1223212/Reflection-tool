from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agents_runtime.errors import PromptLoadError
from agents_runtime.loader import Prompt, load_prompt


FIX = Path(__file__).resolve().parent / "fixtures" / "mini.prompt.md"


def test_load_mini_prompt_dataclass() -> None:
    text = FIX.read_text(encoding="utf-8")
    assert text.startswith("---")
    p = load_prompt("mini", prompts_dir=str(FIX.parent))
    assert isinstance(p, Prompt)
    assert p.agent_id == "mini-test"
    assert p.version == "v0"
    assert p.model_tier == "plumbing"
    assert isinstance(p.inputs, list)
    assert "## Body" in p.body
    assert "---" not in p.body.split("\n")[0]


def test_body_strips_leading_blank_after_frontmatter() -> None:
    p = load_prompt("mini", prompts_dir=str(FIX.parent))
    assert p.body.startswith("##")


def test_missing_file_raises() -> None:
    with pytest.raises(PromptLoadError, match="找不到"):
        load_prompt("nonexistent-xyz", prompts_dir=str(FIX.parent))
