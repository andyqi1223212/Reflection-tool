# Agent Prompt Conventions — L5 Writing Discipline

> 这份文档是 `agents/` 目录下**所有 prompt 文件必须遵守的写作纪律**。
> 它不是 prompt 本身，是写 prompt 时的规则。
> 任何一份 prompt 偏离这些规则 → 等于把项目拉回 L4。

读这份文档前，先把 [`外部source/产品.txt`](../外部source/产品.txt) §L5 三能力（第 542-620 行）刷一遍。本文档只是把那三条抽象能力翻译成**可执行的写作规则**。

---

## 0. 一句话总纲

> **Prompt = 函数。它必须有 signature（input/output 契约）、单一职责、可对比版本、明示边界（含失败回退）。**
>
> 你写的不是"给 AI 的请求"，是**给项目的一段可重用基础设施**。

L4 的 prompt 是"AI 你帮我做 X"；L5 的 prompt 是 `def diagnose(question_md, brief) -> ICChainDraft | FailureReason`。

---

## 1. 强制 frontmatter（每份 prompt 都必须有）

每份 `*.prompt.md` 文件**开头**必须有 YAML frontmatter，缺一项不准跑：

```yaml
---
agent_id: pipeline-a-diagnose
version: v1
model_tier: flagship              # flagship | normal
inputs:                           # 严格说明输入是什么（文件 / 字段 / 体量）
  - { name: question_md, type: markdown_file, max_tokens: 30000 }
outputs:                          # 严格说明输出格式
  - { name: ic_chain_draft, type: json, schema_ref: "context/crystallization-schema-v0.md#section-2" }
forbidden_inputs:                 # 明令禁止读什么（防 context 漂移）
  - "外部source/*.md (除当前任务指定的那一份)"
  - "回答版本explore/*.md (除标注册)"
single_responsibility: "把 1 份纯问题 md 诊断为 IC chain 草稿；不做风格化、不写 anchor、不写文件"
failure_mode: "若信息不足以诊断，输出 {\"status\": \"insufficient\", \"reason\": \"...\"}, 禁止瞎编"
upstream: null                    # 谁的输出是我的输入；为 null 表示链路起点
downstream: [pipeline-b-style]    # 谁会消费我的输出
created: 2026-05-11
last_iter: null                   # 每次迭代更新；含 "what changed / score delta"
---
```

**字段语义**：

| 字段 | 为什么必填 | 违反代价 |
|---|---|---|
| `agent_id` | 跨文件引用、Scratchpad 追溯 | 半年后不知道这是谁 |
| `version` | 对比迭代（L5 Iterative Mindset 核心） | 没法跑 prompt v1 vs v2 |
| `model_tier` | 控制成本 + 控制能力 | 用错档位输出降几个等级 |
| `inputs` / `outputs` | 接口契约 | 下游 agent 接错数据 |
| `forbidden_inputs` | 防 P1 attention 稀释、P2 context 累积 | context 满你只能怪自己 |
| `single_responsibility` | 防 L4 全能外包思维 | 一份 prompt 包打天下，没法 swap 模型、没法独立 eval |
| `failure_mode` | 防 LLM "幻觉式自信" | 不知道哪些是模型瞎编的 |
| `upstream` / `downstream` | workflow 拓扑可视 | 重构时不知道改这个会断谁 |
| `last_iter` | 留迭代账本 | 见 §6 |

---

## 2. Prompt 正文结构（按顺序，不准乱）

每份 prompt 正文（frontmatter 之下）必须按下面 7 节，**顺序固定**：

```markdown
## 1. 角色（你是谁）
一句话，最多两句。

## 2. 任务（你要做什么）
一句话动词开头，可以分 2-3 步骤。**严禁出现"分析"这种空动词**——必须说清楚分析什么、产出什么。

## 3. 输入契约
明确列出每个 input：
- 名字 / 来源（文件路径或上游 agent_id）
- 你应该读这个 input 的【哪些部分】（不是全部）
- 不该读的部分明令禁止

## 4. 输出契约
- 输出格式（JSON / 纯文本 / md）
- 完整 schema（字段名 / 类型 / 约束 / 必填可选）
- 一个 well-formed example
- 失败回退格式

## 5. 反例（**至少 3 个**）
直接引用 schema §6 或自己写。格式：
- 反例：<bad output>
- 为什么不好：<一句话>
- 应该怎样：<一句话或改后的版本>

## 6. Few-shot examples（1-3 个）
- 必须是真实从 v3 / 标注册抠出来的，不许编
- 每个 example：input → reasoning（可省）→ output
- 用 `### Example N` 分节

## 7. 自检 checklist（agent 输出前自查）
LLM 输出前默念 5-7 条检查项。比如：
- [ ] 输出是合法 JSON
- [ ] 所有 required 字段都填了
- [ ] anchor 长度 ≤ 20 中文字符
- [ ] 没有引用禁止的输入文件
- [ ] 不确定的字段标 "unknown" 而非编造
```

**为什么是这 7 节、为什么这个顺序**：

| 节 | 解决的 L5 问题 |
|---|---|
| 1 角色 | 给 agent 一个稳定的 self-model，减少 persona 漂移 |
| 2 任务 | 单一职责的口语化锚点 |
| 3 输入契约 | Context Engineering 的第一道闸 |
| 4 输出契约 | Structured Output（产品.txt §L5 第 538 行） |
| 5 反例 | 让 agent 知道**不该做什么**——这比说"该做什么"更高效 |
| 6 Few-shot | LLM 学风格最快的方式是看例子 |
| 7 自检 | agent 在输出前再过一遍 schema，把错误前置拦截 |

---

## 3. Context Engineering 具体规则

**铁律 1：每个 prompt 显式列出所有 input，禁止"读项目所有文件"**

❌ "你可以参考项目里相关文档"
✅ "输入仅限：(1) `agents/conventions.md` §2 / §5; (2) 上游 pipeline-a 输出的 JSON; (3) `context/crystallization-style-agent-brief.md` §4 / §8"

**铁律 2：明令禁止读什么**

每个 prompt 必须有 `forbidden_inputs` frontmatter 字段 **+** 正文 §3 末尾明文重申。理由：LLM 看到 @file 引用经常会"顺便也读一下相关的"，必须明文阻断。

**铁律 3：input 拆"哪部分"，不喂整篇**

❌ "读 vision.md 了解项目"
✅ "读 vision.md §3 灵魂 + §5 分类引擎；其余章节不读"

**铁律 4：上游 agent 的输出当结构化数据用，不当 prose 读**

如果上游是 JSON，prompt 写："上游 pipeline-a-diagnose 的输出 JSON 包含字段 X / Y / Z；把它当 metadata 引用，不要把 chain.questions 当原始素材"——防 B 把 A 草稿当 trigger md 来读。

---

## 4. Single Responsibility 具体规则

**铁律 5：一个 prompt 只输出一种结构**

❌ "输出诊断 + 草稿三层卡 + 评分"
✅ "只输出 IC chain draft JSON。评分 / 风格化 / 入库不是你的事"

**铁律 6：禁止 agent 写文件 / 调 API**

agent 输出 JSON 就停。**写不写 chains.json 是 py 的事**——py 是 trusted 执行层，agent 是 untrusted 生成层。

❌ "如通过则写入 data/chains.json"
✅ "输出 JSON。后续由 [`tools/run_pipeline.py`](../tools/run_pipeline.py) 决定是否写入"

**铁律 7：禁止 agent 自评 / 自审**

A 不能给自己评分；B 不能审 A。评分是 judge agent 的事。理由：自评有强烈 confirmation bias。

---

## 5. Failure Mode 必写

每份 prompt 末尾必须明示**两种**失败回退：

1. **信息不足型**：输入信息不够做出靠谱判断 → 输出 `{"status": "insufficient", "reason": "...", "missing": ["..."]}`；**禁止瞎编填充**
2. **格式型**：无法输出合法 JSON → 输出纯文本 `FAILURE: <reason>`，**禁止用 markdown code fence 假装是 JSON**

这一条直接对应产品.txt §L6 第 681 行：当 agent 超过失败阈值，把控制权交还人类。**L5 的雏形版本**就是：不会就说不会。

---

## 6. Iterative Mindset 具体规则

**铁律 8：每次改 prompt 必须更新 frontmatter `last_iter` 字段**

格式：
```yaml
last_iter:
  date: 2026-05-12
  version_bump: v1 -> v2
  changed: "anchor 反例加 schema §6.2 公式化那个；约束加'读出口必须有咯噔感'"
  baseline_score: { anchor: 3.0, mechanism: 4.0, micro_steps: 3.5 }
  new_score:      { anchor: 4.2, mechanism: 4.0, micro_steps: 3.5 }
  evidence: "data/eval_runs/2026-05-12_card-id.json"
```

**铁律 9：旧版本不删，复制到 `.archive/`**

`pipeline-a-diagnose.prompt.md` → 改之前先 `cp .archive/pipeline-a-diagnose.v1.prompt.md`。理由：v1 vs v2 对比离不开 v1 还能跑。

**铁律 10：一次只改一边**

A v1 vs A v2 比较时，B 必须保持 v1 不变。同时改 A 和 B = 你不知道是谁带来的提升。

---

## 7. 反例：用户 a.v0 草稿如何违反每条铁律

用 [`.archive/a.v0-user-draft.md`](.archive/a.v0-user-draft.md) 做反例对照（教学用）：

| 铁律 | a.v0 怎么违反的 | v1 怎么修 |
|---|---|---|
| 铁律 1（明列 input） | 用 @ 把 4 份大文件全喂 | input 拆到具体章节 |
| 铁律 2（forbidden） | 没明令禁止任何东西 | frontmatter 加 `forbidden_inputs` |
| 铁律 3（拆部分） | "阅读 vision.md 知道项目背景" 全篇喂 | 只读 §3 + §5 |
| 铁律 5（一种结构） | 一个 prompt 想生成卡片 | 拆成 A（草稿）+ B（三层）两份 |
| 铁律 6（不写文件） | "根据 README 数据流分别写入" | 写入交给 py |
| 铁律 7（不自评） | "给负责审批的 agent 评分" 但流程混在一起 | judge 独立成 `judge.prompt.md` |
| 铁律 8 / 9（版本对比） | 没有 frontmatter / 没有 last_iter | 全员强制 frontmatter |

a.v0 不是写错了，是**还没引入 L5 工程纪律**。所有违反点都能映射到本文档某条铁律。这就是 L4 → L5 跃迁的具体内容。

---

## 8. 调用约定（你怎么在 Cursor 里跑这些 prompt）

每个 `*.prompt.md` 都设计为可被 Cursor chat 用 `@` 引用、再加输入参数。**标准调用模板**：

```
@<agent>.prompt.md

# Inputs
<input_name_1>: <值 or @file>
<input_name_2>: ...

按 prompt 跑，输出 JSON。
```

**重要纪律**：

- **每次跑都开新 chat**——避免 P3 状态膨胀（plan §1.5）
- 模型档位**按 frontmatter `model_tier` 切换**，不要靠记忆
- 输出 JSON 第一时间存到 `data/run_<date>_<agent_id>.json`
- 跑完关 chat，**不要继续聊**——把状态写回文件，不留在 chat 历史

---

## 9. 这份 conventions 自身的演进

- 每次新加 / 修改一条铁律，**更新本文件 + 在末尾加 changelog**
- 任何 prompt 违反本文件 → 在 PR / commit 注脚里说明"为何 deviating"
- 本文件不应该超过 250 行——超了说明你在过度规则化，砍

## Changelog

- 2026-05-11 v1：基于用户 a.v0 反例 + plan §1.5 / §3 提炼出 10 条铁律 + 7 节 prompt 正文结构。
