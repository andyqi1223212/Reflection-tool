# Lexicon v2 SSOT 收敛 — 合并草稿（待审）

> **目的**：把分散在 prompt §5 反例 / brief §1 §4 §5 §8 / schema §4 的 Pipeline B 风格规则收敛到 lexicon 一处。
>
> **本文档不直接落档**——你在每节末尾用 `> 批注：...` 留意见；我看完后再真改文档与 agents_runtime。
>
> **决策依据**：上一轮对话「思考 A」结论 + 第一性原理（一规则一处）。
>
> **预期收益**：
>
> - 改一条写作规则只改一处（当前 lexicon / brief / prompt §5 三处易 desync）
> - prompt system 体积再压（粗估 system+user 从 v2.2 24.6k → v2.3 ~20k）
> - brief 退役为人类档案（§2 用户原文反馈 / §3 迭代脉络 永久价值大于删除）

---

## 概览：5 处改动


| #   | 文件                                                                                                       | 改动                                                                | 大小        |
| --- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | --------- |
| 1   | **新建** [context/pipeline-b-style-lexicon-v2.md](../context/pipeline-b-style-lexicon-v2.md)               | 在 v1 基础上：§0 加形状 / §1 加 1 行 / §2 5 条 → 8 条 / **§5 新增 7 条反例**       | +~80 行    |
| 2   | **改** [agent第二轮/pipeline-b-style.prompt.md](../agent第二轮/pipeline-b-style.prompt.md) frontmatter          | inputs 删 `style_brief`；`style_lexicon.source` 改 v2；version → v2.3 | -1 行      |
| 3   | **改** 同上 §3 输入契约表 + §5 反例 11 条 → 5 条（只留结构级）                                                              | 内容级 7 条迁走 + 表格删 brief 行                                           | -~120 行   |
| 4   | **改** [context/crystallization-style-agent-brief.md](../context/crystallization-style-agent-brief.md) 顶部 | 加 deprecation banner（agent 不再读；保留人类档案）                            | +5 行      |
| 5   | **改** [.cursorrules](../.cursorrules) Context curation 表                                                 | Pipeline B 必读列删 `style_brief`、加 lexicon-v2                        | -1 行 +1 行 |
| -   | **agents_runtime 代码**                                                                                    | **零改动**（loader + context_builder 已通用，frontmatter 改完自动跟随）          |           |
| -   | **归档** v1 → `context/_archive/lexicon-v1-2026-05-22.md`（手动 mv）                                           |                                                                   |           |


---

## Part A：新建 lexicon v2 全文（待审）

> 路径：`context/pipeline-b-style-lexicon-v2.md`
>
> **变化标注**：v1 已有内容用普通字体；v2 新增 / 修改部分用 **粗体 + (NEW v2)** 标识。

```markdown
---
file: pipeline-b-style-lexicon-v2.md
purpose: Pipeline B 唯一默认读取的风格规则文件（SSOT 二次收敛）；写 crystallization 时只翻这一份
derived_from:
  - context/crystallization-style-agent-brief.md §1（沉淀摘要 / 口诀）
  - context/crystallization-style-agent-brief.md §4（执行清单 7 步）
  - context/crystallization-style-agent-brief.md §5（禁忌替代）
  - context/crystallization-style-agent-brief.md §8（实证归纳）
  - context/crystallization-schema-v0.md §4.2 / §4.3 / §4.4（内容 lint）
  - agent第二轮/pipeline-b-style.prompt.md §5 反例 1/2/3/4/5/7/10（内容级反例迁入）
  - 回答版本explore/良质回答标注册.md §〇-b / §八（四分档 + 验证档）
absorbs:
  - brief §1 沉淀摘要 → §0 口诀 + 引言
  - brief §4 执行清单 7 步 → §2 写作规则（与原 5 条合并去重 → 8 条）
  - brief §5 / §8 → 已迁入 §1 / §2 / §4（v1 已做）
  - prompt §5 内容级反例 1/2/3/4/5/7/10 → §5 反例（v2 新增）
maintenance: 标注册 / brief 高分句 / prompt 内容反例进来时**只改本文件**；不再多处双写
last_synced: 2026-05-22
---

# Pipeline B 风格规则（lexicon v2）

> **总目标**：**准机制 + 生活载体 + 短入口**——情绪信息完整、推理可执行，少废话省 token。

---

## 0. 口诀

口语承接，书面拆解；一句人情，一段因果；拒绝糖浆铺底，拒绝术语阅兵。

`subtle = 客观共情 + 一段一支点 + 冷热短打`——心疼体现在判断准，不在形容词数量。

`婆婆妈妈 = 情感卡路里高、认知卡路里低`：反复安慰、空洞夸奖、同义抚慰复读、用长度冒充深度——一律删。

**Crystallization 形状**（与 vision / schema 一致）：机制 1-2 句 + ≤20 字入口句 + ≤3 步小动作；trigger 时只看晶体即可着陆。 **(NEW v2)**

[来源: brief §〇-b + brief §1]

---

## 1. 拒杞 ↔ 替代（默认不进卡正面）

| 类别 | 例 | 处置 |
|------|----|------|
| **CS / 工程隐喻** | 算力、ETL、编译、CI/CD、root、API、过拟合、bug、interrupt handler | 改写为生活/身体/关系语；**仅当用户消息先用工程词** 才可顺势用 1 个收尾 |
| **显式公式** | `愧疚 = 责任感 × 情绪 ÷ 事实` | 不进 mechanism / anchor；可作开发者注释或 v1 扩展字段 |
| **鸡汤糖浆** | 反复"你已经很棒"、"加油"、"相信自己" | 删 |
| **抽象正确的废话** | "重要的是 mindset"、"找到自己" | 删；改成可观察行为 |
| **过密英文术语 / 黑话堆积** | "context wall"、"attention dilution"、"single source of truth" 连用 | 改写为同义中文 + 必要英文括注；一段最多 1 个英文专有名词 | **(NEW v2)** |

**实证**：A03/A04（公式）、C05/C06/C15（CS 壳）= 2 分；B10/B13/C11/C12（短锚 + 能动）= 4 分。
我感觉在这种文档里类似B10这种内容没用了

**meta 自约束** **(NEW v2)**：本 lexicon 自身也守这套规则——维护时若发现自己堆英文，先修自己再传播。

[来源: brief §5 + schema §4.2 + 标注册 §八.1 + sub1 用户偏好]

---

## 2. 写作规则（8 条，叠用） **(MODIFIED v2: 原 5 条 → 8 条；合并 brief §4 执行清单 7 步)**

### 内容纪律

1. **先拆假设** **(NEW v2)**：本段隐含前提是什么？删掉多余前提后剩几条变量？
2. **机制先于道德**：先命名模式（人设、好人牢笼、时间旅行、超前预警），再谈是否 proportionate。
3. **隐喻纪律**：默认生活 / 身体 / 关系；**一道菜一个隐喻**；不要 CS 词刷屏。
4. **段落纪律**：一段一支点（一条假设 / 一条边界 / 一条因果）；禁同义复读。
5. **锋利协作** **(NEW v2)**：可刺痛，但必须解释"你怎么把中性分析听成否定"——刺痛 + 解释 = 共情而非否定。
6. **双层过滤器（机制 × 载体）**：机制可对、载体可换——用户反感"脏数据"等具体词时**保机制、换载体**。

### 节奏纪律

7. **叙事折旧**：同一 pattern 第一次长叙事可有冲击；第二次开始读者会"太麻烦"（F08/F09）。索引层只放压缩句，故事下放 trigger / questions，不重复全长展开。
8. **收束 + 篇幅** **(NEW v2)**：mechanism 1-2 句 + ≤20 字入口句 + ≤3 步小动作；**宁短勿灌**——情绪完整靠"判断准"不是靠形容词多。

[来源: brief §4 1-7 + brief §8.1/§8.3/§8.4 + 原 v1 §2]

---

## 3. 锚句家族（已实证 4 分档 + 验证不错）

> **本节内容 v2 不变** —— 与 v1 完全一致

每条：`家族名 | 黄金句 | [ID]`。写 anchor / mechanism 时**取家族风格**，不直接抄字。

### attention 主轴（自我架构 / 注意力经济）

- **得失心偷算力** | "得失心不产生结果，只偷算力。" | [C12 · 4分]
- **创造而非发现** | "答案不是被发现的，是被创造的。" | [C11 · 4分]
- **存在短锚 / 在场** | "我在这里。我活着。我感受。" | [B13 · 4分]
- **Inner Game 顾问** | "Self 1 不杀死，让它从控制者变顾问。" | [B10 · 4分]
- **侦察兵→指挥官** | "侦察兵收到了，现在指挥官行动。" | [B11 · 3.5]
- **警报响火没烧** | "警报响了，但火没烧起来。" | [B14 · 3.5]

### judgment 主轴（判决外包 / 愧疚链）

- **三还** | "把注意力还给球，把评判权还给他，把平静留给自己。" | [F05]
- **三责任边界** | "我的责任是…我不需要为…负责。" | [F07]
- **生存战已打完** | "生存战已打完。" | [H06]
- **愧疚的时间旅行** | "你害怕的不是他，是借他脸审判你的自己。" | [F03]

**routing**：用户当下痛在 **「羞/愧/怕别人」**（judgment）还是 **「空/漂/偷算力/万一」**（attention）？axis 决定整张卡语调；不要全堆愧疚库。

[来源: 标注册 §八.1 四分档 + §六 验证档 + brief §6 双主轴]

---

## 4. 刺痛 × 着陆配对（硬约束）

> **本节内容 v2 不变** —— 与 v1 完全一致

mechanism 含负向命名（"你不是…，是…"）或高刺痛自省（"24h 风险雷达 / 智力优越感护城河"）时，**micro_steps 必须含 ≥1 步身体可做的动作**——不能全是抽象规劝。否则刺痛裸奔，用户接不住。

**反例 vs 修订**（H11 重创 → 配 H09 三件套）：

```
❌ mechanism: "你在用'智力优越感'当护城河防御别人 judge 你。"
   micro_steps: ["接纳真实的自己"]

✅ mechanism 保留刺痛；
   micro_steps:
     - "卡住时先做 3 次延长呼气，让身体先于脑子换轨"
     - "把当前在想的写一句到外部（纸/备忘录）"
     - "默念一次：警报响了，火没烧。"
```

[来源: brief §8.5 + schema §4.4 + 标注册 H09/H11]

---

## 5. 反例（内容级；自 v2 从 prompt §5 迁入 7 条） **(NEW SECTION v2)**

> **结构级反例**（route=update/meta 输出形态、A→B 边界、append-only 语义、raw_answer_seeds 护栏被忽略）仍留在 [prompt §5](../agent第二轮/pipeline-b-style.prompt.md)；
>
> **本节只收内容级反例**——「写出来的字面违反 §1-§4 规则」。

### 反例 5.1：mechanism 退化为分析口吻

❌ 错误：
```json
"mechanism": "这条链把学习问题和评价问题缠在了一起。真正卡住的不只是题，而是『我已经展示过我懂，所以我必须持续证明我懂』。一旦证明压力升起，工作记忆被评价恐惧占用，解题能力反而下降。"
```
为什么不好：研究报告口吻，不是机制描述。违反 §2 写作规则 2（命名先于因果）。

✅ 应该：
```json
"mechanism": "你不是只在做题，你还在维护『提前学过 → 必须答得好』的人设。证明压力一进来，工作记忆就被它占满，剩下的算力解题不够用。"
```
（命名 + 因果两层，"人设"是关系隐喻不是 CS 词）

### 反例 5.2：anchor 太长 / 含 CS 词

❌ 错误：`"anchor": "练习是暴露 bug，不是维护人设"`
为什么不好：含 "bug"（CS 词），违反 §1 拒杞词；且 12 字略长（虽 <20 但欠口语化）。
✅ 应该：`"anchor": "得失心，不进考场。"`（短、动名词、生活语）

### 反例 5.3：anchor 22 字含转折

❌ 错误：`"anchor": "我可以证明，但我不为审判而活。"`
为什么不好：22 字超 schema §2.6 上限；含转折难默念，违反 §3 锚句家族（短锚二元结构常胜）。
✅ 应该：`"anchor": "生存战已打完。"`

我其实很多时候觉得：anchor太短不好，比如身体收摊，在家能松这样的：卡不为极简牺牲 **内容完整性**，不必写成「电脑屏幕那么局促」。
### 反例 5.4：micro_steps 抽象规劝

❌ 错误：
```json
"micro_steps": ["保持平静，不要焦虑", "学会接受不完美", "通过冥想找到内心宁静"]
```
为什么不好：全是抽象规劝，无身体动作；含"通过/慢慢"模糊时间词。违反 schema §2.7 + §1（"抽象正确的废话"）+ §4（刺痛配着陆）。

✅ 应该：
```json
"micro_steps": [
  "卡住时先写下确定的条件，不开内心法庭",
  "把问题问成具体卡点，不问自己笨不笨",
  "下课只复盘解题流程，不复盘老师的表情"
]
```

### 反例 5.5：mechanism 写公式

❌ 错误：`"mechanism": "愧疚感 = 责任感 × 他人情绪 ÷ 事实清晰度"`
为什么不好：A03/A04 实证为 2 分；公式不进卡正面，违反 §1（显式公式行）。
✅ 应该：把公式拆成因果文字，例 IC-020 风格。

### 反例 5.6：刺痛裸奔（mechanism 重创 + micro_steps 抽象）

❌ 错误：`"mechanism": "你在用『智力优越感』当护城河防御别人 judge 你"` + `"micro_steps": ["接纳真实的自己"]`
为什么不好：高刺痛必须配着陆垫，违反 §4 刺痛 × 着陆配对。
✅ 应该：mechanism 保留刺痛，micro_steps 给身体动作 + 一句权限句（参 §4 修订示范）。

### 反例 5.7：meta_card anchor 退化为具体动作句

❌ 错误：route=meta，输出 `"anchor": "想刷新时先做 3 次呼气。"`
为什么不好：这条 anchor 只对单一 trigger 成立；元锚卡的 anchor 必须能在**任何一张** child trigger 下默念有效——违反 §3 attention 主轴态势感知家族纪律。
✅ 应该：`"anchor": "我在错的轨道上努力。"`（态势感知家族——任何 attention 轴 bubble 下都成立）

---

## changelog

- **2026-05-22 v2**：SSOT 二次收敛
  - **§0** 加「Crystallization 形状」一行（吸收 brief §1 essence）
  - **§1** 拒杞表新增「过密英文术语 / 黑话堆积」行（sub1 用户语言偏好）+ meta 自约束
  - **§2** 写作规则 5 条 → 8 条（合并 brief §4 执行清单 7 步去重；新增 #1 先拆假设 / #5 锋利协作 / #8 收束篇幅）
  - **§5** 新增内容级反例 7 条（从 prompt §5 迁入；prompt 只保留 routing/结构级 5 条）
  - **B 的 frontmatter** 删 `style_brief` input；brief 退役为人类档案（不再被 agent 读）
  - 实测预期：B system+user 从 24.6k → ~20k；改一条写作规则只改一处
- **2026-05-20 v1**：从 brief §8 / schema §4.2-§4.4 / 标注册 §八 抽提合并；B frontmatter 默认引此文件 + brief §1/§4 + schema §2.5-§2.7。同步删 prompt §6 Few-shot 全段。
  - **实测**：system+user 字符 39k → 24.6k（净降 ~37%；real ball-trash A draft）
  - **dogfood Judge 评分**：4.92/5（vs v2.1 baseline 4.67），verdict=pass
```

> **批注区 A**：你对新 lexicon 内容的批注写在这里 ↓
>
> - 
> - 
> - 

---

## Part B：prompt 改动（pipeline-b-style.prompt.md v2.3）

### B.1 frontmatter 改动（diff 形式）

```diff
 ---
 agent_id: pipeline-b-style
-version: v2.2
+version: v2.3
 model_tier: normal
 inputs:
   - { name: pipeline_a_draft, type: json, required: true, description: "..." }
   - { name: existing_card_json, type: json, required: "if route==update", description: "..." }
-  - { name: style_brief, type: doc_section_set, source: "context/crystallization-style-agent-brief.md", sections: ["§1 沉淀摘要", "§4 执行清单"], required: true, description: "高密度总述 + 执行清单。§5/§8 已迁入 lexicon，本输入不再喂" }
-  - { name: style_lexicon, type: doc_full, source: "context/pipeline-b-style-lexicon-v1.md", required: true, description: "B 默认读取的唯一风格规则文件——口诀 / 拒杞替代 / 写作规则 / 锚句家族 / 刺痛着陆配对 整合在此。从 brief §8 + schema §4.2/§4.4 + 标注册 §〇-b/§八 抽提合并；写卡时**只翻这一份**；将来风格规则迭代也只改本文件" }
-  - { name: schema_lint, type: doc_section_set, source: "context/crystallization-schema-v0.md", sections: ["§2.5 mechanism", "§2.6 anchor", "§2.7 micro_steps"], required: true, description: "字段硬约束（长度/结构）。§4 内容 lint / §6 反例 已迁入 lexicon + prompt §5（system 反例）" }
+  - { name: style_lexicon, type: doc_full, source: "context/pipeline-b-style-lexicon-v2.md", required: true, description: "B 唯一权威风格规则——v2 吸收 brief §1/§4 + prompt §5 内容反例；写卡时**只翻这一份**；风格规则迭代也只改本文件" }
+  - { name: schema_lint, type: doc_section_set, source: "context/crystallization-schema-v0.md", sections: ["§2.5 mechanism", "§2.6 anchor", "§2.7 micro_steps"], required: true, description: "字段硬约束（长度/结构）。内容 lint / 反例已迁入 lexicon" }
 forbidden_inputs:
   - "外部source/*.md（任何原始对话；attention 稀释风险——你只看 A 的草稿）"
   - "context/inquiry-compound-vision.md 全文（A 已经做完 vision 那一层的诊断；你只关注风格化）"
   - "context/raw-questions-synthesis.md（A 已用过；二次 dump 会污染你的 attention）"
+  - "context/crystallization-style-agent-brief.md（v2.3 起 B 默认禁读；§1/§4 essence 已迁入 lexicon v2；本文件保留为人类档案）"
   - "inquiry-chain-demo-v3-good-answer.md 全文（route=new/meta 只读 1-2 张同 axis fewshot；route=update 只读 existing_card_json 那张——别再翻 md 全文）"
   - "round2/route_helper.py / .spec.md（A 已经消化过 helper 输出；你不需要看）"
   - "回答版本explore/良质回答标注册.md（v2.2 起 B 不再默认读取；锚句家族 + 高分 ID 已迁入 style_lexicon。本文件仅作人类标注 / lexicon 同步源；agent 路径上是禁读）"
-last_iter: 2026-05-20  # v2.2: 风格规则收敛到 context/pipeline-b-style-lexicon-v1.md（SSOT）...
+last_iter: 2026-05-22  # v2.3: SSOT 二次收敛——brief 退役（agent 不读）；prompt §5 内容反例 7 条迁入 lexicon v2 §5；prompt §5 只保留结构反例 5 条；inputs 从 4 段 → 3 段。预期 system+user ~24.6k → ~20k
 ---
```

### B.2 §3 输入契约表改动

```diff
 | Input | 你应该读的部分 | 你不许读的部分 |
 |---|---|---|
 | `pipeline_a_draft` | **整段 JSON 当结构化数据用**；... | 不要把 `chain.questions` 当原始素材二次抽取——A 抽好了 |
 | `existing_card_json`（route=update） | 整张卡的当前值；... | 不要读 chains.json 全文 |
-| `style_brief` | §1 沉淀摘要（高密度总述）/ §4 执行清单（写作步骤） | §2 用户原文反馈（A 已吸收）、§3 迭代脉络、§5 禁忌替代（已迁 lexicon §1）、§6 双主轴（A 的活）、§7 扩展阅读、§8 实证归纳（已迁 lexicon §2/§4） |
-| `style_lexicon` | **整文喂入** —— B 唯一权威风格规则。§0 口诀 / §1 拒杞替代 / §2 写作规则 5 条 / §3 锚句家族 / §4 刺痛×着陆配对 | 无（v1 ≈ 2.8k 字，全部相关）|
+| `style_lexicon` | **整文喂入** —— B 唯一权威风格规则（v2）。§0 口诀 / §1 拒杞替代 / §2 写作规则 8 条 / §3 锚句家族 / §4 刺痛×着陆配对 / §5 内容级反例 7 条 | 无（v2 ≈ 3.5k 字，全部相关）|
 | `schema_lint` | §2.5 mechanism / §2.6 anchor / §2.7 micro_steps 写法纪律 | §3 JSON Schema、§4 内容 lint / §6 反例（已迁 lexicon）、§5 example、§7 双主轴 routing（A 的活）|

 **明令禁止**（铁律 2 / forbidden_inputs）：
 - ❌ 不读 `外部source/` 任何 md ...
 - ❌ 不读 `context/inquiry-compound-vision.md`
 - ❌ 不读 `context/raw-questions-synthesis.md`
+- ❌ 不读 `context/crystallization-style-agent-brief.md`（v2.3 起禁读；essence 已迁入 lexicon v2）
 - ❌ 不读 `inquiry-chain-demo-v3-good-answer.md` 全文
 - ❌ 不读 `round2/route_helper.py` 与 spec
 - ❌ 不读 [pipeline-a-diagnose.prompt.md](pipeline-a-diagnose.prompt.md)
 - ❌ 不读 `回答版本explore/良质回答标注册.md`
```

### B.3 §5 反例改动（11 条 → 5 条结构反例）

原 §5 标题：`## 5. 反例（system 反例唯一权威；正向规则与拒杞表见 user lexicon）`

新 §5 标题：`## 5. 反例（结构级；内容级反例见 lexicon §5）`

新 §5 开头加一句：

> **结构级反例**收在 prompt（routing / output_kind / A→B 边界 / append-only 语义 / raw_answer_seeds 护栏），影响输出**形态**；
>
> **内容级反例**（mechanism 退化分析口吻 / anchor 含 CS 词 / micro_steps 抽象规劝 / 刺痛裸奔 / 公式 / meta anchor 退化具体动作）全部迁入 `[pipeline-b-style-lexicon-v2.md](../context/pipeline-b-style-lexicon-v2.md)` §5。

**保留的 5 条结构反例**（原编号 → 新编号）：


| 新编号    | 原编号   | 名                                    | 为什么留 prompt                                      |
| ------ | ----- | ------------------------------------ | ------------------------------------------------ |
| 反例 5.1 | 反例 6  | 把 A 的 mechanism_sketch 复制当 mechanism | B 的 single_responsibility 边界（必须转译不能 passthrough） |
| 反例 5.2 | 反例 8  | route=update 时输出整张新卡 / 改动原卡字段        | output_kind 结构 + append-only 语义                  |
| 反例 5.3 | 反例 9  | 把 update_directives.* 的方向描述当文本输出     | A 给方向，B 写最终文本——A→B 边界                            |
| 反例 5.4 | 反例 9b | 在 update_entry 里复制原 mechanism 再"改写"  | append-only 心智坑（核心结构错）                           |
| 反例 5.5 | 反例 11 | raw_answer_seeds.not_for_anchor 被忽略  | B 必须尊重 A 给的护栏——A→B 契约                            |


**删除/迁走的 7 条**（原编号 → 去向）：


| 原编号   | 名                         | 去向             |
| ----- | ------------------------- | -------------- |
| 反例 1  | mechanism 退化为分析口吻         | → lexicon §5.1 |
| 反例 2  | anchor 太长 / 含 CS 词        | → lexicon §5.2 |
| 反例 3  | anchor 22 字含转折            | → lexicon §5.3 |
| 反例 4  | micro_steps 抽象规劝          | → lexicon §5.4 |
| 反例 5  | mechanism 写公式             | → lexicon §5.5 |
| 反例 7  | 刺痛裸奔                      | → lexicon §5.6 |
| 反例 10 | meta_card anchor 退化为具体动作句 | → lexicon §5.7 |


### B.4 §1 §2 几处零星引用更新

```diff
-2. **写 final mechanism**：基于 A 的 `mechanism_sketch`，按 brief §4 + lexicon §2 写作规则转译为 30-200 字
+2. **写 final mechanism**：基于 A 的 `mechanism_sketch`，按 lexicon §0 + §2 写作规则转译为 30-200 字
```

§2A.3 anchor 写法也类似——把 `brief §4` 引用全部改为 `lexicon §2`；grep `brief` 看其它残留。

### B.5 Notes for human chat 模板更新

```diff
 # Inputs
 
 ## pipeline_a_draft
 <粘 agents/runs/run_<date>_pipeline-a_<scenario>.json>
 
 ## existing_card_json  (仅 route=update 时必填)
 <从 data/chains.json 抽出 target_ic_id 对应那一项 object 的完整 JSON>
 
 ## style_lexicon  (B 唯一权威风格规则)
-@pipeline-b-style-lexicon-v1.md
-
-## style_brief  (实际生效仅 §1 / §4)
-@crystallization-style-agent-brief.md
+@pipeline-b-style-lexicon-v2.md
 
 ## schema_lint  (实际生效仅 §2.5 / §2.6 / §2.7)
 @crystallization-schema-v0.md
```

> **批注区 B**：prompt 改动的批注 ↓
>
> - 
> - 

---

## Part C：brief 退役方案

**选项 A（推荐）**：brief 文件全文不动，仅在顶部加 deprecation banner：

```markdown
# Crystallization / 伴侣回答风格 — Agent 复用简报

> ⚠️ **2026-05-22 起 agent 不再读本文档**——Pipeline B 写卡规则全部在 `[pipeline-b-style-lexicon-v2.md](pipeline-b-style-lexicon-v2.md)`。
>
> 本文档保留为**人类档案**：§2 用户原文反馈归档 / §3 迭代脉络 / §6 双主轴 routing / §7 扩展阅读 / §8 实证归纳 等长期价值大于删除（agent 不读不等于人不读）。
>
> 维护契约：今后**不再**写新 § 内容；若有新风格洞察直接进 lexicon。本文件冻结作 history。

> **受众**：后续 subagent、打包 prompt、或生成 Inquiry Chain Crystallization 时必读。  
> **目标**：情绪信息完整、推理可执行、**少废话、省 token**；全文优先读本节 + §2 原文反馈；**实证规则见 §8**；执行细则见 §4–§6。  
> **关联**：`context/inquiry-compound-vision.md`（产品灵魂）、`context/crystallization-implicit-knowledge-anchors.md`（隐性知识锚）、`回答版本explore/良质回答标注册.md`（条目 ID 与表）。

[ ... 原文 §1-§8 保持不动 ... ]
```

**选项 B**：rename brief → `crystallization-style-feedback-archive.md` 并精简到 §2/§3/§7。

**选项 A 优点**：最小改动，不破坏 schema-v0.md 的 `关联` 引用、不破坏 `.cursorrules` 引用、不破坏 sub2 / sub4 future synthesize prompt 中可能引用的路径；agent 路径已断（forbidden_inputs 加了）。

**选项 B 优点**：文件名诚实表达"已不是规则源"；缺点：rename 涉及多处引用 grep + 改。

**推荐 A** —— 心智上 deprecate ≠ delete；保留全文 + banner 就够了。

> **批注区 C**：brief 退役方案选 A 还是 B？↓
>
> 你的选择：

---

## Part D：agents_runtime 影响评估

**结论：零代码改动**。理由：

1. [agents_runtime/loader.py](../agents_runtime/loader.py) `load_prompt` 用通用 YAML 解析 → frontmatter 改完自动生效
2. [agents_runtime/context_builder.py](../agents_runtime/context_builder.py) `build_context` 遍历 `prompt.inputs` 自动按 type 装配 → 删 `style_brief` input → user message 自然少这一段
3. [agents_runtime/agents.py](../agents_runtime/agents.py) `run_b` 的 inputs dict 不传 `style_brief` 也无碍（context_builder 只按 prompt 声明的 inputs 找）

**唯一需要注意的**：

- [agents_runtime/_stats/parse_stats.jsonl](../agents_runtime/_stats/parse_stats.jsonl) 历史统计是 v2.2 数据；v2.3 起 user 长度变化，统计新增条目自然反映
- [agents_runtime/tests/test_orchestrate_dry.py](../agents_runtime/tests/test_orchestrate_dry.py) dry-run 测试我看过一眼应该只验 stage 顺序 + manifest 状态机；user 内容长度不在断言里 → 不会破。但**实施时跑一遍 pytest 确认**

**实施步骤**（待你 approve）：

```bash
# 1. 新建 lexicon v2（Part A 全文）
# 2. mv 旧 v1 到归档
mv context/pipeline-b-style-lexicon-v1.md context/_archive/lexicon-v1-2026-05-22.md
# （注意：sub2 也定义了同款归档方式，与本步骤路径一致）

# 3. 改 prompt frontmatter（Part B.1）
# 4. 改 prompt §3 表 + §5 反例（Part B.2/B.3）+ §1/§2 零星引用（Part B.4）+ Notes（Part B.5）
# 5. brief 顶部加 banner（Part C 选项 A）
# 6. .cursorrules Context curation 表更新（Part D 下一节）

# 7. 烟雾测试：跑一次 run_b 验证 B 不崩
./venv/bin/python3 -m agents_runtime.agents run_b runs/2026-05-21_觉醒_0f898d/a.json
# 看输出符合 schema + 风格无明显倒退

# 8. 测试
./venv/bin/python3 -m pytest agents_runtime/tests/ -q

# 9. dogfood 重跑 1-2 个有 feedback 历史的卡（球场垃圾话 / 觉醒），人工比对 v2.2 vs v2.3 b.json，看风格是否退步
```

### D.1 .cursorrules Context curation 表更新

```diff
 | Agent | 必读（runtime / chat 一致） | 禁读（`forbidden_inputs` + 纪律） |
 |---|---|---|
 | **Pipeline A** | ... | ... |
-| **Pipeline B** | A draft JSON；`crystallization-style-agent-brief` §1/§4；`pipeline-b-style-lexicon-v1`（`doc_full`）；schema §2.5–§2.7/§4/§6；`existing_card`（route=update）；fewshot 手选 | 标注册（v2.2+ forbidden）、A/B/Judge prompt、其它 raw 全文 |
+| **Pipeline B** | A draft JSON；`pipeline-b-style-lexicon-v2`（`doc_full`，唯一权威）；schema §2.5/§2.6/§2.7；`existing_card`（route=update）；fewshot 手选 | 标注册（v2.2+ forbidden）、**`crystallization-style-agent-brief`（v2.3+ forbidden）**、A/B/Judge prompt、其它 raw 全文 |
 | **Judge** | ... | ... |
 | **Push / merge** | ... | ... |
```

> **批注区 D**：agents_runtime 影响 / 实施步骤的批注 ↓
>
> - 

---

## Part E：待你确认的设计选择


| #   | 决策点                                               | 选项                                                              | 我的建议                                                                 |
| --- | ------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------- |
| E1  | 反例 5.7（meta anchor 退化为具体动作句）该留 prompt 还是迁 lexicon | A: 留 prompt（与 meta 强相关，结构级） / B: 迁 lexicon（本质是 anchor 家族纪律，内容级） | **B 迁 lexicon** —— 实质是 §3 attention 主轴态势感知家族纪律；route 只是触发条件          |
| E2  | 写作规则是 8 条全平铺 / 分两组（内容 6 + 节奏 2）/ 分三组              | 我已写成 2 组（内容 1-6 + 节奏 7-8）                                       | **2 组**（不要 3 组，认知负担）                                                 |
| E3  | brief 顶部 banner 选 A 还是 rename 选 B                 | A 不动 / B rename                                                 | **A 不动**                                                             |
| E4  | v2 是否同步删 `回答版本explore/良质回答标注册.md` 的引用             | 该文件早 v2.2 起 B 不读了；本次不动它                                         | **不动**（与 sub2 lexicon SSOT 收敛是两件事；标注册仍作人类标注源）                        |
| E5  | dogfood 验证用哪个 run 重跑                              | 球场垃圾话（update）/ 觉醒（meta）                                         | **两个都跑**——覆盖 update / meta 两条结构分支                                    |
| E6  | sub2 的 lexicon_proposals 与本次手动 v2 的关系             | 本次手工做完后 v2 是基准；sub2 跑 propose 时 base_version = v2               | **本次先手工 v2** —— sub1/sub2 还没落代码；这是一次性的 SSOT 整顿。落 sub2 之后所有 vN+1 都自动化 |


> **批注区 E**：6 个决策点你的选择 ↓
>
> E1:   
> E2:  
> E3:  
> E4:  
> E5:  
> E6:我都同意，你dogfood之后 记得跑一下merge工具看看

---

## Part F：执行 checklist（你 approve 后我跑）

按你 review + 批注后的最终方案，落实清单：

- F1 新建 `context/pipeline-b-style-lexicon-v2.md`（按 Part A 全文 + 你的批注）
- F2 `mv context/pipeline-b-style-lexicon-v1.md context/_archive/lexicon-v1-2026-05-22.md`（需先创建 `_archive/`）
- F3 改 `agent第二轮/pipeline-b-style.prompt.md` frontmatter（Part B.1）
- F4 改 `agent第二轮/pipeline-b-style.prompt.md` §3 表 + §5 反例（Part B.2/B.3）
- F5 改 `agent第二轮/pipeline-b-style.prompt.md` §1/§2 零星 brief 引用 + Notes 模板（Part B.4/B.5）
- F6 `context/crystallization-style-agent-brief.md` 顶部加 banner（Part C 选项 A）
- F7 `.cursorrules` Context curation 表更新（Part D.1）
- F8 烟雾测试：`run_b` 单跑 + `pytest -q`
- F9 dogfood 重跑 1-2 卡，记一份 v2.2 vs v2.3 对比短报告进 `agents_runtime/_stats/`（或 `_archive/lexicon-v1-2026-05-22.md` 附近）
- F10 把本 proposal 文档 mv 到 `agentflow3-tocode/_done/lexicon-v2-merge-proposal.md`（表示已 ratify 落档）

---

## Part G：风险与回滚


| 风险                                                                         | 缓解                                                                                        |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| v2 lexicon 内容级反例 7 条总共 ~80 行，加进 user 是新增长 → system+user 实际可能不降反升           | **实测前不下结论**；预期：删 brief §1/§4 (~~2.5k) > 加 lexicon §5 (~~1.8k) ⇒ 净降 ~0.7k。F8 烟雾测试时实测       |
| brief deprecated 后 sub2/sub4 future synthesize prompt 若引用 brief 会拿到不更新的旧规则 | sub2/sub4 还未落地；它们的 input 设计上就只读 lexicon（不读 brief）→ 无问题                                    |
| 写作规则 5 → 8 条变多 LLM 更挑剔 → 反而漏 routing 大局                                    | dogfood 跑两轮观察；若发现 attention 分散，把 #1 先拆假设 / #5 锋利协作 收回 brief 章节（最坏 30 分钟回滚）                |
| 反例 5.7（meta anchor）迁 lexicon 后 meta route 时 prompt 反例不提示 → 易漏              | prompt §5 结构反例最后加一句「meta 时 anchor 还要看 lexicon §3 attention 态势感知家族纪律 + §5.7」做一个 cross-link |


**回滚**：所有改动都是 markdown 改字 + 一次 mv；git revert 一个 commit 全恢复。

---

*草稿日期：2026-05-22。等待用户在 6 个批注区 + 6 个决策点写完意见后，我按最终方案真改文档与 .cursorrules。*