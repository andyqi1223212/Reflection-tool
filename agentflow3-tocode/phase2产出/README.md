# Phase 2 产出索引

本目录为 [`phase2-orchestrator.md`](../phase2-orchestrator.md) 的**执行级交付**：按 plan 章节逐项对照实现、验收状态，并与 [`phase1产出/`](../phase1产出/) 做 **crosscheck**。

| 文档 | 内容 |
|------|------|
| [00-plan逐条执行表.md](./00-plan逐条执行表.md) | plan §0–§9 章节 ↔ 实现状态索引 |
| [01-验收清单对照.md](./01-验收清单对照.md) | plan §1 checklist 逐条 ↔ 实现与证据（pytest / CLI） |
| [02-与phase1-crosscheck.md](./02-与phase1-crosscheck.md) | Phase 1 产出 01–05 + `route_context.example` 与 Phase 2 数据流对齐 |
| [03-数据流与实现对照.md](./03-数据流与实现对照.md) | plan §5（manifest / stages / merge / resume / CLI）↔ 代码位置 |
| [04-范围边界与风险.md](./04-范围边界与风险.md) | plan §6 不在范围、§7 风险、§9 实施顺序 ↔ 实际执行 |
| [05-摩擦与后续.md](./05-摩擦与后续.md) | 与 plan 样例输出差异、真机 E2E、Phase 3/4 衔接 |

**跨 Phase 审阅（非 plan 交付项）**：

| 文档 | 内容 |
|------|------|
| [../pipeline-b-context-curation-audit.md](../pipeline-b-context-curation-audit.md) | Pipeline B 读哪些文件/章节、重叠矩阵、实测字符量、瘦身建议 |

**新增代码（相对 Phase 2 plan §4.1）**：`agents_runtime/orchestrate.py`、`run_state.py`、`_subprocess.py`、`tests/test_run_state.py`、`tests/test_orchestrate_dry.py`；仓库根 `runs/.gitignore`（`*`）。**未改** `round2/*`、`agents_runtime/agents.py` 等既有文件（符合 plan §6）。
