from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import PromptLoadError

_REQUIRED_FM_KEYS = frozenset(
    {
        "agent_id",
        "version",
        "model_tier",
        "inputs",
        "outputs",
        "forbidden_inputs",
        "single_responsibility",
    }
)
# agent第二轮/conventions.md 常见 frontmatter，不算「未知」
_OPTIONAL_FM_KEYS = frozenset(
    {
        "created",
        "last_iter",
        "upstream",
        "downstream",
        "failure_mode",
    }
)


@dataclass
class Prompt:
    agent_id: str
    version: str
    model_tier: str
    inputs: list[dict[str, Any]]
    outputs: list[dict[str, Any]]
    forbidden_inputs: list[str]
    single_responsibility: str
    body: str
    source_path: str
    extra: dict[str, Any]


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("\ufeff"):
        text = text[1:]
    if not text.lstrip().startswith("---"):
        raise PromptLoadError("文件不以 YAML frontmatter（---）开头")
    # 首行 --- 之后到下一个独占行的 ---
    m = re.match(r"^---\s*\r?\n", text)
    if not m:
        raise PromptLoadError("frontmatter 起始标记异常")
    rest = text[m.end() :]
    sep = re.search(r"\r?\n---\s*\r?\n", rest)
    if not sep:
        raise PromptLoadError("未找到 frontmatter 结束标记 ---")
    fm_raw = rest[: sep.start()]
    body = rest[sep.end() :].lstrip()
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError as e:
        raise PromptLoadError(f"YAML frontmatter 解析失败: {e}") from e
    if not isinstance(fm, dict):
        raise PromptLoadError("frontmatter 根节点必须是 mapping")
    return fm, body


def load_prompt(name: str, *, prompts_dir: str = "agent第二轮") -> Prompt:
    """
    name = 'pipeline-a-diagnose'（不带 .prompt.md 后缀）。
    prompts_dir 相对 repo root；也支持绝对路径。
    """
    root = _repo_root()
    pdir = Path(prompts_dir)
    if not pdir.is_absolute():
        pdir = root / pdir
    path = pdir / f"{name}.prompt.md"
    if not path.is_file():
        raise PromptLoadError(f"找不到 prompt 文件: {path}")
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    missing = sorted(_REQUIRED_FM_KEYS - set(fm))
    if missing:
        raise PromptLoadError(f"frontmatter 缺少必备字段: {', '.join(missing)}")
    extras = {k: v for k, v in fm.items() if k not in _REQUIRED_FM_KEYS}
    unknown = sorted(k for k in extras if k not in _OPTIONAL_FM_KEYS)
    if unknown:
        warnings.warn(
            f"prompt {name} frontmatter 含未知字段（仅告警）: {', '.join(unknown)}",
            stacklevel=2,
        )
    inputs = fm["inputs"]
    outputs = fm["outputs"]
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        raise PromptLoadError("inputs / outputs 必须是 list")
    forbidden = fm["forbidden_inputs"]
    if not isinstance(forbidden, list):
        raise PromptLoadError("forbidden_inputs 必须是 list")
    return Prompt(
        agent_id=str(fm["agent_id"]),
        version=str(fm["version"]),
        model_tier=str(fm["model_tier"]),
        inputs=inputs,
        outputs=outputs,
        forbidden_inputs=[str(x) for x in forbidden],
        single_responsibility=str(fm["single_responsibility"]),
        body=body,
        source_path=str(path),
        extra=extras,
    )


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for d in [here.parent, *here.parents]:
        if (d / ".cursorrules").exists() or (d / ".git").exists():
            return d
    return Path.cwd()
