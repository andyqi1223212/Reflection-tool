# Plan：从 chat agent flow 走到 code+api（v0.5 → v0.7 渐进式迁移）

> 触发源：用户 2026-05-17 提出"参考 `外部source/agentflow总结gemini.md` §13-22 的目标方向，但不绑技术栈/痛点/工程认知，只取参照，为我计划 from chat agent flow to code+api"。
>
> Gemini 总结里值得吸收的 4 条骨架（**作为参照，不是要求**）：纯 Python 编排器 / 物理化状态消除脑内合并 / Human-in-the-loop 2.0 异步审批 / 数据飞轮 RAG few-shot。本 plan 把这 4 条**裁剪到本仓库当前体量**（23 张卡、单人 dogfood、无并发、本地 file://）——能用文件解决就别上 DB，能用 Python wrapper 就别上 langgraph，能保留 md prompt 可读性就别 Jinja 化。
>
> 与 `agent第二轮/plan-update-append-mode.md` 的关系：那份是"prompt 层契约改造"的子工程；本份是"承载 prompt 的 runtime 层从 chat 切到 code"的母工程。两者正交、可并行——本 plan 不依赖 update_entry 链路全闭环，反过来 update_entry 链路也能在 chat 模式继续 dogfood 到本 plan 落地。
>
> **第一性原理（贯穿全 plan）**：
> 1. **状态在文件，不在 chat history**——这一条 v0.5 已经做到（`agents/runs/*.json`），code+api 模式继承这条
> 2. **LLM 是 stateless 转换算子**——A/B/Judge 已是单调用，没有多轮工具调用循环；code+api 模式不引入 agent loop，保持"一次调用一次产物"的纪律
> 3. **prompt 是人写给人读的工程资产**——md 不 Jinja 化，runtime 在 py 里拼装"frontmatter 给 code 看 / body 给 LLM 看"
> 4. **可逆**：每个 phase 落地后，chat 模式仍能跑通同一份 prompt——code 路径与 chat 路径长期并行，不删 chat 入口

---

## 已拍板决策（2026-05-17）

§6 那 6 个技术决策项已与用户对齐；细节展开见 §6 各节，下面是一站式摘要。

| 决策项 | 选项 | 备注 |
|---|---|---|
| §6.1 LLM 调用方式 | 复用 `tools/llm_api.py`（已支持 DeepSeek） | 验证若 JSON parse fail > 5% 再升级到 DeepSeek 官方 SDK |
| §6.2 Provider | **全 DeepSeek 分档**：A / Judge = DeepSeek v4 Pro（reasoning 档）；B = DeepSeek v4 Chat | 维护成本最低 + 保留 flagship / normal 区分；evaluator 独立性损失靠 §7 风险表里的缓解条 |
| §6.3 状态持久化 | 文件夹 `runs/<run_id>/*.json` | 人类直接 cat 可读；> 50 个 run 后再加 in-memory pandas 索引 |
| §6.4 prompt 模板化 | 完全不模板化 | py 在 `context_builder.py` 里按 frontmatter 字段名硬编码映射 ≤10 行 |
| §6.5 HITL UI | `crystallization-prototype/inbox.html`（纯前端） | accept 按钮显示一行命令让人粘到终端跑——保留"人在最后一关 commit"的体感 |
| §6.6 Phase 顺序 | 1 → 2 → 3 → 4 → 5 | Phase 1+2 视为一个原子里程碑 |
| 文档分流 | 本 plan + 本轮 code+api 后续新文档放 `agentflow3-tocode/`；`agent第二轮/` 不动 | 把"prompt 契约真理"与"runtime 迁移工程"两类文档物理分开 |

---

## 0. 改动总览

| Phase | 内容 | 性质 | 风险 | 估时 | 阻塞下一 phase？ |
|---|---|---|---|---|---|
| **§2 Phase 1：prompt → callable** | `agents_runtime/`：md loader + LLM client；A/B/Judge 各暴露一个 `run_*(inputs) -> dict` Python 函数 | 新增模块 | 中 | 1 天 | 是 |
| **§3 Phase 2：orchestrator** | `agents_runtime/orchestrate.py`：单 case A→B→Judge→push 全链；状态写 `runs/<run_id>/{a,b,judge,push}.json` | 新增脚本 | 中（替代 chat ferrying，需对照 chat 输出回归） | 0.5-1 天 | 否（后续 phase 可独立） |
| **§4 Phase 3：eval harness** | `agents_runtime/eval.py`：在固定 question_md 子集上批跑、与 baseline diff | 新增脚本 | 低 | 0.5 天 | 否 |
| **§5 Phase 4：inbox UI** | `crystallization-prototype/inbox.html`：列 conditional_pass / fail 案例，人手 accept→触发 push / reject→归档 | 新增页面 | 低（不动现有 prototype） | 1 天 | 否 |
| **§6 Phase 5：动态 few-shot RAG** | `agents_runtime/retrieval.py`：基于 question 文本 k-NN 取 v3 卡作 fewshot；Phase 3 eval 验证是否真的提质 | 新增模块 | 低-中（**先观测再做**，可能不需要） | 1 天 | — |

**总估时**：core 路径（Phase 1+2）约 1.5-2 天；扩展（Phase 3-5）按 friction 优先级再排。

**不在本 plan 范围**：

- 切换到 TypeScript / Cursor SDK 重写（现有 py 资产无法复用，ROI 低；本仓库 dogfood 量 < 100 卡用不上 TS 的工程红利）
- 引入 langgraph / autogen / crewai 等 agent framework（A/B/Judge 是固定 DAG，3 个节点 + 1 个闸门，框架的抽象成本 > 收益）
- 引入 SQLite / DuckDB / vector DB（23 张卡 → 100 张卡这个区间，`chains.json` + TF-IDF 完全够用；迁 DB 是 200+ 张卡时再说）
- Web 后端 / 用户系统 / 多用户并发（单人 dogfood，本地 file:// 够用）
- Prompt Jinja 模板化（破坏现有 md 可读性，并且 frontmatter 已经把"动态部分"压到几个 inputs；不值得引入第二层 DSL）

---

## 1. 当前 L4.5 状态盘点（不是从 Gemini 抄，是审视本仓库）

### 1.1 现在 chat 模式下的真实数据流

```
人类                             文件
─────────────────────────────────────────────
1. 开 chat，@ pipeline-a-diagnose.prompt.md
   @ <question.md>
   @ schema-v0.md @ raw-questions-synthesis.md
   @ route_helper 终端跑一次贴 stdout
2. LLM 输出 A draft JSON
3. 人类肉眼审 diagnostic_notes      ──→  agents/runs/run_<date>_pipeline-a_*.json
4. 关 chat，开新 chat（切 normal model）
   @ pipeline-b-style.prompt.md
   贴 A draft（粘 1-2 KB JSON）
   @ brief @ annot @ schema
   route=update 时 + 贴 existing_card_json
5. LLM 输出 B card / update_entry
6. 人类审 anchor 咯噔感             ──→  agents/runs/run_<date>_pipeline-b_*.json
7. 关 chat，开新 chat（切 flagship）
   @ judge.prompt.md
   贴 B output + route_context + existing_card
   @ rubric @ schema_lint @ v3 fewshot
8. LLM 输出 judge_report             ──→  agents/runs/run_<date>_judge_*.json
9. pass → @ push.prompt.md → Cursor agent 跑 shell
   conditional_pass / fail → 人类决定回 A 还是回 B 改 prompt
```

### 1.2 真实痛点（按 dogfood 体感排序，不照搬 Gemini）

| # | 痛点 | 触发频率 | 当前承受方式 |
|---|---|---|---|
| F1 | 跨 chat 的人工 ferrying 易漏字段（忘贴 raw_answer_seeds / 贴错 existing_card） | 每次跑 update 至少 1 次 | 跑一遍发现不对，回上一 chat 翻历史，浪费 5-10 分钟 |
| F2 | 改一句 prompt 想看效果，要把 A→B→Judge 三个 chat 全部重开重跑 | 每次 prompt iter | 拖延改 prompt 的意愿 |
| F3 | 没有 baseline 对比——改 prompt 后只能"感觉"分数有没有变好 | 每次 prompt iter | 改坏了不知道、改好了不知道 |
| F4 | conditional_pass / fail 的 case 散在 `agents/runs/*.json`，没法一眼看"最近 5 次 fail 集中在哪个维度" | 每周回顾时 | 翻 5-10 个 json 文件用脑子聚合 |
| F5 | few-shot 全靠人类记忆 / 翻 v3 md 找同 axis 卡 | 每次跑 A 或 Judge | `pick_fewshot.py` quick win 提过但未做 |
| F6 | route_helper 已经 plumbing 化，但调用还要人类手跑终端再贴 stdout | 每次跑 A | 浪费 30 秒，但更糟的是容易忘跑 |
| F7 | 脑内合并致幻（Gemini 命名） | route=update 的 Judge 阶段 | 已通过本日 judge.prompt v2.1 改"独立打分"消除——**不再是 runtime 层痛点** |

> **F7 已用 prompt 层解决**——这恰好说明：不是所有痛点都要等 code+api。但 F1-F6 都是 runtime 层痛点，prompt 层改不动。

### 1.3 已经做对的事（迁移时不能弄丢）

- **每 step 开新 chat** 的纪律 → code+api 模式天然继承（每次调用就是 stateless 函数）
- **forbidden_inputs / single_responsibility 写在 frontmatter** → loader 可以解析这两个字段做静态检查
- **stateless prompts + 文件状态** → code+api 模式直接复用 `agents/runs/` 目录结构
- **plumbing 与 reasoning 分离**（`push.prompt.md` 已是 `model_tier: plumbing`） → code+api 模式下 plumbing prompt 直接退化为 py wrapper，不再需要 md 形态
- **prompt 与 schema / annot / brief 解耦** → context 装配可以在 py 里完成，prompt 本身不变

---

## 2. 目标态 L5 code-orchestrated（pragmatic 版）

### 2.1 新数据流（与 §1.1 对照看）

```
人类                                code（agents_runtime/）
──────────────────────────────────────────────────────────────────
1. 编辑 question_md（或选既有）
2. python orchestrate.py <question.md>      ↓
                                            ① route_helper.run(question) → routing JSON
                                            ② loader.load("pipeline-a-diagnose")
                                               → 解析 frontmatter / inputs / forbidden / body
                                            ③ context = assemble_a_context(question, routing, retrieved_fewshot)
                                            ④ llm_client.call(prompt=body, context=context, model=reasoning)
                                               → A draft JSON（structured output API 强制 schema）
                                            ⑤ 写 runs/<run_id>/a.json
                                            ⑥ 同上跑 B（context 含 A draft + existing_card 若 route=update）
                                            ⑦ 写 runs/<run_id>/b.json
                                            ⑧ 同上跑 Judge
                                            ⑨ 写 runs/<run_id>/judge.json
                                            ⑩ if verdict==pass：自动跑 push 等价命令
                                               else：把 run_id 推到 inbox.html
3. 人类只在两个时刻介入：
   - inbox 里看 conditional_pass / fail：accept / reject / iter prompt
   - 想审 A 的诊断方向是否对：开 chat 模式跑一次同 question 做对照（chat 路径长期保留）
```

### 2.2 文件布局（与现有结构非破坏共存）

```
growth/
├── agents_runtime/                  ← 新增；code+api 的全部新代码住这里
│   ├── __init__.py
│   ├── loader.py                    ← 解析 md prompt frontmatter+body
│   ├── llm_client.py                ← 包 tools/llm_api.py 的 DeepSeek 调用 + retry / JSON parse
│   ├── context_builder.py           ← 按 prompt 的 inputs 字段从文件装配 context
│   ├── retrieval.py                 ← 动态 few-shot（Phase 5）
│   ├── orchestrate.py               ← CLI：跑单 case A→B→Judge→push
│   ├── eval.py                      ← CLI：批跑 + 与 baseline diff
│   └── tests/                       ← pytest：context_builder / loader 单测
├── agentflow3-tocode/               ← 新增 ← 本轮 chat→code 迁移所有新文档住这里
│   └── plan-chat-to-code-api.md     ← 本份 plan；后续新增 README / phase 进度 / friction 都进这里
├── agent第二轮/                     ← 完全不动；md prompts 仍是契约真理
│   ├── pipeline-a-diagnose.prompt.md
│   ├── pipeline-b-style.prompt.md
│   ├── judge.prompt.md
│   ├── push.prompt.md               ← code+api 模式下被 orchestrate.py 直接调 round2/run_pipeline.py 替代，但 md 保留作 fallback 触发方式
│   ├── conventions.md
│   ├── plan-update-append-mode.md   ← 旧 plan（prompt 层 append-only 改造），与本 plan 正交、共存
│   └── README.md                    ← 加一行分流指针到 agentflow3-tocode/
├── round2/                          ← 完全不动；继续作底层 plumbing
├── tools/                           ← 完全不动
├── data/chains.json                 ← 完全不动；retrieval.py 读它做 fewshot
├── crystallization-prototype/
│   ├── index.html                   ← 完全不动
│   ├── inbox.html                   ← 新增（Phase 4）
│   └── inbox.js / inbox.css         ← 新增（Phase 4）
└── runs/                            ← 新增；orchestrator 写 case 状态
    └── <YYYY-MM-DD>_<scenario>_<short_hash>/
        ├── input.json               ← question_md path + initial routing
        ├── a.json                   ← Pipeline A 输出 + 元数据（model / tokens / latency）
        ├── b.json
        ├── judge.json
        ├── push.json                ← 仅 verdict==pass 时存在；含 merge 命令 + exit code
        └── manifest.json            ← run 的元信息（创建时间 / 当前阶段 / verdict）
```

### 2.3 prompt md 与 py runtime 的契约

- **frontmatter（YAML）**：py 解析；定义 inputs / outputs schema / forbidden_inputs / model_tier
- **body（Markdown）**：作为 system prompt 完整喂给 LLM；py **不**重写、不模板化、不删反例
- **inputs[].source 字段**：py 按字段名去 `context_builder` 找对应文件 / 章节读出来，拼成用户消息
- **outputs.schema**：py 用作 LLM API 的 `response_format` / `tools.function.parameters`（DeepSeek 兼容 OpenAI `response_format: json_object` 形态），从物理上保证返回合法 JSON

举例：A 的 frontmatter `inputs: [{name: question_md, type: doc, ...}, {name: route_helper_output, type: json, ...}]`，py 拼出用户消息：

```
# question_md
<file 内容>

# route_helper_output
<JSON>

# v3 fewshot
<retrieval 选出来的 2-3 张卡>
```

system prompt = prompt md 的 body 部分（## 1. 角色 之后到文件末）。

---

## 3. 不动的资产（迁移时严格保留）

| 资产 | 现位置 | 为什么不动 |
|---|---|---|
| md prompts（A/B/Judge/push/conventions） | `agent第二轮/*.md` | 是品味与契约的真理来源；py 只读不写 |
| v3 卡库 | `inquiry-chain-demo-v3-good-answer.md` | 用户体感最终落地；retrieval / eval 都从这里取 |
| chains.json + chains.data.js | `data/` + `crystallization-prototype/` | UI 已稳定；导出由 `tools/export_v3_chains.py` 独家负责 |
| schema-v0 | `data/inquiry-chain.schema.json` + `context/crystallization-schema-v0.md` | A/B/Judge 都引用；code+api 模式直接复用 |
| 23 张卡 + 它们的 updates | v3 md | 不重新建库、不迁 DB |
| `round2/{run_pipeline,route_helper,next_ic_id}.py` | round2/ | plumbing 已稳定；orchestrator 是 subprocess.run 它们 |
| `crystallization-prototype/index.html` | 同上 | inbox.html 增量新增，不动主页 |
| 文件 state（agents/runs/*.json） | 已有 | runs/ 是新格式，但旧 agents/runs/ 不删除（chat 路径仍写它） |

---

## 4. 与 Gemini 总结的 4 条对照（哪些采用 / 哪些不采用）

| Gemini 提的 | 本 plan 的态度 | 理由 |
|---|---|---|
| 纯 Python 编排器 | 采用 | 现有 tools / round2 都是 py，运行时也用 py 减少跨语言成本 |
| LLM = stateless 转换算子 | 采用且已部分做到 | A/B/Judge 都是单调用；code+api 模式不引入 agent loop |
| 物理化状态 / 消除脑内合并 | 部分采用 + 已部分做到 | Judge 的脑内合并今天 v2.1 prompt 层已解决（不再合并）；本 plan 加 `runs/<run_id>/` 目录把跨 stage 的状态彻底 physicalize |
| Human-in-the-loop 2.0 异步审批 inbox | 采用（Phase 4） | conditional_pass / fail 散在 json 是 F4 痛点；inbox 是直接缓解 |
| 数据飞轮 vector DB + 动态 few-shot | 简化采用（Phase 5） | 用 TF-IDF + `chains.json` 起手；Phase 3 eval 验证有效再升级到 embedding |
| Pydantic + structured output 前置约束 | 采用 | `outputs.schema` 已是 JSON Schema 形态；DeepSeek 兼容 OpenAI `response_format: json_object` 即可起步 |
| YAML 静态 + Jinja2 动态 prompt | **不采用** | 现有 md prompt 是给人读的工程资产（含反例 / 自检 / Notes for humans）；Jinja 会破坏可读性 + 让 prompt 只能用 py 看 |
| SQLite / Vector DB | 不采用（当前体量） | 23 张卡 → 100 张卡区间用文件 + chains.json 完全够；DB 是 200+ 卡后的事 |
| 整套 L5 一次升级 | 不采用 | 渐进式 phase，每个 phase 落地后 chat 路径仍能跑——可逆是优先级第一 |

---

## 5. 分 Phase 详细设计

### 5.1 Phase 1：prompt → callable

> → **workhorse 实施详见 [`phase1-prompt-callable.plan.md`](phase1-prompt-callable.plan.md)**（含必读 / 禁读 / 函数签名 / 失败模式 / 接口契约）；下方为母 plan 摘要。

**目标**：把 md prompt 包装成 Python 函数 `run_a(inputs: dict) -> dict`，输出与 chat 模式 byte-identical（同 question_md / 同 fewshot / 同 model → 同 JSON 输出 ± LLM 非确定性）。

**模块**：

```python
# agents_runtime/loader.py
def load_prompt(name: str) -> Prompt:
    """读 agent第二轮/<name>.prompt.md，返回 Prompt 对象"""
    # 解析 ---frontmatter--- + body
    # 校验 frontmatter 必备字段（agent_id / version / model_tier / inputs / outputs / forbidden_inputs / single_responsibility）

# agents_runtime/llm_client.py
def call(*, system: str, user: str, model: str, response_schema: dict, temperature: float = 0.3) -> dict:
    """统一接口；底层调 tools/llm_api.py 的 DeepSeek provider"""
    # 内部 retry 1 次（DeepSeek 偶发 schema fail）；JSON parse 失败 fallback 到 plain text + json.loads

# agents_runtime/context_builder.py
def build_context(prompt: Prompt, inputs: dict) -> str:
    """按 prompt.inputs 的 source + sections 字段从文件读切片，拼出 user message"""

# agents_runtime/agents.py（薄壳）
def run_a(question_md_path: str, *, fewshot: list[str] | None = None, dry_run: bool = False) -> dict
def run_b(a_output: dict, *, existing_card: dict | None = None, fewshot: list[str] | None = None) -> dict
def run_judge(b_output: dict, route_context: dict, *, existing_card: dict | None = None, fewshot: list[str] | None = None) -> dict
```

**模型 slug 配置**（走 `.env`，不写死代码）：

```bash
# .env
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro     # A / Judge 用；reasoning 档
DEEPSEEK_CHAT_MODEL=deepseek-v4-chat         # B 用；chat 档；更便宜
DEEPSEEK_API_KEY=sk-...
```

`agents/run_a` / `run_judge` 调 reasoning model + temperature=0；`run_b` 调 chat model + temperature=0.3-0.5（详 §7 风险表 evaluator 共谋缓解条）。

**验收（end of Phase 1）**：

- [ ] `python -m agents_runtime.agents run_a 外部source/球场垃圾话应对策略.md` 在终端跑出 A draft JSON
- [ ] 与 `agents/runs/run_2026-05-11_pipeline-a_ball-trash-talk.json`（chat 模式跑的）逐字段对比，差异仅在自然的 LLM 抖动（mechanism_sketch 措辞 ± / patterns 排序）；axis / route / patterns 集合一致
- [ ] forbidden_inputs 在 py 里实施为 lint：context_builder 拒绝从 forbidden 列出的文件读内容，触发 `ForbiddenInputError`
- [ ] outputs.schema 通过 DeepSeek `response_format: json_object` 强制；返回非法 JSON 时 LLM 客户端自动 retry 1 次
- [ ] **JSON parse fail 率统计** 落到 `runs/<run_id>/_debug/parse_stats.json`；若 Phase 1 末日 fail 率 > 5%，升级到 DeepSeek 官方 Python SDK（openai 兼容协议，改动小）
- [ ] 单测覆盖：loader 解析 frontmatter / context_builder 装配 / llm_client mock 调用

**估时**：1 天专注开发 + 0.5 天回归。

### 5.2 Phase 2：orchestrator（替代 chat ferrying）

> → **workhorse 实施详见 [`phase2-orchestrator.plan.md`](phase2-orchestrator.plan.md)**（含 run_id 格式 / manifest schema / stage 实施 / exit code 解读 / resume 算法）；下方为母 plan 摘要。

**目标**：单 case 全链 A→B→Judge→push 由 `orchestrate.py` 串。人类只看最终 verdict + runs/<run_id>/ 目录。

**关键设计**：

- **run_id**：`<YYYY-MM-DD>_<scenario_slug>_<6_char_hash>`，scenario_slug 从 question_md 文件名抽
- **resume 友好**：每 stage 写完就落盘；中断后 `python orchestrate.py --resume <run_id>` 从下一 stage 继续
- **route 路由**：A 输出 route=update 时，orchestrator 自动从 `data/chains.json` 取 target_ic_id 对应卡填进 B / Judge 的 `existing_card` 参数（消除 F1 痛点）
- **route_helper 自动调**：orchestrator 进 A 之前自动跑 `round2/route_helper.py --include-raw-answer-excerpt`，输出存进 runs/<run_id>/route_helper.json（消除 F6 痛点）
- **push 闸门**：verdict==pass → 自动调 `round2/run_pipeline.py merge --mode <new|update>`；非 pass → 写 `runs/<run_id>/manifest.json` 标记 `awaiting_human`，不入库

**CLI 体感**：

```bash
# 全新场景，跑全链
python -m agents_runtime.orchestrate 外部source/新场景.md

# 已有 run，从某 stage 重跑（改完 prompt 后回归）
python -m agents_runtime.orchestrate --resume 2026-05-17_ball-trash-talk_a3f9c2 --from b

# dry-run（跑到 push 前停）
python -m agents_runtime.orchestrate 外部source/x.md --no-push
```

**验收**：

- [ ] 在 3 个历史 question_md（球场垃圾话 / 内卷正和博弈 / IC-012 关联场景）上跑通；与对应 chat 模式产物对照 verdict 一致
- [ ] 中途 kill 后 --resume 能从下一 stage 继续（不重跑已完成 stage）
- [ ] route=update 时 `existing_card` 自动从 chains.json 抽取——人类无需手动贴
- [ ] 失败时 manifest.json 含 `last_stage` / `last_error` / `next_action`，给人类可读的恢复指南

**估时**：0.5-1 天。

### 5.3 Phase 3：eval harness（prompt 迭代基础）

> → **workhorse 实施详见 [`phase3-eval-harness.plan.md`](phase3-eval-harness.plan.md)**（含 suite YAML schema / adversarial_cases 设计 / diff 报告渲染 / 漏判率硬 gate）；下方为母 plan 摘要。

**目标**：固化"回归测试集"——一组 (question_md, expected_route, expected_axis, expected_verdict_floor) 案例；每次改 prompt 后批跑、生成 diff 报告。

**关键设计**：

```python
# agents_runtime/eval.py
def run_suite(suite_yaml: str, *, baseline_run_id: str | None = None) -> SuiteReport:
    """读 suite 定义，并行跑 N 个 case，与 baseline 输出 diff"""
```

```yaml
# eval/suites/v0.7.yaml
cases:
  - question: 外部source/球场垃圾话应对策略.md
    expected_route: new
    expected_axis: attention
    expected_verdict_floor: pass
    expected_patterns_subset: [P-EVAL, P-EFF]
  - question: 外部source/睡前刷新.md
    expected_route: update
    expected_target_ic_id: IC-012
    expected_verdict_floor: pass
# 故意写差的对照集（给 §7 风险表 evaluator 共谋缓解条 (c) 用）
adversarial_cases:
  - question: tests/adversarial/anchor_too_long.md  # anchor 故意 22 字含转折
    expected_judge_fails: [anchor]
  - question: tests/adversarial/micro_steps_abstract.md  # micro_steps 全抽象规劝
    expected_judge_fails: [micro_steps, landing_pad_pairing]
```

**diff 报告**（输出到 `eval/reports/<date>.md`）：

```
| case | route | axis | verdict | mechanism | anchor | micro_steps | Δ from baseline |
|---|---|---|---|---|---|---|---|
| 球场垃圾话 | new ✓ | attention ✓ | pass ✓ | 4.5 (+0.0) | 4.5 (+0.0) | 4.5 (-0.5)⚠ | micro_steps 抽象规劝 +1 |
```

**验收**：

- [ ] 选 4-5 个代表性 case 建 v0.7 suite
- [ ] 改 B prompt 一处反例 → 跑 eval → diff 看 score 变化
- [ ] 报告同时给出 token 消耗 + latency（让 cost 显形）
- [ ] adversarial_cases 漏判率 < 10%（评估 Judge 在全 DeepSeek 单 provider 下的独立性）

**估时**：0.5 天。

### 5.4 Phase 4：inbox UI

> → **workhorse 实施详见 [`phase4-inbox-ui.plan.md`](phase4-inbox-ui.plan.md)**（含 file:// 加载策略 / inbox.html 骨架 / accept-reject modal / index.html 最小侵入修改）；下方为母 plan 摘要。

**目标**：把 `runs/` 里 `awaiting_human` 的 case 在浏览器列出来；人类点 accept → 触发 push；reject → 归档到 `runs/_rejected/`。

**关键设计**：

- 新页面 `crystallization-prototype/inbox.html`，**完全不改 index.html**
- 读 `runs/*/manifest.json` 列表渲染（直接 fetch 本地文件，纯前端）
- 每个 case 卡片显示：question_md 标题 / route / verdict / 6 维度 scores / suggested_revisions
- 点开看完整 A / B / Judge JSON（折叠区，与现有 index.html 折叠风格一致）
- accept 按钮：显示一行可点复制的命令 `python -m agents_runtime.orchestrate --resume <run_id> --from push --force-pass`，人类粘到终端跑
  - **注意**：accept 不修改 verdict 本体；而是写 `manifest.json` 的 `human_override: "accept"` 字段后让 push 直跑
- reject 按钮：把 run 目录移到 `runs/_rejected/<run_id>/`，附 `human_note.txt`

**验收**：

- [ ] 浏览器打开 `file:///.../inbox.html` 看到列表
- [ ] 跑一个故意 conditional_pass 的 case，在 inbox 里 accept → 看到 chains.json 增量更新
- [ ] reject 后该 case 从主列表消失，进入 `_rejected/`

**估时**：1 天。

### 5.5 Phase 5：动态 few-shot RAG（**先观测再做**）

> → **workhorse 实施详见 [`phase5-retrieval-rag.plan.md`](phase5-retrieval-rag.plan.md)**（含 TF-IDF char_wb ngram / orchestrator 接入 / gate 实验脚本 / embedding 升级路径）；下方为母 plan 摘要。

**目标**：跑 A / Judge 时，自动从 v3 卡库（chains.json）取最相关 2-3 张作 fewshot；替代人类手动 @ md 段。

**关键设计（极简版）**：

```python
# agents_runtime/retrieval.py
def top_k_cards(query: str, *, axis: str | None = None, k: int = 3) -> list[Card]:
    """对 chains.json 全卡建 TF-IDF（不持久化，每次调用 in-memory 建索引——23 张卡毫秒级）
    若指定 axis，先过滤同 axis 卡再算相似度"""
```

**前置 gate**：先在 Phase 3 eval suite 上对比"手选 fewshot vs 自动 fewshot" 的分数差。若自动版无显著退化（≤ 0.3 分平均），切换；若明显退化，先用手选，研究为什么 TF-IDF 没选对。

**升级路径（仅在 TF-IDF 不够时）**：
- 用 DeepSeek embedding 或 BGE 这类开源 embedding 离线建索引存进 chains.json 的每张卡新字段 `embedding: [...]`（不是单独 DB——保持文件即状态）
- retrieval 改为 cosine similarity

**验收**：

- [ ] Phase 3 eval 显示自动 fewshot 不显著退化
- [ ] retrieval 单测：相同 query 多次调用结果稳定（无随机性）

**估时**：1 天（仅 TF-IDF 版）。

---

## 6. 决策项详记（已于 2026-05-17 拍板；速查见顶部"已拍板决策"摘要表）

下面每节展开当时的选项与论据，留档便于半年后回看为什么这么选。

### 6.1 LLM 调用方式 — 已拍板：**复用 `tools/llm_api.py`**

候选选项：

| 选项 | 优点 | 缺点 |
|---|---|---|
| **A. 用现成的 `tools/llm_api.py`**（已拍板） | 已支持多 provider（含 DeepSeek）；改动小 | 不支持 structured output API / 流式 / tool use |
| B. 直接 DeepSeek 官方 Python SDK | 支持 `response_format: json_object`（强制返回合法 JSON） | 锁定 DeepSeek；切别家要再改 |
| C. LiteLLM 这类 proxy 库 | 多 provider + 都有 structured output | 多一层抽象；学习成本 |

**拍板理由**：先用 A 把系统转起来，维护成本最低。Phase 1 验收期统计 JSON parse fail 率：

- fail 率 < 5%：A 接受为稳定方案
- fail 率 ≥ 5%：升级到 B（DeepSeek 官方 SDK，openai 兼容协议，迁移成本 < 1 小时）

`llm_client.py` 内部加 retry 1 次 + 失败时 raw text 落 `runs/<run_id>/_debug/`，让 fail 可追溯。

### 6.2 LLM provider 选哪家 — 已拍板：**全 DeepSeek 分档**

候选选项：

| Provider | A/Judge（flagship） | B（normal） | 备注 |
|---|---|---|---|
| OpenAI | gpt-5.x / o-series | gpt-4o-mini | `.cursorrules` 里 llm_api.py 已支持 |
| Anthropic | Claude 4.x Opus | Claude 4.x Sonnet/Haiku | `.cursorrules` 里也支持 |
| 跨家混用 | A 用 Claude，Judge 用 OpenAI | B 用便宜的 | "judge 独立性"最强但运维 2 个 API key |
| **DeepSeek 单家分档**（已拍板） | DeepSeek v4 Pro（reasoning 档） | DeepSeek v4 Chat（chat 档） | 维护成本最低 + 保留 flagship / normal 区分 |

**拍板理由**：

- 用户已有 DeepSeek API 资源；单 provider 把运维成本压到最低（一个 API key、一份 .env、一个出账单）
- 通过 **档位差异化**（reasoning vs chat）+ **温度差异化**（A/Judge=0, B=0.3-0.5）部分恢复 evaluator 独立性——同家族不同档位的模型决策路径仍有差异
- evaluator 独立性损失通过 §7 风险表"evaluator 共谋"条目的 3 条缓解措施补：(a) 档位差异、(b) 温度差异、(c) Phase 3 eval 加 adversarial_cases 监测漏判率
- 若 Phase 3 监测到漏判率上升，**回退路径**：Judge 切到 Anthropic Sonnet 或 OpenAI 一档大模型即可（agents_runtime 已经做了 provider 抽象，改 .env 一个变量）

**配置形态**（走 `.env`，不在代码里写死）：

```bash
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro       # A 与 Judge
DEEPSEEK_CHAT_MODEL=deepseek-v4-chat           # B
DEEPSEEK_API_KEY=sk-...
# 未来若启用回退：
# JUDGE_FALLBACK_PROVIDER=anthropic
# JUDGE_FALLBACK_MODEL=claude-sonnet-4.x
```

### 6.3 状态持久化形态 — 已拍板：**文件夹 `runs/<run_id>/*.json`**

| 选项 | 优点 | 缺点 |
|---|---|---|
| **A. 文件夹 `runs/<run_id>/*.json`**（已拍板） | 人类直接 cat 可读；git friendly；零依赖 | 跨 run 查询要遍历目录 |
| B. SQLite `runs.db` | SQL 查询方便（"过去 10 次 fail 集中在哪") | 引入数据库；schema migration 烦 |
| C. 混合：文件存 payload + 索引存 SQLite | 两全 | 复杂度高 |

**拍板理由**：当跨 run 查询变频繁（> 50 个 run 后），加一个 `agents_runtime/index.py` 扫描 runs/ 目录建 in-memory pandas DataFrame——比 DB 简单 10 倍。

### 6.4 prompt 模板化程度 — 已拍板：**完全不模板化**

| 选项 | 优点 | 缺点 |
|---|---|---|
| **A. 完全不模板化**（已拍板） | md 仍是给人读的工程资产 | py 拼装 context 时要硬编码字段名（轻微重复） |
| B. 用 Jinja2 在 body 内 `{{ inputs.question_md }}` | DRY | 破坏 md 可读性；非 py 读者看不懂 |
| C. 单独 `_template.md` 与 `_body.md` 拆分 | 平衡 | 两份文件需要同步 |

**拍板理由**：py 在 `context_builder.py` 里按 frontmatter 的 inputs 字段名一对一映射，硬编码不超过 10 行。这点重复换回 md 的可读性极值。

### 6.5 HITL UI 形态 — 已拍板：**`inbox.html` 纯前端**

| 选项 | 优点 | 缺点 |
|---|---|---|
| **A. 在 `crystallization-prototype/` 加 `inbox.html`**（已拍板） | 复用现有静态站；零部署 | 纯前端无法触发 shell（accept 时要 fallback：UI 复制命令给人手跑） |
| B. 起个 Flask/FastAPI 小后端 | accept 按钮真能触发命令 | 引入后端 / 端口 / 进程管理 |
| C. CLI inbox（`python -m agents_runtime.inbox`）+ 选数字 accept | 单 py 进程通吃 | 不能浏览器多 tab 看 |

**拍板理由**：accept 按钮的工作方式 = UI 显示一行可点复制的命令，人类粘到终端跑——保留"人在最后一关用手指 commit"的体感，且不引入后端。后续若觉得复制粘贴烦，再升 B。

### 6.6 第一个 Phase 落地顺序 — 已拍板：**Phase 1 → 2 → 3 → 4 → 5**

| 选项 | 理由 |
|---|---|
| **A. Phase 1 → 2 → 3 → 4 → 5**（已拍板） | 1 → 2 是最大收益（消除 F1/F2/F6）；3 必须在 2 之后；4/5 看 friction |
| B. 先 Phase 3 eval | 没有 2 的 orchestrator，eval 没法批跑 |
| C. 先 Phase 5 RAG | 跳过基础设施直接做"高级功能"，风险高 |

**拍板理由**：Phase 1 + 2 视为一个原子里程碑（一起验收）；3/4/5 之间无强依赖，按 friction 优先级排（默认 3 优先于 4 优先于 5）。

---

## 7. 风险与回退

| 风险 | 概率 | 缓解 |
|---|---|---|
| LLM API 调用比 chat 慢 / 贵（同模型，结构化输出有额外开销） | 中 | 先 dry-run 一遍统计 token；若 > chat 的 1.5x 重审 prompt 是否塞太满 |
| DeepSeek `response_format: json_object` 在长 prompt 下偶发 schema fail | 中 | llm_client.py 内部 retry 1 次；连续失败时 fallback 到 plain text + 手动 json.loads；fail 率 > 5% 升级到 DeepSeek 官方 SDK（见 §6.1） |
| 自动 retrieval 选出的 fewshot 不如手选 | 中-高 | Phase 3 eval 做 gate；不通过就退回手选模式（手选 + 自动并存） |
| 人类失去"chat 模式审 anchor 咯噔感"的肉眼审 | 中 | inbox.html 必须显示 anchor 全文 + 一键播放（默念）；同时 chat 路径长期保留 |
| code+api 链路下出错难调试（vs chat 模式可以看每条消息） | 中 | llm_client.py 把每次调用的 full system+user message + raw response 落到 `runs/<run_id>/_debug/` |
| inbox accept 触发 push 时 verdict 还是 conditional_pass，py 拒绝执行 | 低 | accept 显式写 `human_override` 字段；push 命令读到这个字段视同 pass |
| md prompt 改了但 py loader 没跟上 frontmatter 新字段 | 低 | loader 用宽松解析（未知 key 仅 warn 不 fail）；conventions.md 里加一条"frontmatter 加字段要 grep agents_runtime/ 看有没有用" |
| **全 DeepSeek 单 provider，B 与 Judge 同家族模型可能共谋错**（evaluator 独立性损失） | 中 | 三条缓解：(a) Judge 用 reasoning 档（v4 Pro），B 用 chat 档（v4 Chat）——不同档位差异化判断；(b) Judge 调用 temperature=0，B 调用 temperature=0.3-0.5——强制 Judge 更确定性；(c) Phase 3 eval 加一组"故意写差的卡"作 adversarial_cases 对照集，跑 Judge 看 fail 是否抓得到——若漏判率 > 10%，回退到跨 provider 方案（见 §6.2 `JUDGE_FALLBACK_*` 配置） |

**回退策略**：每个 Phase 落地都不删除 chat 路径——`push.prompt.md` 仍可被 cursor agent 触发；A/B/Judge 仍可在 cursor chat 里手跑。code+api 任何 phase 出问题，回 chat 模式继续 dogfood。

---

## 8. 实施顺序

阻塞链：

```
§5.1 Phase 1：loader + llm_client + context_builder + agents 函数 + 单测
   │
   ▼
§5.2 Phase 2：orchestrate.py + runs/<run_id>/ 目录形态
   │
   ├──────► §5.3 Phase 3：eval harness + v0.7 suite + adversarial_cases + diff 报告
   │
   ├──────► §5.4 Phase 4：inbox.html
   │
   └──────► §5.5 Phase 5：retrieval.py（gate：Phase 3 验证有效）
```

Phase 3 / 4 / 5 之间无强依赖，按 friction 优先级排（默认 3 优先于 4 优先于 5）。

---

## 9. 与现有 plan / 文档的关系

- **`agentflow3-tocode/`（本目录）**：本轮 chat→code 迁移文档分流目录；后续 phase 推进时新增的 README / friction / phase 进度笔记都进这里，与 `agent第二轮/`（prompt 契约真理）物理分开
- **`agent第二轮/plan-update-append-mode.md`**：正交——append-only 是 prompt 层数据契约，本 plan 是 runtime 层；本 plan 落地后 update 链路天然受益（不再需要人手贴 existing_card）
- **`agent第二轮/push.prompt.md` §"未来 code+api 模式注意事项"**：本 plan 是那一段的展开实施版；落地后 push.prompt.md 退化为 fallback md（实际触发由 orchestrate.py 直接 subprocess.run round2 脚本）
- **`agent第二轮/README.md`**：Phase 2 落地后需更新 §1 workflow 图增加 code 路径分支；§3 调用顺序加"code+api 路径"小节并列于现有 chat 路径；本轮已在 §0 末尾加一行分流指针到 agentflow3-tocode/
- **`agent第二轮/conventions.md`**：Phase 1 落地后增加一节"py runtime 与 md prompt 的契约"——frontmatter 必备字段升级、forbidden_inputs 的 lint 实施
- **`.cursorrules`**：Phase 1 完成后在 # Tools 里加入"agents_runtime CLI 用法"

---

## 10. 备忘 / 不实施

- **多用户 / 协作**：单人 dogfood 阶段不做
- **权限 / 鉴权**：无网络部署不需要
- **prompt 版本 A/B 测试** ：Phase 3 eval 能手动对比就够；正式 A/B 框架（流量切分）不需要
- **prompt 自动优化**（DSPy 这类）：明确不做——破坏 prompt 是工程资产的纪律

---

*已拍板，可启动 Phase 1。*
