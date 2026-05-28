# Phase 2 × Phase 1 Crosscheck

对照 `agentflow3-tocode/phase1产出/` 与 Phase 2 plan §2 / §8.1，确认「Phase 1 黑盒 import + plumbing」连贯。

## 1. 与 `01-验收清单对照.md`（Phase 1）

| Phase 1 结论 | Phase 2 行为 |
|--------------|----------------|
| `run_a` 需 `route_helper_output`（否则模型走 `missing_route_helper`） | orchestrator **stage 0 固定** subprocess 调 `round2/route_helper.py --include-raw-answer-excerpt`，再 `run_a(..., route_helper_output=rh)`，满足 A 契约。 |
| `run_b` / `run_judge` 需 API | 未改 Phase 1 调用链，仅串起来。 |

## 2. 与 `02-环境与CLI.md`（Phase 1）

| Phase 1 文档 | Phase 2 |
|--------------|---------|
| 两步行：先 `route_helper` 再 `run_a` | 合并为一行 `python -m agents_runtime.orchestrate <question.md>`。 |
| `from agents_runtime import run_a, run_b, run_judge` | orchestrator 内部 `from .agents import run_a` 等同源；对外额外暴露 `from agents_runtime.orchestrate import run_single_case`（plan §8.2）。 |
| `--debug-dir` | orchestrator 将 `debug_dir` 固定为 `runs/<id>/_debug/`，与 Phase 1「可指定 debug 目录」并存（CLI 未再暴露 `--debug-dir`，见 `05-摩擦与后续.md`）。 |

## 3. 与 `03-黄金对照与Schema漂移.md`（Phase 1）

- Phase 1 已说明黄金 JSON 为 **v1**，当前 prompt 为 **v2.x**；Phase 2 **不做**「与黄金字面一致」的自动断言。
- Phase 2 plan §1 第 10 条「verdict 同向」仍依赖 **人工 + API**，与 Phase 1 文档 03 的风险描述一致。

## 4. 与 `04-模块实现索引.md`（Phase 1）

| Phase 1 模块 | Phase 2 使用方式 |
|----------------|------------------|
| `agents.py` 的 `run_a` / `run_b` / `run_judge` | 仅 import 调用；未读 implementation（符合 Phase 2 plan §3 对 Phase 1 internals 的禁读精神）。 |
| `context_builder` / `loader` / `llm_client` | orchestrator 不 import（符合 plan §3）。 |

## 5. 与 `05-摩擦与后续.md`（Phase 1）

- Phase 1「下一 phase = orchestrator」：**已落地** `agents_runtime/orchestrate.py`。
- 真 API 未跑通的缺口：与 Phase 1 相同，Phase 2 E2E checklist #1/#10 仍标 **需 key**。

## 6. 与 `route_context.example.new.json`

| 内容 | Phase 2 |
|------|---------|
| Phase 1 提供 `route: "new"` 最小样例供 CLI `run_judge` 第二参 | Phase 2 **不再要求人类手写**该文件：由 `_route_context_from_a(a)` 从 `a.json` 抽取 `route` / `target_ic_id` / `update_directives` / `raw_answer_seeds` / `meta_evidence`；其中 `raw_answer_seeds` **整段透传**（对齐 plan §5.3 + §7）。 |

## 7. 与 `compare_a_ball_trash.py`

- 仍为 **可选** 离线对比工具；orchestrator 不调用。验收 #10 若要做数值对比，可继续用手工脚本 + 新 `runs/<id>/a.json`。
