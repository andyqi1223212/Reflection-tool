# Pipeline B Context Curation 计划（用户意见沉淀）

> **状态**：✅ **已实施（2026-05-20）** — v2.2 已落地；24.6k 字符 / Judge 4.92 PASS  
> **权威 prompt**：[`agent第二轮/pipeline-b-style.prompt.md`](../agent第二轮/pipeline-b-style.prompt.md) v2.1  
> **装配实现**：[`agents_runtime/context_builder.py`](../agents_runtime/context_builder.py) · [`agents_runtime/agents.py`](../agents_runtime/agents.py) `run_b`  
> **可视化审阅**：[`pipeline-b-context-curator/`](../pipeline-b-context-curator/)（勾选 + 真实章节原文）  
> **背景审计**：[`pipeline-b-context-curation-audit.md`](./pipeline-b-context-curation-audit.md)

---

## 1. 目标（为什么要改）

| 目标 | 说明 |
|------|------|
| **减 token / 减注意力稀释** | 当前一次 `run_b` 约 **~39k 字符**（system ~24k + user ~15k）；同一套「口味 / 反例 / 锚句」在 4–5 份文档里重复出现。 |
| **单一事实来源** | B 的风格与 lint 规则应能回答：「这条约束以哪份文件、哪一节为准？」避免 prompt 正文、简报、schema、标注册各说一遍。 |
| **保留 B 独有职责** | B 只做 **诊断草稿 → 合规 crystallization 字段**（含 v2.1 `full_card` / `update_entry` / `meta_card`）；不重诊断、不评分、不入库。 |
| **可人工审阅、可回滚** | 用审阅器勾选验证后再改 frontmatter / 导出脚本；chat 路径与 code 路径对齐。 |

**非目标（本计划不做）**

- 不改 Pipeline A / Judge 的 context（另案）。
- 不删仓库里的标注册 / schema / 简报全文（仅 **B 默认不再整段喂入**）。
- 不在本阶段做 Phase 5 动态 retrieval（fewshot 按 axis 自动摘卡可后续接）。

---

## 2. 用户 Raw 意见（原文意图，未抛光）

1. **反例簇**：`prompt` 正文 **§5 反例**、简报 **§5 禁忌替代**、简报 **§8 实证归纳**、schema **§4 内容 lint**、schema **§6 反例**——体感上「差不多都是反例」；**核心是 prompt §5 那份**（最细、含 v2 路由坑）。
2. **Few-shot**：**一定得删**（`prompt` §6 三篇 example 太长，和 v3 / 标注册重复）。
3. **标注册三块效果一般**：`§〇 标注规则`、`§八 成果汇总`、`B/C/F/H 系列高分句`（runtime 实为 **§三 全表**）——需要 **改革成一个精简文档**，不再三块齐喂。
4. **schema §4 / §6**：和 prompt §5 **高度重叠**；保留 **§5 反例里的内容** 作为反例权威即可。

---

## 3. 客观校正（实施前必读，避免改错）

以下是对 raw 意见的核对结论（详见 [audit §4 重叠矩阵](./pipeline-b-context-curation-audit.md)）：

| 用户说法 | 校正 |
|----------|------|
| brief **§5** = 反例 | **不完全是**。§5 是 4 行「避免→替代」表（~230 字），不是 ❌/✅ 反例集；可与拒杞词表 **合并一处**，不必与 prompt §5 双份保留。 |
| brief **§8** = 反例 | **不对**。§8 是 **正向写作规则**（双层过滤器、公式/短锚、折旧、CS 边界、刺痛配对）；与 schema **§4.1–4.4** 同质，不是 prompt §5 的重复。 |
| schema **§6** ≈ prompt **§5** | **对**（§6 是 §5 子集）；且 prompt §5 多 **v2.1 反例 8–11**（update / meta / raw_answer_seeds）。 |
| schema **§4 整节** ≈ prompt **§5** | **半对**。§4.1–4.4 + §6 与 §5/§8 重叠；**§2.5–2.7 必须保留**（字段长度/结构，与 taste 正交）。 |
| 标注册 **§〇** 无用 | **半对**。与 brief **§1** 重复度高，但含 **〇-b 不要婆婆妈妈** 表；应 **压缩进 lexicon**，非整段删除语义。 |
| 标注册 **§八** 无用 | **对 B 而言基本冗余**（已 mirror 到 brief §8）。 |
| 标注册 **§三** 高分句 | **ROI 低**（~6k 字全表）；B 只需 **锚句家族 + 少量黄金 ID**，不需候选电话簿。 |

---

## 4. Context Curation 决议（喂什么 / 不喂什么）

### 4.1 System（`prompt` 正文 → `llm` system message）

| 章节 | 文件 | 决议 | 理由 |
|------|------|------|------|
| §1 角色 | `agent第二轮/pipeline-b-style.prompt.md` | **保留** | 三分支心智（new / update / meta） |
| §2 任务 | 同上 | **保留** | 操作步骤 |
| §3 输入契约 | 同上 | **保留**（实施时 **改文案** 与 frontmatter 对齐） | 现与 runtime 切片不一致 |
| §4 输出契约 | 同上 | **保留** | JSON 三形态样板 |
| **§5 反例** | 同上 | **保留（反例唯一权威）** | 含 v2.1；可 **二期压缩** 条数，不单靠 schema §6 |
| **§6 Few-shot** | 同上 | **删除** | ~7.4k 字；默认 run_b 不送 |
| §7 自检 checklist | 同上 | **保留** | 输出前门禁；与 schema §4.5 部分重叠可接受 |
| Notes 人类模板 | 同上 | **不进入 API** | 仅 Cursor 手工调用说明 |

**Few-shot 补充决议**：默认 **0 条**；若 dogfood 发现「正向转译」变差，再考虑 **1 条极短正向样**（≤400 字）或 Phase 5 按 axis 插 1 张 v3 卡——**不恢复 §6 全文**。

---

### 4.2 User（`build_context` 按 frontmatter 顺序）

| Input 名 | 文件 · 章节 | 决议 | 理由 |
|----------|-------------|------|------|
| `pipeline_a_draft` | 上游 A JSON | **保留（整段）** | 唯一结构化输入 |
| `existing_card_json` | `data/chains.json` 单卡 | **保留**；`route=new` 时 **可不发空 `{}`**（实现优化） | update 必备 |
| `style_brief` | [`context/crystallization-style-agent-brief.md`](../context/crystallization-style-agent-brief.md) | **§1 沉淀摘要** + **§4 执行清单** only | §4 是「怎么写」步骤；§5/§8 迁入 lexicon |
| ~~`style_brief` §5~~ | 同上 | **不喂** | 并入 lexicon 拒杞表 |
| ~~`style_brief` §8~~ | 同上 | **不喂**（由 lexicon 承接） | 与 schema §4 三角重复 |
| **`style_lexicon`**（新） | [`context/pipeline-b-style-lexicon-v1.md`](../context/pipeline-b-style-lexicon-v1.md)（待建） | **整份喂入（目标 <2k 字）** | 见 §5 |
| ~~`annot_register` §〇~~ | [`回答版本explore/良质回答标注册.md`](../回答版本explore/良质回答标注册.md) | **不喂** | 压缩进 lexicon |
| ~~`annot_register` §八~~ | 同上 | **不喂** | 与 brief §8 重复 |
| ~~`annot_register` B/C/F/H~~ | 同上（runtime = **§三 全表**） | **不喂** | 改为 lexicon 锚句家族 |
| `schema_lint` | [`context/crystallization-schema-v0.md`](../context/crystallization-schema-v0.md) | **§2.5 / §2.6 / §2.7 only** | 字段硬约束 |
| ~~`schema_lint` §4~~ | 同上 | **不喂** | 规则由 lexicon + prompt §5 覆盖 |
| ~~`schema_lint` §6~~ | 同上 | **不喂** | 由 prompt §5 覆盖 |
| ~~v3 fewshot~~ | [`inquiry-chain-demo-v3-good-answer.md`](../inquiry-chain-demo-v3-good-answer.md) | **默认不喂** | `run_b` 尚未接；人工 chat 可选 |

**标注册全文**：仍作 **人类标注 / 迭代源**；B API **不默认引用**。

---

### 4.3 明确禁止（不变）

与 `pipeline-b-style.prompt.md` `forbidden_inputs` 一致，B **不读**：

- `外部source/*.md`
- `context/inquiry-compound-vision.md`
- `context/raw-questions-synthesis.md`
- `inquiry-chain-demo-v3-good-answer.md` 全文
- `round2/route_helper.py` / `.spec.md`
- `pipeline-a-diagnose.prompt.md`

---

## 5. 新建精简文档（lexicon）规格

**路径（拟定）**：`context/pipeline-b-style-lexicon-v1.md`  
**方案**：**乙**——正向规则 + 锚句家族 + 拒杞 **只保留这一份**（不另喂 brief §8 + schema §4）。

建议结构（实施时按此起草）：

| 节 | 内容来源 | 目标 |
|----|----------|------|
| 0. 口诀 | 标注册 §〇-b、简报 §1 各 1 段 | ≤15 行 |
| 1. 拒杞 ↔ 替代 | 简报 §5 + schema §4.2 表 **合并一张** | 1 表 |
| 2. 写作规则 | 简报 §8.1–8.5 **压缩**（无重复叙事） | 5 条 bullet |
| 3. 锚句家族 | 标注册 §八「四分档」+ B10/C12/F05/H09 等 | 8–12 家族 ×（名称 + 1 黄金句 + ID） |
| 4. 刺痛 × 着陆 | §8.5 + prompt §5 反例 7 各 1 行 | 规则 + 1 对 micro_step |

**维护契约**：标注册 / 简报更新后，**只同步改 lexicon**；B frontmatter 只指向 lexicon + brief §1/§4 + schema §2.5–2.7。

---

## 6. 实施阶段（与代码 touch 点）

### 阶段 1 — 只改 curation（优先）

| 动作 | 文件 |
|------|------|
| 新建 lexicon | `context/pipeline-b-style-lexicon-v1.md` |
| 改 B `inputs` frontmatter | `agent第二轮/pipeline-b-style.prompt.md` |
| §3 输入契约表与 frontmatter 对齐 | 同上正文 |
| `build_context`：新 input `style_lexicon`；`route=new` 省略空 `existing_card_json` | `agents_runtime/context_builder.py` |
| 导出审阅块 + 预设 `user_slim_v1` | `tools/export_pipeline_b_context_chunks.py` · `pipeline-b-context-curator/` |
| 单测更新 | `agents_runtime/tests/test_context_builder.py` |

**阶段 1 不删**：prompt §5、§7；brief §1/§4；schema §2.5–2.7。

### 阶段 2 — prompt 瘦身（dogfood 后）

| 动作 | 文件 |
|------|------|
| 删除 prompt §6 Few-shot 正文 | `agent第二轮/pipeline-b-style.prompt.md` |
| 可选：压缩 prompt §5（保留 v2 反例 8–11） | 同上 |
| Judge 侧补 schema §4.5 / 部分 §6（B 不背） | `agent第二轮/judge.prompt.md` |

### 阶段 3 — 标注册治理

- `良质回答标注册.md` 保持全量供人标注。
- 高分 ID 变更时 **只 export 到 lexicon**（脚本可后做）。

---

## 7. 预期效果（粗算）

| 相对当前 runtime 默认 | 约字符 |
|------------------------|--------|
| 删 prompt §6 | −7.4k |
| 删 user：brief §5/§8、annot 三块、schema §4/§6 | −10k 量级 |
| 增 lexicon | +1.5k |
| **净节省** | **约 −15k～−17k（~40%）** |

审阅器勾选预设名（实施后）：`user_slim_v1` ≈ 本计划阶段 1。

---

## 8. 待拍板 → 已决（2026-05-20）

1. **lexicon 替代 brief §8 + schema §4 + 标注册 §八**：✅ 已决方案 A SSOT；落地于 [`context/pipeline-b-style-lexicon-v1.md`](../context/pipeline-b-style-lexicon-v1.md) v1（2.78k 字）。
2. **prompt §5 反例条数**：阶段 1 全量保留；dogfood pass 后**已同步删除 §6 Few-shot 全段**（节省 ~10k system 字符）。
3. **dogfood 实测（2026-05-20）**：v2.2 system+user **24.6k 字符**（vs v2.1 ~39k，净降 ~37%）；Judge 评分 **4.92/5 pass**（vs v2.1 baseline 4.67）。详见 [`agents/runs/dogfood-2026-05-20/`](../agents/runs/dogfood-2026-05-20/)。

---

## 9. 文件引用速查（实施后 B 默认读取）

```
agent第二轮/pipeline-b-style.prompt.md     # system: §1–§5、§7（无 §6）
context/crystallization-style-agent-brief.md   # user: §1, §4
context/pipeline-b-style-lexicon-v1.md     # user: 全文（新建）
context/crystallization-schema-v0.md       # user: §2.5, §2.6, §2.7
<pipeline_a_draft.json>                    # user: A 产出
<existing_card.json>                       # user: route=update 时 chains 单卡
```

**不再默认读取**

```
context/crystallization-style-agent-brief.md   # §5, §8
回答版本explore/良质回答标注册.md              # §〇, §八, §三
context/crystallization-schema-v0.md       # §4, §6
inquiry-chain-demo-v3-good-answer.md       # fewshot 全文
```

---

## 10. 相关链接

| 文档 | 用途 |
|------|------|
| [pipeline-b-context-curation-audit.md](./pipeline-b-context-curation-audit.md) | 实测字符量、重叠矩阵、漂移说明 |
| [pipeline-b-context-curator/README.md](../pipeline-b-context-curator/README.md) | 本地勾选审阅 |
| [plan-chat-to-code-api.md](./plan-chat-to-code-api.md) | 总迁移 plan（Phase 1–5） |

---

*沉淀自：用户 2026-05-20 审阅意见 + context 审计对话；实施状态以 git / frontmatter 为准。*
