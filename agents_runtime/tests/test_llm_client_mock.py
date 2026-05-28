from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents_runtime.errors import LLMJsonParseError
from agents_runtime import llm_client as lc


def _fake_choice(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    ch = MagicMock()
    ch.message = msg
    resp = MagicMock()
    resp.choices = [ch]
    return resp


def test_call_json_success_first_try(tmp_path: Path) -> None:
    stats = tmp_path / "parse_stats.jsonl"
    with patch.object(lc, "_STATS_FILE", stats):
        client = MagicMock()
        client.chat.completions.create.return_value = _fake_choice('{"ok": true}')
        with patch.object(lc, "_get_client", return_value=client):
            out = lc.call_json(
                system="s",
                user="u",
                model="deepseek-reasoner",
                temperature=0.0,
                agent_id="t-agent",
                debug_dir=str(tmp_path),
            )
        assert out == {"ok": True}
    lines = stats.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["success"] is True
    assert row["retried"] is False


def test_call_json_retry_then_success(tmp_path: Path) -> None:
    stats = tmp_path / "parse_stats.jsonl"
    with patch.object(lc, "_STATS_FILE", stats):
        client = MagicMock()
        client.chat.completions.create.side_effect = [
            _fake_choice("not-json"),
            _fake_choice('{"fixed": 1}'),
        ]
        with patch.object(lc, "_get_client", return_value=client):
            out = lc.call_json(
                system="s",
                user="u",
                model="m",
                temperature=0.0,
                agent_id="t2",
                debug_dir=str(tmp_path),
            )
        assert out == {"fixed": 1}
        assert client.chat.completions.create.call_count == 2
    row = json.loads(stats.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["success"] is True
    assert row["retried"] is True


def test_call_json_double_fail_writes_debug(tmp_path: Path) -> None:
    stats = tmp_path / "parse_stats.jsonl"
    with patch.object(lc, "_STATS_FILE", stats):
        client = MagicMock()
        client.chat.completions.create.return_value = _fake_choice("@@@")
        with patch.object(lc, "_get_client", return_value=client):
            with pytest.raises(LLMJsonParseError):
                lc.call_json(
                    system="s",
                    user="u",
                    model="m",
                    temperature=0.0,
                    agent_id="t3",
                    debug_dir=str(tmp_path),
                )
        fails = list(tmp_path.glob("parse_fail_t3_*.txt"))
        assert len(fails) == 1
    row = json.loads(stats.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["success"] is False
    assert row["retried"] is True
