# Phase 1 产出索引

本目录为 [`phase1-prompt-callable.md`](../phase1-prompt-callable.md) 的**执行级交付**：对照 plan 全文（§0–§9）说明实现位置、验收状态与人工步骤。

**状态摘要（2026-05-19）**：本机已跑通 **`route_helper` + `run_a`**（球场垃圾话）；`run_b` / `run_judge` 仍待 API + update 路径需 `existing_card`。

| 文档 | 内容 |
|------|------|
| [01-验收清单对照.md](./01-验收清单对照.md) | 逐条对应 plan §1 checklist（含 E2E 勾选） |
| [02-环境与CLI.md](./02-环境与CLI.md) | `.env`、route_helper 两步行、`agents_runtime.agents` |
| [03-黄金对照与Schema漂移.md](./03-黄金对照与Schema漂移.md) | v1 黄金 vs 本机 E2E（update/IC-024） |
| [04-模块实现索引.md](./04-模块实现索引.md) | plan §4/§5 文件 ↔ 代码映射 |
| [05-摩擦与后续.md](./05-摩擦与后续.md) | 已做 / 未做 / Phase 2 |
| [06-本机E2E-run_a记录.md](./06-本机E2E-run_a记录.md) | **本次成功 run 的命令、对照表、下一步** |
| [run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json](./run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json) | 本机 A 产出快照 |
| [route_context.example.new.json](./route_context.example.new.json) | `route=new` 样例 |
| [route_context.example.update_ic024.json](./route_context.example.update_ic024.json) | 与本机 E2E 对齐的 `route=update` 样例 |
| [compare_a_ball_trash.py](./compare_a_ball_trash.py) | 可选：`axis` + `patterns` 与黄金 v1 对比 |

代码根目录：`agents_runtime/`（plan §4.1）。
