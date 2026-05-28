# Crystallization Schema v0

> **角色**：把"良质回答"的实证规则（`context/crystallization-style-agent-brief.md` §4 / §8、`回答版本explore/良质回答标注册.md` §〇 / §八）固化成一份**可对一张卡做自动 lint** 的数据原子定义。
>
> **关联**：
> - 内容样本：`inquiry-chain-demo-v3-good-answer.md`（23 张已重写的卡）
> - 产品愿景：`context/inquiry-compound-vision.md` §4（Inquiry Chain 数据原子）
> - 风格简报：`context/crystallization-style-agent-brief.md`
> - 标注实证：`回答版本explore/良质回答标注册.md`
>
> **目标**：让以后任何 agent / subagent / 工程实现读完这份就能写出合格 Crystallization，不必重新读对话历史。

---

## 1. 一张卡到底长什么样（自然语言版）

```text
IC-004：课堂题没做出，害怕老师同学觉得自己装、笨

[mechanism]  你不是只在做题，你还在维护"提前学过 → 必须答得好"的人设。
             证明压力一进来，工作记忆就被它占满，剩下的算力解题不够用。
[anchor]     得失心，不进考场。
[micro_steps]
  1. 卡住时先写下确定的条件，不开内心法庭。
  2. 把问题问成具体卡点，不问自己笨不笨。
  3. 下课只复盘解题流程，不复盘老师的表情。
[patterns]   P-EVAL · P-FAMILY · P-KNOW-DO
[axis]       attention
[source_refs] C12 · B11 · F07
[chain]
  trigger:   提前学过 ML / 线代，上课问问题、帮同学解释，
             但课堂练习题做不出来，开始害怕老师同学觉得装或笨。
  questions: [我听的时候理解了，做的时候想偏了，脑子紧焦虑;
              我怕老师觉得我很菜、爱装; ...]
```

这一张卡承担两件事：

- 被 trigger 时只看 `anchor`、不超过 `mechanism` + `micro_steps`，3–10 秒着陆。
- 反思时展开 `chain`，复盘当时的追问路径与情境，可一键打包成 md 给 Gemini。

---

## 2. 字段定义（每个字段都有具体功能）

### 2.1 `id`（必填）

格式：`IC-NNN`（三位数字，含前导零，如 `IC-004`）。

为什么需要：稳定主键。卡片改写、合并、迁移到代码后都不会断链；`source_refs` 也用 ID 互引。

### 2.2 `title`（必填，≤60 字）

一句话情境标签，写情境而不是结论。命名规则：`<场景> + <核心情绪/行为>`。

- 好：`课堂题没做出，害怕老师同学觉得自己装、笨`
- 差：`处理评价恐惧的方法`（变结论）；`关于学习的卡`（无情境）。

### 2.3 `patterns`（必填，1–4 个）

来自固定词表（vision §4 的"心理结构 tag"）：

| Tag | 含义 |
|-----|------|
| `P-EVAL` | 评价恐惧 / 完美形象的牢笼 |
| `P-OVER` | 过度共情 / 过度负责 → 愧疚 |
| `P-SPIRAL` | 灾难化思维 / 万一链条 |
| `P-EFF` | 得失心绑架 / 工具理性焦虑 |
| `P-UNDER` | 被 underrated / underdog 扬眉吐气 |
| `P-EXIST` | 存在性焦虑 / 终极安全感缺失 |
| `P-KNOW-DO` | 知行裂痕 / 道理太多 |
| `P-FAMILY` | 原生家庭 / 跨阶级心理底色 |

为什么必填且最多 4：tag 是检索灵魂；超过 4 个就退化成话题归类，违反 vision §5"按底层 pattern 不按表面话题"。

### 2.4 `axis`（必填，二选一）

来自简报 §6 的双主轴 routing：

- `judgment`：判决外包 / 愧疚链。trigger 时用户痛在"羞 / 愧 / 怕别人"。
- `attention`：自我架构 / 注意力经济。trigger 时用户痛在"空 / 漂 / 偷算力 / 证明"。

为什么必填：实证显示，全部往愧疚库堆是常见误差；axis 是粗粒度路由，让"我又在偷算力"和"我又在愧疚"被引到不同卡组。

### 2.5 `crystallization.mechanism`（必填，30–200 字）

1–2 句话命名当下机制。**写法纪律**：

- 先命名再因果（"…不是 X，是 Y。Y 导致 Z"）。
- 用生活 / 身体 / 关系隐喻，不用 CS 隐喻。
- 一段一支点；一句铺底 + 一句切入即够，不复读。
- 长度上限 200 字是为了避免 v2 的"分析总结化"——超长往往是在絮叨。

### 2.6 `crystallization.anchor`（必填，≤20 字）

可默念短锚。**写法纪律**：

- 名词 / 动词为主，禁形容词堆。
- 二元对比结构往往最稳（"X 是 Y，不是 Z" / "A 还给 B"）。
- 不出现 "AI / 系统 / 编译 / 算力 / 进程 / API" 等 CS 词。

### 2.7 `crystallization.micro_steps`（必填，1–3 步，每步 ≤60 字）

可执行小动作。**写法纪律**：

- 动词开头：先 / 再 / 把 / 写 / 问 / 默念 / 回到…。
- 每一步在身体或当前 5 分钟内能做的事，不抽象。
- 不出现"通过 / 长期 / 慢慢"等需要时间证明的词。

### 2.8 `chain.trigger`（必填）

当时的现实情境（一段，1–4 句）。保持原汁原味的事件描述，不是分析。

### 2.9 `chain.questions`（必填，≥2 条）

用户在那次对话里**自己问的问题**，按时间顺序。**只存问题，不存 AI 答案**——vision §2 的关键设计原则。

### 2.10 `source_refs`（推荐填，可空）

来自 `回答版本explore/良质回答标注册.md` 的高分句 ID 列表（如 `B10`、`F01`、`H07` 等），表示这张卡的素材出处。

为什么需要：内容审计 + 未来 dogfood 时如果某条素材失效，能反向定位影响哪些卡。

### 2.11 `created_at`（推荐填）

ISO 日期字符串（如 `2026-05-09`）。**仅用于排序与回溯**——不做心态曲线 / streak / 成长 metric（vision §8 anti-feature）。

---

## 3. JSON Schema（draft-07，可直接喂工具校验）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "InquiryChain",
  "type": "object",
  "required": ["id", "title", "patterns", "axis", "crystallization", "chain"],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^IC-\\d{3}$"
    },
    "title": {
      "type": "string",
      "minLength": 4,
      "maxLength": 60
    },
    "patterns": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "uniqueItems": true,
      "items": {
        "enum": [
          "P-EVAL",
          "P-OVER",
          "P-SPIRAL",
          "P-EFF",
          "P-UNDER",
          "P-EXIST",
          "P-KNOW-DO",
          "P-FAMILY"
        ]
      }
    },
    "axis": {
      "enum": ["judgment", "attention"]
    },
    "crystallization": {
      "type": "object",
      "required": ["mechanism", "anchor", "micro_steps"],
      "additionalProperties": false,
      "properties": {
        "mechanism": {
          "type": "string",
          "minLength": 30,
          "maxLength": 200
        },
        "anchor": {
          "type": "string",
          "minLength": 4,
          "maxLength": 20
        },
        "micro_steps": {
          "type": "array",
          "minItems": 1,
          "maxItems": 3,
          "items": {
            "type": "string",
            "minLength": 5,
            "maxLength": 60
          }
        }
      }
    },
    "chain": {
      "type": "object",
      "required": ["trigger", "questions"],
      "additionalProperties": false,
      "properties": {
        "trigger": {
          "type": "string",
          "minLength": 10
        },
        "questions": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "string",
            "minLength": 4
          }
        }
      }
    },
    "source_refs": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "created_at": {
      "type": "string",
      "format": "date"
    }
  }
}
```

注意：JSON Schema 只能管**结构 / 长度 / 枚举**这一层；下面 §4 的"内容 lint"是它管不到的部分，需要靠人工审阅或后续 LLM critic。

---

## 4. 内容 lint：JSON Schema 之外的写作纪律

### 4.1 双层过滤器（机制 × 载体）

来自简报 §8.1：

1. **先看机制是否值得保留**：因果是否准、是否能命名一个 pattern。
2. **再选载体**：默认生活 / 身体 / 关系隐喻；用户对某词反感（如"脏数据"）时，**保机制、换载体词**——这条卡的机制不丢，描述用户能默念的词。

### 4.2 拒杞词清单（默认不进卡片正面）

| 类别 | 例 | 处置 |
|------|----|------|
| CS / 工程 | 算力、ETL、编译、CI/CD、root、API、过拟合、interrupt handler | 改写为生活语言；除非用户消息**先**用工程语 |
| 显式公式 | "愧疚 = 责任感 × 情绪 ÷ 事实清晰度" | 不进 `mechanism` / `anchor`；可作为开发者注释或 v1 扩展字段 |
| 鸡汤糖浆 | 反复"你已经很棒"、"加油"、"相信自己" | 删；情感卡路里高 / 认知卡路里低 = 婆婆妈妈 |
| 抽象正确的废话 | "重要的是 mindset"、"找到自己" | 删；改成可观察行为 |

实证依据：标注册中 A03 / A04（公式）、C05 / C06 / C15（CS 隐喻）认同度 = 2，明显偏低；B10 / B13 / C11 / C12（短锚 + 能动）= 4，明显偏高。

### 4.3 长度折旧规则

来自简报 §8.3：同一 pattern 下，**第一条**长叙事（如 F08、F09）可有冲击力；从**第二条**开始读者会"太麻烦"。

写作时：

- 索引层（`anchor` + 可见的 `mechanism`）严格压短；
- 故事 / 长记忆放进 `chain.trigger` + `chain.questions`，靠折叠区承接；
- 同一 pattern 内的多张卡尽量复用同一个 anchor 家族（不重复全长展开）。

### 4.4 刺痛与着陆配对

来自简报 §8.5：高刺痛自省（如 H11"24h 风险雷达 / 智力优越感护城河"）必须与"着陆垫"句（H09 三件套 / F05"把平静留给自己"）同包出现，不能让 `mechanism` 单行刺痛裸奔。

工程上：lint 时若 `mechanism` 含负向命名（"你不是…，是…"）但 `micro_steps` 全是抽象规劝（无身体动作），需打回。

### 4.5 字段间一致性

| 检查 | 通过条件 |
|------|----------|
| `axis` ↔ `patterns` | `judgment` 至少含 `P-EVAL` / `P-OVER` / `P-UNDER` / `P-FAMILY` 中之一；`attention` 至少含 `P-SPIRAL` / `P-EFF` / `P-KNOW-DO` / `P-EXIST` 中之一 |
| `anchor` ↔ `mechanism` | anchor 应是 mechanism 的最短摘要句，能从 mechanism 推出 |
| `micro_steps` ↔ `mechanism` | 每一步对应 mechanism 里命名的一个支点（命名 → 拆分 → 替代动作） |
| `chain.questions` ↔ `chain.trigger` | questions 第一条应能由 trigger 直接派生（情境一致） |

---

## 5. Example：一条完整合规卡（IC-004 of v3）

```json
{
  "id": "IC-004",
  "title": "课堂题没做出，害怕老师同学觉得自己装、笨",
  "patterns": ["P-EVAL", "P-FAMILY", "P-KNOW-DO"],
  "axis": "attention",
  "crystallization": {
    "mechanism": "你不是只在做题，你还在维护『提前学过 → 必须答得好』的人设。证明压力一进来，工作记忆就被它占满，剩下的算力解题不够用，越想表现好越做不出。",
    "anchor": "得失心，不进考场。",
    "micro_steps": [
      "卡住时先写下确定的条件，不开内心法庭",
      "把问题问成具体卡点，不问自己笨不笨",
      "下课只复盘解题流程，不复盘老师的表情"
    ]
  },
  "chain": {
    "trigger": "提前学过机器学习 / 线代，上课问老师问题、帮同学解释，但课堂练习题做不出来，开始害怕老师同学觉得自己装或笨。",
    "questions": [
      "我听的时候理解了，做的时候想偏了，脑子紧焦虑",
      "我怕老师觉得我很菜、爱装",
      "老师笑笑说不影响分数，我又害怕他是不是笑话我",
      "我是不是提前学了，就一定要表现完美？",
      "我害怕老师觉得我笨，想到高中老师用聪明/笨 judge 人"
    ]
  },
  "source_refs": ["C12", "B11", "F07"],
  "created_at": "2026-05-09"
}
```

人工审阅时，从上到下扫一遍：

1. tags + axis 匹配（`P-EVAL` 对 `judgment`？这里偏 `attention`，因为机制讲算力被偷——✅ 与简报 §6 一致）。
2. mechanism 30–200 字，无 CS 词，命名 + 因果两层（人设 → 算力被占）。✅
3. anchor ≤20 字，可默念，二元结构（X，不进 Y）。✅
4. micro_steps 三步，动词开头，5 分钟内能做。✅
5. chain.questions ≥2 条，由 trigger 自然派生。✅
6. source_refs 指向标注册 C12 / B11 / F07，便于反查。✅

---

## 6. 反例：哪些卡会被 lint 打回

### 6.1 mechanism 退化成分析总结

```text
[mechanism] 这条链把学习问题和评价问题缠在了一起。真正卡住的不只是题，
            而是"我已经展示过我懂，所以我必须持续证明我懂"。一旦证明
            压力升起，工作记忆被评价恐惧占用，解题能力反而下降。

[anchor]    练习是暴露 bug，不是维护人设。
```

问题：mechanism 写得对但是"分析总结口吻"，anchor 用了"bug"（CS 词）。

修：见 §5 example。

### 6.2 anchor 太长 / 太抽象

| 不合规 anchor | 问题 | 修订 |
|--------------|------|------|
| "我可以证明，但我不为审判而活。" | 22 字，含转折，不易默念 | "生存战已打完。" |
| "未闭环，不等于已失控。" | 抽象正确，但缺画面 | "警报响了，火没烧。" |

### 6.3 micro_steps 抽象规劝

| 不合规 step | 问题 | 修订 |
|------------|------|------|
| "保持平静，不要焦虑" | 抽象规劝，无动作 | "默念一次：警报响了，火没烧" |
| "学会接受不完美" | 时间维度模糊 | "卡住时先写下确定的条件" |

### 6.4 公式 / 工程隐喻进了正面

```text
[mechanism] 愧疚感 = 责任感 × 他人情绪 ÷ 事实清晰度
[anchor]    把愧疚的分母拉大
```

问题：A03 / A04 实证为 2 分；公式可放进开发者注释或 v1 扩展字段，但不在卡片正面 trigger 首屏。

---

## 7. 双主轴 routing 速查（写卡时先定 axis 再写）

| Axis | 用户当下痛感 | 典型 patterns | 入口锚句家族 |
|------|--------------|--------------|--------------|
| `judgment` | 羞 / 愧 / 怕别人 / 被瞧不起 / 想证明 | `P-EVAL` `P-OVER` `P-UNDER` `P-FAMILY` | "把评判权还给他"、"在乎你但不替你管理全部感受"、"那合同已经过期了" |
| `attention` | 空 / 漂 / 偷算力 / 没闭环 / 万一 | `P-SPIRAL` `P-EFF` `P-EXIST` `P-KNOW-DO` | "得失心不进执行现场"、"警报响了火没烧"、"我在这里我活着我感受" |

写卡先问：**用户当下是被人 judge 吓到，还是被未来 / 算力 / 不闭环 漂走？** 这一步定 axis，axis 决定整张卡的语调。

---

## 8. v0 之后的钩子（不实现，留接口）

按 vision §9：

- **v1**：在每条卡上自动跑 embedding，按聚类自动生成 emergent taxonomy → 字段建议保留 `embedding: number[]`（不在 v0 schema，但 `additionalProperties: false` 应改为 `true` 以便平滑扩展）。
- **v2**：agent workflow 自动决定检索深度 / 打包大小 → 字段建议保留 `usage_log: { triggered_at, picked_anchor, packed_into_md }[]`。

v0 **不允许**提前实现这两个，但 schema 演进时不要破坏向后兼容（新增字段而不是改语义）。

---

## 9. 文件契约（生效后所有 agent 须遵守）

1. 写新卡：先读简报 §4 / §8 + 本文档 §2 / §4，再写。
2. 修旧卡：保留 `id`，更新 `created_at`；`source_refs` 跟着内容改写同步增减。
3. 重命名 pattern 词表：要更新 vision §4、本文档 §2.3、`.cursorrules` Scratchpad 三处，缺一不可。
4. **不允许**：把卡降级为"普通笔记"或"对话存档"——即不写 `mechanism / anchor / micro_steps` 三层。

---

*最后更新：2026-05-09 — 与 `inquiry-chain-demo-v3-good-answer.md` 同步。*
