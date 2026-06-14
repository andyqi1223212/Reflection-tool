# Inquiry Crystallization · 把好回答压成可检索的「晶体卡」

把对话里那个 **trigger 当下的好回答**，自动提炼成结构化「晶体卡」的多 Agent pipeline。喂入一段对话，它产出一张可被你下次 trigger 时快速检索、命中、落地的卡。

---

## 为什么做它

跟 AI 深聊完的两三天，我整个人通透。再过一周，新情境又把我打回原形——更扎心的是，我想找回之前那段对话，几十个聊天记录翻不出来。

我意识到：我**不需要对话全量备份**。我需要的是，被触发的那一秒，能让我在 30 秒内松下来、落到一个小动作上的东西。

这个工具的设计原则只有一句：

> **问题是资产，答案是耗材。**

AI 几千字的共情和建议是耗材——会过期。但我**追问的路径**、以及我们一起命名出的那个**机制**是资产。晶体卡只存资产。

> 完整的设计故事见 [blog/refined-v1.md](blog/refined-v1.md)。

---

## 看一眼它在干啥

输入：[`examples/sample-conversation.md`](examples/sample-conversation.md) 里的合成对话片段——

> 朋友：我发现我每个周末都很颓废。明明计划得好好的——要看书、要运动、要学点新东西——但一到周六就开始刷手机，刷一整天。周日晚上又开始焦虑，恶性循环。是不是就是单纯的自制力差？
> 
> 我：……那周末刷手机就不是自制力问题，是你这一周都在"还债"……

跑一次 `python -m agents_runtime.orchestrate`，输出（节选自 [`examples/sample-run/b.json`](examples/sample-run/b.json)）：

```json
{
  "title": "周末计划学习却刷手机一整天，周日晚上焦虑",
  "axis": "attention",
  "patterns": ["P-KNOW-DO", "P-EFF", "P-SPIRAL"],
  "crystallization": {
    "mechanism": "你不是自制力差，是在用周末的刷手机补偿工作日欠下的自由账……",
    "anchor": "是身体在还自由账。",
    "micro_steps": [
      "每个工作日找 5 分钟完全为自己，不学习不工作。",
      "周末想刷手机时，先站起来走几步再决定。",
      "周日晚上焦虑时，默念：身体在还自由账。"
    ]
  }
}
```

下次你（或你朋友）卡在同一个状态，就直接默念 anchor + 跑三个 micro_steps，不需要重新分析一遍。

**为什么一张卡是「机制 + 入口句 + 小动作」这三层？** 因为被触发的那一秒，人**读不进长文**。你只来得及做三件事：知道发生了什么（机制把模糊感受**命名**）、抓一句话喘气（入口句作短锚）、做一件身体能动的最小事（小动作把抽象变可执行）。

---

## 5 分钟 Quickstart

```bash
# 1. clone
git clone https://github.com/andyqi1223212/Reflection-tool.git
cd Reflection-tool

# 2. install deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. configure API key
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY（https://platform.deepseek.com/）

# 4. bootstrap personal-content files from templates (first-run only)
bash tools/bootstrap.sh

# 5. run on the sample conversation
python -m agents_runtime.orchestrate examples/sample-conversation.md
```

如果一切顺利，1-2 分钟后你会在 `runs/<timestamp>_sample-conversation_*/` 看到一组 JSON 文件——其中 `b.json` 就是新产生的卡。这一步只是确认环境跑得通。

**确认跑通后，日常使用全程在前端，不用再碰命令行**——见下面。

---

## 开始用你自己的对话（全程在前端，不碰命令行）

日常用法只有三步：**导出对话 → 删到只剩问题 → 前端粘贴跑**。

### 1. 把 AI 对话导出成 markdown

现在 Chrome 上有不少插件能一键把你和 ChatGPT / Claude / DeepSeek 的对话导出成 markdown（应用商店搜 "export ChatGPT / Claude conversation" 一类即可）。导出后你会得到一段对话文本。

### 2. 只留「问题」，最多加上那一两句**核心触动**的回答

不要把 AI 几千字的回答整段喂进来。这个 pipeline 的 prompt 是按开头那句 **「问题是资产，答案是耗材」** 设计的——A agent 真正读的是你**追问的路径**（你问了什么、怎么一步步逼近），最多保留那一两句**真正点醒你的回答**。

> 喂太多答案，诊断会被原文的措辞带跑、抽不出底层机制；只留问题链 + 核心触动句，A 才能把机制重新长出来，而不是复述。

所以导出后删一删：**留问题链 + 最多 1–2 句核心触动回答**，就够了。

### 3. 在前端粘贴 → 运行 → 收卡

1. 开发台（`dev-hub.html`）点 **Pipeline Run**，或直接开 `pipeline_run.html`。
2. 在「1 · 选择或粘贴 Markdown」里，把上面整理好的对话**粘贴**进文本框（或从 `外部source/` 下拉选已有文件）。
3. 点 **运行 Pipeline**，等 1–2 分钟，A→B→Judge→push 自动跑完。
4. 去 **Inbox** 看这条 run：**accept** 的卡自动 append 到你的卡库（[`inquiry-chain-starter.md`](inquiry-chain-starter.md)），**reject** 就丢弃。
5. 攒一阵后，阅读 UI（`crystallization-prototype/index.html`）就能检索、浏览你所有的卡。

> 想批量 / 脚本化？命令行入口仍在：`python -m agents_runtime.orchestrate <你的对话.md>`。但日常用前端就够，不必碰 terminal。

---

## 三个不显然的工程选择

把一段聊天变成一张卡，技术上不复杂——三个 LLM 调用串起来谁都会写。跑过一两个月后，真正的瓶颈不在调用链，而在三件容易被低估的事：

**一、多 Agent 工作流的难点，是把"主观判断"压成"机器契约"。**
A 做心智诊断、B 做风格提炼、Judge 做审阅。但 Judge 不审"内容对不对"，它审"写作契约有没有破"。比如一条它实际在跑的规则：*机制里如果出现命名式刺痛（"你不是 X，是 Y"），小动作里必须包含至少 1 步身体能做的动作，否则打回重写*——因为刺痛裸奔接不住。把写作品味变成可程序检查的契约，才是 multi-agent 真正的工作量，不是 prompt 字数。

**二、上下文不是越多越好，是越干净越好。**
早期我把几百条历史标注全塞进 B 的 prompt，结果输出越来越糖浆化——因为标注里好坏混杂，AI 取了平均。修法是收敛出**唯一权威文件**（风格词典：8 条核心规则 + 入口句模板 + 反例），标注全表反而进 B 的"禁读清单"。同样的纪律施加到所有 agent：A 看不到风格词典、B 看不到 Judge 的 prompt、Judge 看不到 A/B 的 prompt——**context curation 和 prompt 写作是同等重要的两条腿**。

**三、风格自进化不用微调，用"文本权威 + 人在环"。**
没微调任何模型，也没跑 RLHF。因为风格词典是 markdown，模型权重不是——markdown 我能用 git 看每次改了什么、能一行回滚、能挑合成出来的 10 条规则里哪 3 条合并哪 5 条拒绝。闭环：打分吐槽 → 合成 agent 产"加进词典"的提案 → 提案躺在网页**待审收件箱**里（可预览前后 diff）→ 我点同意才合并、版本号 +1、旧版归档。整个过程没有黑盒，每条规则进入词典的时间、对应哪条反馈、为什么同意，全部可追溯。

---

## 它能 / 不能干什么

**能：**

- 中文对话 → 结构化卡片（带 trigger、机制、anchor、micro_steps、pattern tags、axis）
- 多 Agent 流水线：A（信息诊断）→ B（按 lexicon 风格化）→ Judge（质量裁判）→ push（入库）
- Lexicon 版本化迭代——你的写作审美随时间收敛
- 本地优先：所有数据在你机器上，不出本机（除了调用 LLM 的那一刻）

**不能**（不是 bug，是定位）：

- 不是通用 RAG / 向量库（小规模卡库用 TF-IDF 够；千卡以上再考虑向量）
- 不是 zero-config "AI 助手"——它**有审美偏好**，默认 lexicon / schema / 风格规则是基于中文对话拟合的；建议 fork 一份调成你自己的口味再攒卡，价值要等你积累 ≥10 张属于自己的卡之后才显现
- 不擅长英文场景的精调（lexicon 是中文 dogfood 出来的）

---

## 项目结构

```
agents_runtime/      A / B / Judge / push 四个 Agent 实现 + orchestrate 编排
agent第二轮/         四份 prompt SSOT（A/B/Judge/push 各一份）
context/             lexicon（B 的风格规则）+ schema + 文档
crystallization-prototype/   本地阅读 UI（卡片浏览 + 检索）
examples/            合成示例对话 + 跑通的输出
tools/               feedback server / export / validate 等开发工具
```

完整地图见 [导航.md](导航.md) 和 [agentflow3-tocode/codemap-agentflow.md](agentflow3-tocode/codemap-agentflow.md)。

---

## 配置入口

- **调 B 的风格规则（lexicon）**：[`context/pipeline-b-style-lexicon-v4.md`](context/pipeline-b-style-lexicon-v4.md)
- **调 prompt**：[`agent第二轮/<a|b|judge|push>.prompt.md`](agent第二轮/)
- **改 schema**：[`context/crystallization-schema-v0.md`](context/crystallization-schema-v0.md)（人类语义）+ [`data/inquiry-chain.schema.json`](data/inquiry-chain.schema.json)（机器契约）
- **切换用户数据目录**：`export IC_USER=yourname`，数据落到 `users/yourname/`

---

## 进阶

- 跑 dev UI（含 Inbox 人审、Lexicon Review、Pipeline Run）：`bash tools/start_dev_ui.sh`
- 反馈循环（feedback → lexicon 自进化）：见 [`agentflow3-tocode/dogfood-subplans/`](agentflow3-tocode/dogfood-subplans/)
- 架构细节：[`agentflow3-tocode/codemap-agentflow.md`](agentflow3-tocode/codemap-agentflow.md)

---

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

作者：haoyu（[@andyqi1223212](https://github.com/andyqi1223212)）

---

*如果你跑通了第一张属于你自己的卡，欢迎开 issue 告诉我。这个项目最大的好奇心就是：除了我之外，还有谁的审美会被它接住。*
