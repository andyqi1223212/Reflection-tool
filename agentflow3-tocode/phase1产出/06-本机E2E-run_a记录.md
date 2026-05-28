# 本机 E2E：`run_a` 球场垃圾话（2026-05-19）

## 命令（仓库根）

```bash
./venv/bin/python3 round2/route_helper.py \
  --question 外部source/球场垃圾话应对策略.md \
  --top-k 5 \
  --include-raw-answer-excerpt > /tmp/route_helper.json

./venv/bin/python3 -m agents_runtime.agents run_a \
  外部source/球场垃圾话应对策略.md \
  /tmp/route_helper.json
```

**体感**：第二条命令在返回 JSON 前终端可能长时间无输出（大 system prompt + v4-pro 思考），属正常。

## 产出落盘

完整 JSON：[run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json](./run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json)

下游 `run_b` / `run_judge` 用的 `route_context` 样例（update / IC-024）：[route_context.example.update_ic024.json](./route_context.example.update_ic024.json)

## 与黄金 A（`agents/runs/run_2026-05-11_pipeline-a_ball-trash-talk.json`）对照

| 维度 | 黄金 v1（2026-05-11） | 本机 E2E（2026-05-19） | 判定 |
|------|----------------------|------------------------|------|
| `axis` | `attention` | `attention` | 一致 |
| `patterns`（集合） | P-EVAL, P-UNDER, P-EFF, P-KNOW-DO | P-EVAL, P-SPIRAL, P-EFF, P-KNOW-DO | 部分重叠；本 run **无 P-UNDER**、**增 P-SPIRAL**（与 route_reasoning 中「weak/怂」螺旋一致） |
| `route` | 无（v1 未写） | `update` | 契约漂移 + **库内已有 IC-024**（route_helper top1 score≈0.71 confidence=high） |
| `target_ic_id` | 无 | `IC-024` | 与 helper + 已入库卡一致，合理 |
| 机制文本 | `mechanism_sketch`（new 路径） | `update_directives.*`（update 路径） | 形态不同但语义同向：脑子紧/评分系统/ego |
| `raw_answer_seeds` | 无 | 有；`user_self_reflection` 两条 NPC/人格分开 | v2.2 能力体现良好 |
| `diagnostic_notes.route_reasoning` | 无 | 引用 helper top1 + 语义覆盖 | v2.2 必填项满足 |

**结论（Phase 1 §1 checklist #2）**：`axis` 一致；`patterns` 集合不完全一致但在可接受范围内（helper 指向已存在 IC-024 → **update** 比黄金 v1 的隐式 new 更符合当前数据现实）；自由文本需人工认为「同向」——本 run 用户主观评价为不错。

## 建议下一步（仍未做）

```bash
# 存 A 输出后跑 B（route=update 须从 data/chains.json 抽 IC-024 作 existing_card，或等 Phase 2 orchestrate）
./venv/bin/python3 -m agents_runtime.agents run_b \
  agentflow3-tocode/phase1产出/run_2026-05-19_e2e_pipeline-a_ball-trash-talk.json \
  # 第二个参数：从 data/chains.json 摘出的 IC-024 整卡 JSON（手造文件）

# Judge：b.json + route_context.example.update_ic024.json [+ existing_card]
```

`run_b` 在 `route=update` 时 **必须** 提供 `existing_card_json`（见 B prompt `missing_existing_card`）。
