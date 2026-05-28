# Round-2 试运行脚本与 agent workflow 的融合方式（含 v2 / 第二轮）

本文说明三层产物如何拼接在一起：

- **试运行 py 工具**：`round2/next_ic_id.py`（已实施）/ `round2/run_pipeline.py merge`（已实施）/ `round2/route_helper.py`（已实施，spec 见 [`route_helper.spec.md`](route_helper.spec.md)）
- **第二轮 prompt v2**：`agent第二轮/pipeline-a-diagnose.prompt.md` / `pipeline-b-style.prompt.md` / `judge.prompt.md`（已 bump v2，加入 route-aware）
- **现役 v1 与 prototype 链路**：`agents/*.prompt.md` 仍是 v1，`tools/export_v3_chains.py` 仍以 v3 markdown 为唯一来源生成 chains.json

**不修改**：现役 `agents/` v1 prompt、`tools/`、`data/chains.json` 直接写入路径——所有动作发生在 round2 / agent第二轮 草稿区，等用户 dogfood 通过再"转正"到主路径。

---

## 1. 当前 Agent Workflow 里卡在哪

按 `agents/README.md` 的推荐顺序，典型一次产出是：

1. **Pipeline A**（`pipeline-a-diagnose.prompt.md`）→ `agents/runs/run_*_pipeline-a_*.json`
2. **Pipeline B**（`pipeline-b-style.prompt.md`）→ `agents/runs/run_*_pipeline-b_*.json`（卡体 JSON，常带 `id: IC-NEW`）
3. **Judge**（`judge.prompt.md`）→ `agents/runs/run_*_judge_*.json`（`verdict` / `fail_reasons` 等）

之后若要**上线到原型站**，仍需人工：

- 把合规卡写进 `inquiry-chain-demo-v3-good-answer.md`
- 运行 `tools/export_v3_chains.py` → 更新 `data/chains.json` 与 `crystallization-prototype/chains.data.js`

**A.1 + A.2 解决的是「主键闭合 + 入库与 export 一键化」**：在 Judge `verdict == pass` 之后，由脚本接替人工改 id、拼 md、跑 export。

---

## 2. A.1（`next_ic_id.py`）在流程中的用法

**职责**：读取 `data/chains.json` 里已有 `IC-\d{3}` 的最大编号，打印 `max+1`（例如已有 `IC-024` 则打印 `IC-025`）。

**融合方式（试运行）**：

- **独立 CLI**：在跑 B 之前或之后，你在终端执行一次，把打印结果贴进对话，让模型在 B 输出里把占位 id 改成真实 id（若你仍希望 B 里手写数字 id）；或仅作「下一张将是几号」的心智锚点。
- **被 A.2 调用**：`run_pipeline.py merge` 内部会调用同一套逻辑分配新 id，**不要求**你先手跑 `next_ic_id.py`。

**转正到主仓库时**（未来某次 commit，非本次试运行）：

- 将脚本复制或迁移到 `tools/next_ic_id.py`。
- Round-2 plan 里还提到：把 `agents/pipeline-b-style.prompt.md` frontmatter 里 `id` 的 pattern 放宽为允许 `IC-NEW`（与 `^(IC-\\d{3}|IC-NEW)$` 一类），这样 B 的 JSON 可稳定用占位符，**主键由 merge 独占分配**。这一步属于 prompt 契约变更，等你结束试运行再改即可。

---

## 3. A.2（`run_pipeline.py merge`）在流程中的用法

**输入**：

- `--b`：Pipeline B 产出的 JSON（允许顶层含 `_meta`，merge 会剥离后再校验）。
- `--judge`：Judge 产出的 JSON。

**硬条件**：

- `judge.verdict` 必须为 `"pass"`，否则 exit code 2，不写文件。
- 卡体通过 `data/inquiry-chain.schema.json`（Draft-07）校验，否则 exit code 1。

**实际写入逻辑（与 Round-2 plan 文字略有对齐、但与「手写 chains.json」不同）**：

本仓库的 **`tools/export_v3_chains.py` 以 v3 markdown 为唯一来源**全量生成 `data/chains.json`。因此本试运行的 `merge` **不会**直接 `append` 到 `chains.json`，而是：

1. 用 `next_ic_id` 得到新 `IC-NNN`，赋给卡体。
2. 在 `inquiry-chain-demo-v3-good-answer.md` 中锚点 `## 3. 这版给产品的启发` **之前**插入一整段与现有 IC 相同结构的 markdown。
3. 调用 `tools/export_v3_chains.py` 再生成 `data/chains.json` 与 `crystallization-prototype/chains.data.js`。
4. 再调用 `tools/validate_chains_json.py`（若失败会提示，但 merge 已成功改 md + export；此时应人工查因）。

### 3.1 白话：输入输出、和「chains 那套」是啥关系

先澄清两个容易混的名词：

- **`_meta`（下划线 meta）**：只是 Pipeline B 的 JSON 里**多出来的一段说明**（谁跑的、读了哪些文件、备注等）。**不是**另一个叫 metamerge 的步骤。merge 入库时会把 `_meta` 整段扔掉，**只保留真正的卡片字段**（`id` / `title` / `patterns` / `axis` / `crystallization` / `chain` / `source_refs` 等），再去过 schema。
- **`merge`**：指的就是 `run_pipeline.py merge` 这一条命令：把「B 的卡 + Judge 的 pass」变成「写进 v3 正文 + 重新导出网站数据」。

**Judge 完之后，数据怎么进 demo v3 和网页？** 可以记一条链：

```text
Judge pass
    ↓
merge：读 B 的卡 JSON + Judge JSON → 剥 _meta → 换新 IC 编号 → 往 inquiry-chain-demo-v3-good-answer.md 里插一整张卡的 markdown
    ↓
自动跑 tools/export_v3_chains.py（像「编译器」）
    ↓
    ├─→ 写出 data/chains.json（给校验、给别的脚本读）
    └─→ 写出 crystallization-prototype/chains.data.js（给静态原型页读）
```

你打开 **`crystallization-prototype/index.html`** 时，页面读的是 **`chains.data.js`** 里的数据；**不是** merge 直接去改 HTML。所以：**demo v3 文件 = `inquiry-chain-demo-v3-good-answer.md`；网页上看到的卡 = export 根据这份 md 生成的 `chains.data.js`。**

**和仓库里「原本就有的」脚本的关系**：

| 文件 | 角色 |
|------|------|
| `inquiry-chain-demo-v3-good-answer.md` | **内容真相来源**：人维护的卡、merge 插入的新卡，都写在这里。 |
| `tools/export_v3_chains.py` | **早就有的**：只认这份 md，每次运行都会**根据 md 全文重新生成** `chains.json` + `chains.data.js`。 |
| `data/chains.json` | **导出产物**：不要当「手写编辑」的主文件；改了 md 再跑 export 就会被覆盖。 |
| `tools/validate_chains_json.py` | **早就有的**：检查当前的 `chains.json` 是否符合 `data/inquiry-chain.schema.json`。merge 在 export 之后顺带跑一下，帮你确认这一轮没导出坏数据。 |
| `round2/run_pipeline.py merge` | **新来的胶水**：替你完成「Judge 通过后 → 改 md → 调 export → 调 validate」这几步，避免你手抄 JSON 进 md、再忘跑 export。 |

一句话：**merge 不替代 `export_v3_chains.py`，而是帮你调用它；真正「进 v3」的是 md，真正「进网页」的是 export 写出来的 `chains.data.js`。**

**推荐命令形态**（在仓库根目录、已 `venv`）：

```bash
# 只看下一个 id
./venv/bin/python3 round2/next_ic_id.py

# 演练：校验 + 打印将插入的 md，不写文件
./venv/bin/python3 round2/run_pipeline.py merge \
  --b agents/runs/run_*_pipeline-b_*.json \
  --judge agents/runs/run_*_judge_*.json \
  --dry-run

# 真入库（会改 v3 md 并跑 export）
./venv/bin/python3 round2/run_pipeline.py merge \
  --b agents/runs/run_*_pipeline-b_*.json \
  --judge agents/runs/run_*_judge_*.json
```

可选参数：`--md`（非默认 v3 路径时）、`--chains`（非默认 `data/chains.json` 时）。

**融合进「五步」叙述的改法**（文档/心智即可，不必改代码）：

在 `agents/README.md` 的「调用顺序」中，在 Judge 之后增加一步 **5b — Merge（本地脚本）**：仅当 `verdict=pass`；产物进入 v3 md → export → 打开 `crystallization-prototype/index.html` 做 dogfood。

**已知与 export 脚本的耦合（merge 前请知悉）**：

当前 `export_v3_chains.py` 会把**所有**解析到的卡片的 `created_at` 设为**运行日当天**。这是既有行为，不是 `round2` 引入的；若你希望历史卡的 `created_at` 不被批量刷新，需要先改 export 脚本再推广 merge（仍属「转正」时的工作，不在本次试运行改文件范围内）。

---

## 4. 与 Judge / B 契约的小对齐点（可选）

- Judge JSON 里常有 `card_id: IC-NEW`；B 里可能已是具体 id（例如历史跑场已改成 `IC-024`）。**merge 以 `next_ic_id` 为准覆盖 `id`**，避免与库内最大号冲突。
- 若同一张卡已经写入 v3（例如 `### IC-024：` 已存在），再对同内容跑一次 merge 会得到下一张号；**应用前应用 `--dry-run` 看标题与 trigger**，避免重复入库。Round-2 后续 **A.3**（trigger 碰撞提示）就是为这层人工决策服务的。

---

## 5. 从试运行「转正」到工程默认路径时建议做的一次性清单

1. 将 `round2/next_ic_id.py`、`round2/run_pipeline.py` 迁到 `tools/`（或保留 `round2` 仅作文档示例，以 `tools` 为 canonical）。
2. 更新根 `README.md` / `agents/README.md`：在 source of truth 表或 workflow 图里写明 **Judge pass → merge → export**。
3. （Plan 附带）调整 Pipeline B prompt frontmatter：`id` 允许 `IC-NEW`。
4. 视需要收紧 `merge`：比对 `judge.card_id` 与 B 卡 `id` 是否一致、或强制 Judge 输出里带 `content_sha` 等防误合并（属增强项）。

---

## 6. 本轮文件清单

| 文件 | 状态 | 作用 |
|------|------|------|
| `round2/next_ic_id.py` | ✅ 已实施 | A.1：打印下一个 `IC-NNN` |
| `round2/run_pipeline.py` | ✅ 已实施（v0.5 范围内的 `merge` 子命令） | A.2：Judge pass 后 → 改 v3 md → 跑 export |
| `round2/route_helper.spec.md` | ✅ spec + py 已对齐 | 第二轮 stage 0：扫 chains.json 给 A 喂 candidates + route_hint |
| `round2/route_helper.py` | ✅ 已实施 | 见 [`route_helper.spec.md`](route_helper.spec.md) |
| `agent第二轮/pipeline-a-diagnose.prompt.md` | ✅ v2.1（2026-05-15：删 raw_answer_md 独立 input；raw answer 入口收敛到 route_helper.raw_answer_excerpt） | 第二轮 A：诊断 + 路由（new / update / meta） |
| `agent第二轮/pipeline-b-style.prompt.md` | ✅ v2 | 第二轮 B：按 route 输出 full_card / patch / meta_card |
| `agent第二轮/judge.prompt.md` | ✅ v2 | 第二轮 Judge：6 维度评分 + §5.7 route-aware 一致性检查 |
| `agent第二轮/push.prompt.md` | ✅ v1（2026-05-15 新增；`model_tier: plumbing`，不调 LLM） | Judge pass 后的 runbook：触发 `run_pipeline.py merge` → 提示刷新 prototype UI |
| `round2/A1-A2与agent-workflow融合说明.md` | ✅ 本文 | workflow 衔接说明 |

---

## 7. 第二轮 workflow：raw-answer aware + route-aware（v2）

**✅ `route_helper.py` 已实施，本节 Step 0 命令可直接用**（实现见 `round2/route_helper.py`，契约见 [`route_helper.spec.md`](route_helper.spec.md)）。

**`route_helper.spec.md` §10 实施自检（composer 已勾）**

- [x] 只依赖标准库
- [x] `repo_root()` 用 `Path(__file__).resolve().parents[1]`
- [x] stdout 单段 JSON，`ensure_ascii=False, indent=2`
- [x] spec §5 两个 smoke test 已跑通
- [x] 不写任何文件
- [x] 不抓 LLM SDK
- [x] 文件顶部 docstring 引用本 spec
- [x] 与 `round2/next_ic_id.py` 风格一致（无吞 traceback、stderr 用 `print(..., file=sys.stderr)`）

> 第二轮在 v1 基础上**保留原框架**（A → B → Judge → merge），但每个 stage 都加了 route-aware 分支。**不**拆 sibling prompts（plan §10 的激进方案已放弃），改为单 prompt 内化分支。

### 7.1 全景图

```mermaid
flowchart LR
  qmd["question_md<br/>(若含 # *response 段，py 会自动抽进 raw_answer_excerpt)"] --> rh["Step 0: route_helper.py<br/>--include-raw-answer-excerpt<br/>(round2/route_helper.spec.md)"]
  rh -->|stdout JSON<br/>(candidates + route_hint + raw_answer_excerpt)| A["Pipeline A v2.1<br/>(诊断 + 路由)"]
  A -->|route + 配套字段| B["Pipeline B v2<br/>(按 route 三分支)"]
  B -->|output_kind: full_card / patch / meta_card| J["Judge v2<br/>(6 维度 + §5.7 route-aware)"]
  J -->|verdict=pass| push["push.prompt.md<br/>(plumbing runbook)"]
  push --> py["run_pipeline.py merge<br/>--mode {new|update|meta}<br/>(update/meta 待扩展)"]
  py --> md[(inquiry-chain-demo-v3-good-answer.md)]
  md --> export["tools/export_v3_chains.py"]
  export --> dataJs["crystallization-prototype/chains.data.js"]
```

### 7.2 调用顺序（一次完整跑通）

#### Step 0：终端跑 route_helper

```bash
./venv/bin/python3 round2/route_helper.py \
    --question 外部source/<your_question>.md \
    --top-k 5 \
    --include-raw-answer-excerpt
```

把 stdout 整段 JSON 复制——下一步粘给 A。

#### Step 1：跑 Pipeline A v2

新 chat，flagship model：

```
@agent第二轮/pipeline-a-diagnose.prompt.md
@外部source/<your_question>.md

# route_helper_output
<Step 0 的 stdout JSON。若 question_md 含 # *response 段，--include-raw-answer-excerpt 已把 raw_answer_excerpt 字段塞在里面，A 直接读，**不必再手动剪贴 raw answer**（v2.1 收敛）>

# Schema excerpts
@context/crystallization-schema-v0.md

# Synthesis excerpts
@context/raw-questions-synthesis.md

# v3 few-shot
- route=new / meta：3 张同 axis / 同主题 IC（直接复制原文）
- route=update：候选 target_ic_id 那张完整原文 + 2 张同 axis fewshot
```

A 输出 JSON 含 `route` + 配套字段。存到 `agents/runs/run_<date>_pipeline-a_<scenario>.json`。

#### Step 2：跑 Pipeline B v2

新 chat，normal model：

```
@agent第二轮/pipeline-b-style.prompt.md

# pipeline_a_draft
<粘 Step 1 输出>

# existing_card_json  (仅 route=update 时必填)
<从 data/chains.json 抽出 target_ic_id 那一项 object>

# style brief / annot register / schema lint
@context/crystallization-style-agent-brief.md
@回答版本explore/良质回答标注册.md
@context/crystallization-schema-v0.md

# v3 fewshot
- route=new / meta：1-2 张同 axis
- route=update：existing_card_json 已是基准
```

B 输出按 `output_kind` 分三种形态。存到 `agents/runs/run_<date>_pipeline-b_<scenario>.json`。

#### Step 3：跑 Judge v2

新 chat，flagship model：

```
@agent第二轮/judge.prompt.md

# b_output
<粘 Step 2 输出>

# route_context  (A 的精简版)
<从 Step 1 输出抽出 route / target_ic_id / update_directives / meta_evidence / raw_answer_seeds.not_for_anchor>

# existing_card_json  (仅 route=update 时必填)
<从 chains.json 抽出 target_ic_id>

# Rubric / Schema lint / v3 reference
@回答版本explore/良质回答标注册.md
@context/crystallization-schema-v0.md
<paste 1-2 v3 cards>
```

Judge 输出 6 维度 scores + `route_aware_checks` + 最终 verdict。存到 `agents/runs/run_<date>_judge_<scenario>.json`。

#### Step 4：跑 push（runbook 触发 merge / update / meta 待扩展）

**route=new 现已可用**——通过 [`agent第二轮/push.prompt.md`](../agent第二轮/push.prompt.md) 触发，或直接在终端跑：

```bash
./venv/bin/python3 round2/run_pipeline.py merge \
    --b agents/runs/run_<date>_pipeline-b_<scenario>.json \
    --judge agents/runs/run_<date>_judge_<scenario>.json
```

push runbook 单独存在的价值（不是冗余）：

- 把 verdict 闸门 / exit code 分流 / 反 anti-pattern（不擅自手改 JSON、不擅自把 conditional_pass 当 pass）写进 prompt，让 Cursor agent 也能按部就班触发，不漏步
- `model_tier: plumbing`——**不消耗 LLM token**，是 push 的"runbook 化"形态

**update / meta 仍待 composer 扩展**（v0.5 范围之外）：

```bash
./venv/bin/python3 round2/run_pipeline.py merge \
    --b agents/runs/run_<date>_pipeline-b_<scenario>.json \
    --judge agents/runs/run_<date>_judge_<scenario>.json \
    --mode {new|update|meta}
```

按 `output_kind` 走不同分支：

- `new` / `meta`：与 v1 行为一致（v3 md 插入新卡 → export）
- `update`：将 `patch` 深度合并到 v3 md 中 `target_ic_id` 那张 section → export
  - 嵌套字段用点路径合并（`crystallization.mechanism` 直接替换原值；`chain.questions` 数组按 B 给的完整新数组全量替换；`alt_anchors` 作为新字段追加到 crystallization 下，v0.5 schema 暂兼容）
  - `created_at` 不改；新增 `updated_at`
  - **重要**：v3 md 是文本格式，patch 入库要求 export 端能反查 IC ID 到对应 section 起止行；A.2 现版可能要先扩展。具体改法见 §8 "merge --mode update 实施提示"

### 7.3 stage 之间的契约总表

| 上游字段 | 下游字段 | 落地者 | 检查者 |
|---|---|---|---|
| route_helper.candidates[] | A.diagnostic_notes.route_reasoning | A | Judge（不直接 check，但 A 的 route_reasoning 必须引 helper 的 top1 IC + score + confidence） |
| route_helper.raw_answer_excerpt | A.raw_answer_seeds | A | B（B 优先用 insight_quotes 写 anchor，严守 not_for_anchor） |
| A.route | B.output_kind | B | Judge（output_kind 必须 = `{new→full_card, update→patch, meta→meta_card}`） |
| A.update_directives | B.patch | B | Judge §5.7 `patch_scope` + `patch_no_directive_leak` |
| A.meta_evidence.child_ic_ids | B.meta_relation.child_ic_ids | B | Judge §5.7 `meta_relation_passthrough` |
| A.raw_answer_seeds.not_for_anchor | B.crystallization.anchor 的护栏 | B | Judge §5.7 `not_for_anchor_respected` |
| existing_card_json | B 写 patch 时的合并基准 | B | Judge（合并 patch 后再对"合并后卡"打 6 维度） |
| B.patch.updated_at | run_pipeline.py merge --mode update 写入 v3 md | py | — |

---

## 8. merge --mode update 实施提示（给 composer）

A.2 现版（`run_pipeline.py merge`）只支持 `new`——往 v3 md 插一整段。`update` / `meta` 模式扩展时，需要在不破坏现有 `tools/export_v3_chains.py` 解析逻辑的前提下：

### 8.1 v3 md 中卡 section 的边界识别

每张卡的 section 在 v3 md 里的形态是：

```markdown
### IC-012：睡前上厕所 / 入睡失败后的刷新机制

**Crystallization**

机制：...

入口句：

> 不刷新，也可以安全。

小动作：

1. 只允许一次睡前整理 + 一次上厕所...
2. ...
3. ...

**Pattern tags**：`P-SPIRAL` `P-EXIST` `P-OVER`

**Axis**：`attention`

**Source refs**：H05、F10

<details>
<summary>Trigger / 追问路径</summary>

**Trigger**：...

**追问路径**：

- ...

</details>

---
```

merge update 模式应：

1. 用 regex 找到 `### IC-012：` 这一行作为 section 起始
2. 找到下一个 `### IC-NNN：` 或 EOF 作为 section 终止
3. 在该 section 范围内做字段级替换：
   - `crystallization.mechanism` → 替换 "机制：" 后的段落
   - `crystallization.anchor` → 替换 "入口句：" 下的 `> ...` 行；若有 `alt_anchors`，作为 `> ...` 下面新增一行 `_备选锚（v2）_: > xxx`（具体格式待定，要让 `export_v3_chains.py` 也认）
   - `crystallization.micro_steps` → 替换 "小动作：" 下的有序列表整段
   - `patterns` → 替换 `**Pattern tags**：` 后的 backtick 序列
   - `chain.questions` → 替换 `<details>` 内的 `- ...` 列表
   - 等等

### 8.2 alt_anchors 的兼容策略

v0.5 schema 没有 `alt_anchors` 字段。建议：

- merge 写 v3 md 时把 alt_anchors 渲染成可见 markdown（如 "_备选锚_：> xxx"）
- `export_v3_chains.py` 暂时**不**解析 alt_anchors 进 chains.json（兼容 schema-v0）；composer 在 v1 schema 时再加 `crystallization.alt_anchors`
- 这样 v3 md 是 source of truth，alt_anchors 信息保留；chains.json 暂时丢这一字段不影响 prototype 渲染

### 8.3 meta_relation.child_ic_ids 的兼容策略

同上：merge 写 v3 md 时渲染为 "_横切：IC-009 / IC-010 / ... / IC-014_"；chains.json 暂不导出，v1 schema 时再加 `meta_relation` 字段。

### 8.4 trigger 碰撞检测（Round-2 plan §3 A.3）的位置

merge --mode new 时仍需要 trigger 碰撞检测——但 v2 的 `route_helper.py` 已经在 stage 0 做过相同的事。建议：

- 信任 A 已经看过 helper candidates 做了路由判定
- merge --mode new 仍可保留一道 last-resort 字符匹配（>70% 重叠则 CLI 提示），但**不阻断**——A 已经判定了 route=new 意味着用户接受了"虽然有重叠但本质不同"

---

## 9. 当前未决问题

| # | 问题 | 当前决策 | 待 dogfood 后确认 |
|---|---|---|---|
| 1 | route_helper.py 阈值是否合理（update_high=0.40 / update_medium=0.13） | 按 spec §4.7 默认值落地 | 跑 3-5 份真实 raw md 后看 hint 准确率，再调 |
| 2 | A 的 fewshot 在 route=update 时是否必须含 target_ic_id 完整原文 | 是（A prompt §3 已规定） | dogfood 看 A 是否还会忽略原文 |
| 3 | B 的 patch 字段命名是 `crystallization.mechanism` 还是 `mechanism`（嵌套 vs 扁平） | 点路径嵌套（与 schema 字段路径一致） | py merge 实施时再校准 |
| 4 | meta_card 是否要在 chains.json 里有独立字段 vs source_refs 字符串塞 | v0.5 用 source_refs 字符串 + meta_relation 临时字段；v1 加 schema | v1 schema 升级时统一 |
| 5 | A 的 raw_answer_seeds 是否真能提升 anchor 质量 | 待 dogfood 验证 | 跑 IC-012 update + IC-025 meta 各一次看 judge_report |

---

## 10. 从试运行「转正」到工程默认路径的清单（更新版）

1. ✅ `round2/next_ic_id.py` / `round2/run_pipeline.py` 已实施
2. ✅ `round2/route_helper.py` 已实施（按 [`route_helper.spec.md`](route_helper.spec.md)）
3. ✅ Pipeline A v2.1（2026-05-15）：删 `raw_answer_md` 独立 input，raw answer 入口收敛到 `route_helper.py --include-raw-answer-excerpt`（py plumbing 抽，prompt 不重复搬运；符合 conventions 铁律 6）
4. ✅ `agent第二轮/push.prompt.md` v1（2026-05-15）：Judge pass 后的 plumbing runbook，把 verdict 闸门 + merge + UI 提示串成显式 5 步走
5. ⏳ `round2/run_pipeline.py` 扩展 `merge --mode {new|update|meta}` 子命令（按本文 §8）
6. ⏳ 一次完整 dogfood：用 `外部source/学校压力下的代偿性控制.md` 跑 A→B→Judge→push（route=update IC-012）；同 md 再跑一次 route=meta 产出 IC-025（plan §10.3 已经准备好诊断结论作为对照参考）
7. ⏳ dogfood 通过后再将 `round2/*.py` 迁到 `tools/`、`agent第二轮/*.prompt.md` 覆盖到 `agents/`
8. ⏳ 同步更新根 `README.md` / `agents/README.md` 反映 v2 workflow
9. ⏳ schema-v0 → v0.1 微升级：加 `alt_anchors`（数组 ≤2）+ `updated_at`（date）+ `meta_relation.child_ic_ids`（v0.5 兼容字段正式化）

在以上 1-6 全部完成前，**不**触动 `agents/` v1 与 `tools/` 现役脚本——保护 prototype 站点持续可用。
