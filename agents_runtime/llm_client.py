from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from .errors import LLMJsonParseError
from .loader import _repo_root

_RETRY_SUFFIX = (
    "\n\n【系统】上一次返回不是合法 JSON，请只输出一个合法 JSON object，"
    "不要 markdown fence，不要解释。"
)

_STATS_DIR = Path(__file__).resolve().parent / "_stats"
_STATS_FILE = _STATS_DIR / "parse_stats.jsonl"

_ENV_BOOTSTRAPPED = False


def _bootstrap_env() -> None:
    global _ENV_BOOTSTRAPPED
    if _ENV_BOOTSTRAPPED:
        return
    root = _repo_root()
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]
    if load_dotenv:
        for name in (".env.local", ".env", ".env.example"):
            p = root / name
            if p.is_file():
                load_dotenv(dotenv_path=p)
    _ENV_BOOTSTRAPPED = True


# 首次 import 时从仓库根加载 .env，再解析默认模型 / base_url（与 tools/llm_api.py 对齐）
_bootstrap_env()
# 官方文档：https://api-docs.deepseek.com/zh-cn/ 、JSON Output：https://api-docs.deepseek.com/zh-cn/guides/json_mode
_DEFAULT_REASONING = os.getenv("DEEPSEEK_REASONING_MODEL", "deepseek-v4-pro")
_DEFAULT_CHAT = os.getenv("DEEPSEEK_CHAT_MODEL", "deepseek-v4-flash")
_DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_OPENAI_BASE_URL", "https://api.deepseek.com")


def _get_client() -> OpenAI:
    _bootstrap_env()
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY")
    return OpenAI(api_key=key, base_url=_DEEPSEEK_BASE_URL)


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    m = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _parse_json_object(raw: str) -> dict[str, Any]:
    s = _strip_json_fence(raw)
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise json.JSONDecodeError("根节点不是 object", s, 0)
    return obj


def _append_stats(agent_id: str, *, success: bool, retried: bool) -> None:
    _STATS_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "ts": time.time(),
            "agent": agent_id,
            "success": success,
            "retried": retried,
        },
        ensure_ascii=False,
    )
    with _STATS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _deepseek_v4_pro_thinking_kwargs(model: str) -> dict[str, Any]:
    """与官方「思考模式」示例一致：deepseek-v4-pro + reasoning_effort + extra_body.thinking。"""
    if model != "deepseek-v4-pro" and "deepseek-v4-pro" not in model:
        return {}
    if os.getenv("DEEPSEEK_V4_PRO_THINKING", "1").lower() in ("0", "false", "no", "off"):
        return {}
    return {
        "reasoning_effort": os.getenv("DEEPSEEK_REASONING_EFFORT", "high"),
        "extra_body": {"thinking": {"type": "enabled"}},
    }


def _write_parse_fail(
    agent_id: str, raw: str, *, debug_dir: str | None
) -> Path:
    root = Path(debug_dir) if debug_dir else Path.cwd() / "_debug"
    root.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    path = root / f"parse_fail_{agent_id}_{ts}.txt"
    path.write_text(raw, encoding="utf-8")
    return path


def call_json(
    *,
    system: str,
    user: str,
    model: str,
    temperature: float,
    agent_id: str,
    debug_dir: str | None = None,
) -> dict[str, Any]:
    """
    DeepSeek chat.completions + response_format json_object；
    JSON 解析失败则追加 retry 提示再调一次。
    """
    client = _get_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    retried = False

    def _one_call(msgs: list[dict[str, str]]) -> str:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        kwargs.update(_deepseek_v4_pro_thinking_kwargs(model))
        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()

    raw = _one_call(messages)
    try:
        out = _parse_json_object(raw)
        _append_stats(agent_id, success=True, retried=retried)
        return out
    except json.JSONDecodeError:
        pass

    retried = True
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user + _RETRY_SUFFIX},
    ]
    raw2 = _one_call(messages)
    try:
        out = _parse_json_object(raw2)
        _append_stats(agent_id, success=True, retried=retried)
        return out
    except json.JSONDecodeError:
        _write_parse_fail(agent_id, raw2, debug_dir=debug_dir)
        _append_stats(agent_id, success=False, retried=retried)
        raise LLMJsonParseError(
            "模型输出两次均无法解析为 JSON object",
            raw_text=raw2,
        ) from None
