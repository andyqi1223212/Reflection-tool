# 黄金 JSON 与当前 Prompt 契约漂移

Plan §1 要求对照 `agents/runs/run_*_ball-trash-talk.json`（**v1 黄金**）与本机 E2E（**v2.2 + 已有 IC-024 库**）。

## 三份 A 相关产物

| 文件 | 何时 | `route` | 说明 |
|------|------|---------|------|
| `agents/runs/run_2026-05-11_pipeline-a_ball-trash-talk.json` | 2026-05-11 chat/v1 | 无 | 隐式 new；含 `mechanism_sketch`；patterns 含 **P-UNDER** |
| `agents/runs/run_2026-05-12_pipeline-b_ball-trash-talk.json` | B 产出已 merge | — | 库内 **IC-024** 正文来源 |
| [run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json](./run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json) | Phase 1 agents_runtime | **update** → IC-024 | helper top1 score≈0.71 confidence=high；`update_directives` + `raw_answer_seeds` |

## Pipeline A：黄金 v1 vs 本机 E2E（2026-05-19）

| 字段 | 黄金 v1 | 本机 E2E | 备注 |
|------|---------|----------|------|
| `route` | 无 | `update` | v2.2 必填；与「库中已有同 trigger 卡」一致 |
| `target_ic_id` | 无 | `IC-024` | 与 route_helper / B 黄金一致 |
| `axis` | `attention` | `attention` | 一致 |
| `patterns` | EVAL, UNDER, EFF, KNOW-DO | EVAL, **SPIRAL**, EFF, KNOW-DO | SPIRAL 对应「weak/怂」纠结；UNDER 未入选 |
| 机制层 | `mechanism_sketch` | `update_directives.mechanism` 等 | update 路径不写 sketch |
| `raw_answer_seeds` | 无 | 2× `user_self_reflection` | v2.2 亮点 |
| `diagnostic_notes.route_reasoning` | 无 | 有，引 helper | v2.2 必填 |

**建议**：真 API 回归仍以「`axis` 一致、patterns 大体同族、路由语义合理」为主；勿强求与 v1 黄金字面相同（尤其 `route` / `P-UNDER`）。

## Pipeline B 黄金

| 字段 | 黄金 | 当前 B v2.1 |
|------|------|-------------|
| `output_kind` | 无 | `full_card` / `update_entry` / `meta_card` |
| `id` | `IC-024` | update 时为 `update_entry` + `target_ic_id` |

本机 E2E 的 A 为 **update** → 下一步 B 应走 **update_entry**，且需 **existing_card_json**。

## Judge 黄金

| 字段 | 黄金 v1 | Judge v2.1 |
|------|---------|--------------|
| `output_kind` / `route_aware_checks` | 无 | 必填结构 |

## `route_context` 样例

| 文件 | 用途 |
|------|------|
| [route_context.example.new.json](./route_context.example.new.json) | `route=new` 最小样例 |
| [route_context.example.update_ic024.json](./route_context.example.update_ic024.json) | 与本机 E2E A 对齐的 **update / IC-024** |

`run_judge` 第二条参数从 A 输出摘：`route`、`target_ic_id`、`update_directives`、`raw_answer_seeds`（及可选 `meta_evidence`）。
