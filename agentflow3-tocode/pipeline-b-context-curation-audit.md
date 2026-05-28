# Pipeline B Context Curation 审阅表

> **用途**：人工审阅「发给 API 的上下文」是否过长、是否重叠、frontmatter 与正文是否一致。  
> **可视化审阅（含真实章节全文 + 勾选瘦身）**：[`pipeline-b-context-curator/`](../pipeline-b-context-curator/) — 运行 `./start.sh` 打开。  
> **用户意见与实施计划（目标 + 文件引用）**：[`pipeline-b-context-curation-plan.md`](./pipeline-b-context-curation-plan.md)  
> **权威 prompt**：[`agent第二轮/pipeline-b-style.prompt.md`](../agent第二轮/pipeline-b-style.prompt.md) **v2.1**（`agents_runtime.loader.load_prompt` 默认只读此目录，**不**读 `agents/pipeline-b-style.prompt.md` v1）。  
> **装配实现**：[`agents_runtime/context_builder.py`](../agents_runtime/context_builder.py) 的 `build_context` + `extract_doc_sections`。  
> **度量环境**：仓库根、最小 `route=new` A 草稿；字符数为 UTF-8 长度近似 token（中文约 ×1.5–2）。

---

## 1. 一次 API 调用里到底有什么

| 层 | 来源 | 约字符 | 约行 | 说明 |
|----|------|--------|------|------|
| **system** | prompt **正文**（`---` 之后） | **~24,000** | **~577** | 含 §1–§7 全套指令 + **§5 反例** + **§6 三个 Few-shot**（占 system 约 **31%**） |
| **user** | frontmatter `inputs` 装配 | **~15,200**（new） | **~402** | 见下表；`route=update` + 整张 IC 卡再 **+~1,600** |
| **合计** | | **~39,000**（new） | | 不含 Cursor 人工额外 `@` 的全文件 / v3 fewshot |

### system 正文分段（便于砍）

| Prompt 章节 | 约字符 | 与 user 文档重叠？ |
|-------------|--------|-------------------|
| §1 角色 | 1,100 | 否 |
| §2 任务（含 new/update/meta 三分支） | 3,700 | 否 |
| §3 输入契约 | 1,400 | 部分（写的「应读章节」与 runtime 切片不一致，见 §4） |
| §4 输出契约（三形态 JSON 样板） | 3,500 | 否 |
| **§5 反例（7+ 条完整 JSON/表格）** | **3,600** | **是** ↔ `schema_lint` 的 §6 反例 |
| **§6 Few-shot（Example 1–3 全文）** | **7,400** | **是** ↔ 标注册高分句 + schema §5 example 精神重复 |
| §7 自检 checklist | 2,500 | 部分 ↔ schema §4.5 字段一致性 |
| Notes（人类调用模板） | 900 | 不进 API（若在 system 末尾仍算进 body） |

---

## 2. frontmatter 声明的输入（契约层）

按 `inputs[]` **顺序**拼进 user message（每个块以 `# {name}` 开头）。

| # | `name` | `type` | 源文件 | frontmatter `sections` | 条件 |
|---|--------|--------|--------|------------------------|------|
| 1 | `pipeline_a_draft` | `json` | （上游 A 产出） | 整对象 | 始终 |
| 2 | `existing_card_json` | `json` | `data/chains.json` 单卡 | 整对象 | **始终传入**；`route≠update` 时为 `{}` |
| 3 | `style_brief` | `doc_section_set` | `context/crystallization-style-agent-brief.md` | §1 / §4 / §5 / §8 | 始终 |
| 4 | `annot_register` | `doc_section_set` | `回答版本explore/良质回答标注册.md` | §〇 / §八 / `B/C/F/H 系列高分句` | 始终 |
| 5 | `schema_lint` | `doc_section_set` | `context/crystallization-schema-v0.md` | §2.5 / §2.6 / §2.7 / **§4 内容 lint** / §6 反例 | 始终 |

**未在 frontmatter 声明、但正文/人类模板仍要求的**：

| 内容 | 契约位置 | `agents_runtime.run_b` 现状 |
|------|----------|------------------------------|
| v3 同 axis 1–2 张卡 | §3 表 + Notes `# v3 fewshot` | `fewshot` 参数 **预留未接**（`run_b` 内 `_ = fewshot`） |
| `agents/conventions.md` | 无 | 不读 |

---

## 3. 每个文件的「应读章节」↔ 磁盘标题对照

### 3.1 `context/crystallization-style-agent-brief.md`

| 标签 | 实际切出的 Markdown 标题 | 行号约 | user 约字符 | 主要内容 |
|------|-------------------------|--------|-------------|----------|
| **§1 沉淀摘要** | `## 1. 沉淀摘要（高密度）` | L9–L20 | ~670 | 口味总述、DS/Gemini 取舍、第一性原理≠术语阅兵 |
| **§4 执行清单** | `## 4. Agent 执行清单（写回答 / 写 Crystallization 时）` | L69–L78 | ~360 | 7 条写作步骤（拆假设、机制先于道德、隐喻/段落/收束纪律） |
| **§5 禁忌替代** | `## 5. 禁忌 ↔ 替代（一行对照）` | L81–L89 | ~230 | 4 行表格：CS 轰炸、暖心絮语、结构化总结、术语阅兵 |
| **§8 实证归纳** | `## 8. 实证归纳：写 Crystallization 时必须叠用的规则` + `### 8.1`–`8.6` | L116–L151 | ~1,200 | 双层过滤器、公式/短锚分工、长度折旧、CS 边界、刺痛着陆、待补标提醒 |

**刻意不读（prompt §3 表 + 简报自身 §7）**：

| 章节 | 标题 | 为何不读 |
|------|------|----------|
| §2 | `## 2. 用户原文反馈归档` | A 已吸收；重复占 attention |
| §3 | `## 3. 迭代脉络` | 元信息 |
| §6 | `## 6. Pattern tags` | routing 属 A；含双主轴表（与 schema §7 重复） |
| §7 | `## 7. 扩展阅读` | 索引表，非执行规则 |

---

### 3.2 `回答版本explore/良质回答标注册.md`

| 标签 | 实际切出范围 | user 约字符 | 主要内容 |
|------|-------------|-------------|----------|
| **§〇 标注规则** | `## 〇、用户偏好修订` **整节**（含子节） | ~1,440 | 含 **`### 〇-b、微妙平衡`**（DS×客观×不要絮叨）；frontmatter 只写「§〇」但 **runtime 会带上 〇-b** |
| **§八 成果汇总** | `## 八、标注成果汇总与迭代结论` + `8.1`–`8.4` | ~1,780 | 认同度分层、验证小结、**「与简报 §8 一致」的新结论**、H/G01 待办 |
| **B/C/F/H 系列高分句** | **`## 三、候选良质回答条目`** 起 → **`## 四`** 前（全文） | **~6,150** | DS-GUILT / DS-INTERN / GM-SYNTH / GM-COOP **全部候选条目**（含未打高分/低分句），**不是**仅 B10/C12 等 ID |

**刻意不读**：

| 章节 | 说明 |
|------|------|
| §一–§二 | 推断共性 + 标注列说明 |
| §四–§七 | 模板、下一步、第二/三波候选（与 §三 大量重复或偏低分） |

**契约漂移（重要）**：

- 正文 §3 表写：「§八 + **B10 / B11 / B13 / C11 / C12 / F05 / F07 / H09** 等高分句」  
- frontmatter 写：`B/C/F/H 系列高分句` → `context_builder` 映射为 **整段 §三**（见 [`phase1产出/04-模块实现索引.md`](phase1产出/04-模块实现索引.md) §2 `B/C`→三至四）。  
- **结果**：user 里最大单块是「§三全表」，占 user 文档摘录 **~40%**，且与 §八「认同度分层」、简报 §8 **三重列举** 同一批 ID。

---

### 3.3 `context/crystallization-schema-v0.md`

| 标签 | 实际切出范围 | user 约字符 | 主要内容 |
|------|-------------|-------------|----------|
| **§2.5 mechanism** | `### 2.5 crystallization.mechanism` | ~200 | 30–200 字、命名先于因果、生活隐喻 |
| **§2.6 anchor** | `### 2.6 crystallization.anchor` | ~170 | ≤20 字、可默念、二元结构 |
| **§2.7 micro_steps** | `### 2.7 crystallization.micro_steps` | ~170 | 1–3 步、动词、≤60 字 |
| **§4 内容 lint** | **`## 4. content lint` 整节** `4.1`–`4.5` | **~1,510** | 见下「漂移」 |
| **§6 反例** | `## 6. 反例` + `6.1`–`6.4` | ~790 | 四类打回样例（表格+短文） |

**§3 正文表写「只读 §4.2 / §4.4」 vs runtime 读整节 §4**：

| 小节 | 是否在 user | 与简报 §8 重叠 |
|------|-------------|----------------|
| 4.1 双层过滤器 | ✅ | ↔ 简报 **§8.1**（几乎同义） |
| 4.2 拒杞词清单 | ✅ | ↔ 简报 §5 表格 + §8.4 |
| 4.3 长度折旧 | ✅ | ↔ 简报 **§8.3** |
| 4.4 刺痛与着陆 | ✅ | ↔ 简报 **§8.5** |
| 4.5 字段间一致性 | ✅ | ↔ prompt §7 checklist；**B 写卡时 A 已定 axis** |

**刻意不读**：

| 章节 | 说明 |
|------|------|
| §1 / §2.1–§2.4 / §2.8–§2.11 | 结构字段；A 已填 |
| §3 JSON Schema | py `validate_chains_json` 用 |
| §5 Example IC-004 | 完整卡 JSON；与 prompt §6 Example 1 **同卡** |
| §7 双主轴 routing | 属 A |
| §8–§9 | 未来钩子 / 文件契约 |

---

### 3.4 `pipeline_a_draft`（JSON，非文件）

| 字段 | B 用途 | 备注 |
|------|--------|------|
| `route` | 决定 full_card / update_entry / meta_card | `run_b` 缺省时补 `"new"` |
| `title` / `patterns` / `axis` / `chain` / `source_refs` | new/meta：passthrough；update：不动原卡 | |
| `mechanism_sketch` | new/meta：转译 mechanism | |
| `update_directives` + `target_ic_id` | update 分支 | |
| `meta_evidence` | meta 分支 | |
| `raw_answer_seeds` | new：anchor 肌理 + `not_for_anchor` 护栏 | v2.2+；体积随 A 输出变化 |
| `diagnostic_notes` | 正文未强调读 | 可忽略，但仍在 JSON 里 |

---

### 3.5 `existing_card_json`（`route=update`）

| 来源 | 章节 | 说明 |
|------|------|------|
| `data/chains.json` → `chains[]` 中单条 | **整卡对象** | 含 `crystallization` / `chain` / `updates[]` 等；IC-012 级卡约 **+1.6k** user 字符 |

**浪费点**：`route=new` 时仍发送 `# existing_card_json\n{}\n`（frontmatter `required: if route==update` 未在 builder 层省略块）。

---

## 4. 重叠矩阵（审阅用）

| 主题 | 出现位置 | 建议审阅问题 |
|------|----------|--------------|
| **双层过滤器（机制×载体）** | 简报 §8.1；schema §4.1；prompt §5 部分反例 | 三处留 **一处权威**（建议简报 §8 **或** schema §4，不要两者整节） |
| **拒杞词 / CS / 糖浆** | 简报 §5 表 + §8.4；schema §4.2；prompt §5 反例 2 | 表格式重复；prompt 内 JSON 反例可缩为「见 schema §6.2」 |
| **刺痛×着陆垫** | 简报 §8.5；schema §4.4；prompt §5 反例 7；标注册 H11/H09 散落在 §三 | 规则 2 份 + 样例 3 份 |
| **公式不进正面** | 简报 §8.2；schema §4.2+§6.4；prompt §5 反例 5 | |
| **mechanism/anchor/steps 字段写法** | schema §2.5–2.7；简报 §4 清单；prompt §4 JSON 样板 | §2.x 与 §4 部分重复（schema 内部） |
| **反例全文** | schema §6.1–6.4；prompt **§5 七个反例**（含完整 JSON） | **最大 system 冗余**；与 user 里 schema §6 **双份** |
| **高分句 / 锚句家族** | 标注册 §三（全表）；§八 分层；简报 §8；prompt §6 Example 锚句 | §三全表 vs「仅 ≥4 分 ID」契约不一致 |
| **完整样例卡 IC-004** | schema §5；prompt §6 Example 1 | 同场景出现 **2 次**（system 更长） |
| **IC-012 update 样例** | prompt §6 Example 2 | 仅 system；update 跑通时仍有价值 |
| **双主轴 routing** | 简报 §6（未喂 B）；schema §7（未喂 B） | 已正确排除；**勿**为 B 加回 |

---

## 5. `forbidden_inputs`（不应出现在 user/system 的读盘路径）

| 模式 | 意图 |
|------|------|
| `外部source/*.md` | 原始对话；raw answer 已由 A 消化为 `raw_answer_seeds` |
| `context/inquiry-compound-vision.md` | Vision 层；A 已做 |
| `context/raw-questions-synthesis.md` | 合成画像；A 已用 |
| `inquiry-chain-demo-v3-good-answer.md` 全文 | 仅 1–2 张 fewshot；**code 路径尚未自动切片** |
| `round2/route_helper.py` / `.spec.md` | Plumbing；A 已跑 |
| `pipeline-a-diagnose.prompt.md` | 防读 A 指令污染（仅 chat 人工 @ 时会破戒） |

---

## 6. Chat 人工调用 vs `agents_runtime.run_b`

| 项 | Cursor 人工（Notes 模板） | `run_b` 自动 |
|----|---------------------------|--------------|
| prompt 文件 | 常 `@agent第二轮/...` 或误 `@agents/...` v1 | **固定** `agent第二轮/pipeline-b-style.prompt.md` |
| style_brief / 标注册 / schema | 常 **整文件 @**（远超 § 切片） | **仅** frontmatter 章节 |
| v3 fewshot | 人工贴 1–2 卡 | **未实现** |
| system 体积 | 若只 @ prompt：同 ~24k | 同左 |
| 总上下文 | 人工 @ 三文件时可达 **100k+** | 实测 **~39k**（new） |

---

## 7. 瘦身建议（供人工勾选，不改代码）

优先级按 **估节省 / 风险** 排序：

| 优先级 | 动作 | 估节省 | 风险 |
|--------|------|--------|------|
| P0 | **删或外链 prompt §6 Few-shot**：保留 1 个最短 update 样例即可 | **~7k system** | 新卡风格略漂；可用 runtime fewshot 补 |
| P0 | **删 prompt §5 反例**：改为「遵守 user 中 schema §6 + 简报 §8」 | **~3.6k system** | 低（user 已有 §6） |
| P1 | **标注册 `B/C/F/H` 改为 ID 白名单切片**（B10,B11,B13,C11,C12,F05,F07,H09,H11…）而非整段 §三 | **~4–5k user** | 需改 `context_builder` 或 frontmatter 新 type |
| P1 | **schema `§4 内容 lint` 改为仅 `§4.2`+`§4.4`**（与 §3 表一致） | **~0.8k user** | 失去 4.5 字段一致性表（可挪到 judge） |
| P1 | **简报只保留 §8，删 §1+§4+§5 或合并进 §8 一页** | **~1.2k user** | §1 高密度总述仍有价值 |
| P2 | **`route=new` 时不发 `existing_card_json` 块** | ~50 user | 需改 `build_context` |
| P2 | **简报 §8 与 schema §4 二选一** | **~1.5k user** | 需指定单一事实来源 |
| P3 | 接 Phase 5：`v3_fewshot` 2 卡自动切片，替代 prompt §6 Example 1 | system 再减 | 依赖 retrieval |

---

## 8. 审阅检查清单（打印勾选）

- [ ] **契约一致**：frontmatter `sections` ↔ §3 表 ↔ `context_builder` 行为（尤其 §三全表、§4 整节、§〇含 〇-b）
- [ ] **单一事实来源**：双层过滤器 / 刺痛着陆 / 拒杞词 — 是否指定「只信简报 §8」或「只信 schema §4」
- [ ] **高分句策略**：§三全表 vs 白名单 ID vs 仅 §八 分层表
- [ ] **system 反例**：prompt §5 是否整段删除
- [ ] **system fewshot**：prompt §6 留几条 / 是否改 runtime `fewshot` 输入
- [ ] **update 路径**：existing 卡是否需裁掉 `updates[]` 历史只留主 `crystallization`
- [ ] **agents/ 副本**：`agents/pipeline-b-style.prompt.md` v1 是否标注废弃，避免人工 @ 错文件

---

## 9. 复现度量命令

```bash
cd /path/to/growth
venv/bin/python3 -c "
from agents_runtime.loader import load_prompt
from agents_runtime.context_builder import build_context
prompt = load_prompt('pipeline-b-style')
a = {'route':'new','title':'t','patterns':['P-EVAL'],'axis':'attention',
     'chain':{'trigger':'t','questions':['q1','q2']},
     'mechanism_sketch':'x'*40,'source_refs':['B10']}
user = build_context(prompt, {'pipeline_a_draft':a,'existing_card_json':{}})
print('system', len(prompt.body), 'user', len(user), 'total', len(prompt.body)+len(user))
"
```

---

*生成：2026-05-20；基于 `agent第二轮/pipeline-b-style.prompt.md` v2.1 + `agents_runtime` 当前 `context_builder` 行为。*
