# Phase 4 × Phase 1 × Phase 2 Crosscheck

## 1. 与 Phase 2 `01-验收清单对照.md`

| Phase 2 条目 | Phase 4 依赖关系 | 对齐结论 |
|--------------|------------------|----------|
| #7 `verdict ∈ {conditional_pass, fail}` → `status=awaiting_human` | inbox **只索引** `status=="awaiting_human"` | `_index.py` 过滤条件与 Phase 2 `run_stage_push` 一致 |
| #7 `next_action` 含 inbox 提示 | inbox 卡片 details 展示 `next_action` | fixture / manifest 字段可读 |
| `--force-pass` / `judge.accepted.json` | accept 命令 `--from push --force-pass` | 与 `phase2产出/03` §5.5 方案 A 一致；inbox **不**执行 merge |
| `manifest.json` schema §5.2 | `_index.py` 读 `run_id` / `question_md` / `created_at` / `status` | 未要求 Phase 2 必写 `a_summary`；从 `a.json` 兜底 `route`/`axis` |
| `--list-pending` CLI | 与 inbox 列表同源逻辑 | Phase 2 `list_pending_human()` 扫 manifest；inbox 扫 + 内联 judge（更适 file://） |

## 2. 与 Phase 2 `03-数据流与实现对照.md`

| Phase 2 节点 | Phase 4 |
|--------------|---------|
| non-pass → awaiting | inbox 列表数据源 |
| pass → merge + UI URL | **不在** inbox 显示（status≠awaiting_human） |
| `runs/<id>/judge.json` | `_index.py` 内联 `verdict/scores/fail_reasons/suggested_revisions` |

## 3. 与 Phase 2 `02-与phase1-crosscheck.md`

- Phase 4 **不调用** `run_a` / `run_b` / `run_judge`（符合 plan §3 禁读 `agents_runtime` 实现）。
- Phase 1「两步行 route_helper + run_a」与 inbox **无关**；用户从 inbox 仅 resume **push** stage。

## 4. 与 Phase 1 `01-验收清单对照.md`

| Phase 1 | Phase 4 |
|---------|---------|
| loader / context_builder / agents 可调用 | inbox 不依赖 Phase 1 模块 |
| E2E 仅 run_a 本机记录 | inbox 用独立 fixture，不阻塞 Phase 1 未完成的 B/Judge API 路径 |
| `route_context` 示例 JSON | inbox 展示 `route`/`axis` 来自 manifest `a_summary` 或 `a.json`（字段子集不同，仅展示用） |

## 5. 与 Phase 1 `04-模块实现索引.md`

- Phase 1 交付的 `agents_runtime/agents.py`：Phase 4 零 import。
- Phase 2 交付的 `orchestrate.py`：Phase 4 仅 **字符串** 引用 CLI 签名。

## 6. 接口契约差异（有意）

| 项 | Phase 2 plan 推荐 | Phase 4 实际 |
|----|-------------------|--------------|
| `a_summary` on manifest | 可选 | 无则读 `a.json`（`_index.py` L77–86） |
| accept 用 venv python | plan 示例 `python -m` | 与 plan §5.3 一致，用户可用 `./venv/bin/python3 -m …` 替换 |

## 7. `runs/.gitignore` 协调

- Phase 2：`runs/*` 默认忽略。
- Phase 4：增加 `!_index.py` / `!_index.js` / `!sample_fixture_*` 以便 fixture 与生成脚本可入库；真实 run 目录仍忽略。
