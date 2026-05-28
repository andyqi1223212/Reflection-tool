# Inquiry Crystallization · 把好回答压成可检索的卡

把对话里那个 **trigger 当下的好回答** 自动提炼成结构化「晶体卡」的多 Agent pipeline。喂入一段对话，它产出一张可被你下次 trigger 时快速检索、命中、落地的卡。

> 这是一个**有审美偏好**的工具：默认 lexicon、schema、风格规则是基于中文对话场景拟合的。建议 fork 一份、调成你自己的口味，再开始攒卡。
> 没有"开箱即用的 AI 助手"——它的价值要等你积累 ≥10 张属于你自己的卡之后才会显现。

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

---

## 5 分钟 Quickstart

```bash
# 1. clone
git clone <repo-url>
cd <repo-dir>

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

如果一切顺利，1-2 分钟后你会在 `runs/<timestamp>_sample-conversation_*/` 看到一组 JSON 文件——其中 `b.json` 就是新产生的卡。

跑通了？继续看下面"开始用你自己的对话"。

---

## 开始用你自己的对话

1. 把一段对话存成 markdown（任意路径，例如 `examples/my-talk.md`）。格式很自由——pipeline 看的是语义而不是结构。
2. 跑：

   ```bash
   python -m agents_runtime.orchestrate examples/my-talk.md
   ```

3. 启动本地 dev UI 看产出的卡：

   ```bash
   bash tools/start_dev_ui.sh
   # 浏览器自动打开 http://127.0.0.1:8765/dev-hub.html
   ```

   在 Inbox 里 accept / reject 每条 run，accept 的卡会自动 append 到你的 [`inquiry-chain-starter.md`](inquiry-chain-starter.md)。

4. 攒到一定数量后，跑 `python3 tools/export_v3_chains.py` 把卡库 export 成可检索的 JSON，前端 UI（`crystallization-prototype/index.html`）就能浏览了。

---

## 它能 / 不能干什么

**能：**

- 中文对话 → 结构化卡片（带 trigger、机制、anchor、micro_steps、pattern tags、axis）
- 多 Agent 流水线：A（信息诊断）→ B（按 lexicon 风格化）→ Judge（质量裁判）→ push（入库）
- Lexicon 版本化迭代——你的写作审美随时间收敛
- 本地优先：所有数据在你机器上，不出本机（除了调用 LLM 的那一刻）

**不能**（不是 bug，是定位）：

- 不是通用 RAG / 向量库（小规模卡库用 TF-IDF 够；千卡以上再考虑向量）
- 不是 zero-config "AI 助手"——你必须调 lexicon 才能产你想要的风格
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

作者: \<待补充\>

---

*如果你跑通了第一张属于你自己的卡，欢迎开 issue 告诉我。这个项目最大的好奇心就是：除了我之外，还有谁的审美会被它接住。*
