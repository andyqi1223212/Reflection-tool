"""agents_runtime：Phase 1 可调用算子（懒加载避免 `python -m agents_runtime.agents` 双导入告警）。"""

from typing import Any

__all__ = ["run_a", "run_b", "run_judge"]


def __getattr__(name: str) -> Any:
    if name == "run_a":
        from .agents import run_a

        return run_a
    if name == "run_b":
        from .agents import run_b

        return run_b
    if name == "run_judge":
        from .agents import run_judge

        return run_judge
    raise AttributeError(name)
