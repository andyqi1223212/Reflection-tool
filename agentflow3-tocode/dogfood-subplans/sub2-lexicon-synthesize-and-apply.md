# Subplan 2 · Lexicon Synthesize + Apply

> 母 plan：`~/.cursor/plans/dogfood-feedback-loop-v0_d9ffe369.plan.md`
> **前置**：sub1 必须完成，且 `users/qihaoyu/feedback.jsonl` 至少有 20 行真实 feedback（用户自己 dogfood 一周后才启动）
> **后置**：sub3 (eval_lite trial 重跑) 直接依赖本子 plan 产出的新 lexicon 版本文件

---

## 0. 目标

把用户在 sub1 攒下的 `feedback.jsonl` 喂给 flagship 模型，让它读完后**提一份 lexicon 修改候选**（不直接改 lexicon）。用户在浏览器里 review 每条 patch → accept / reject / 改后 accept → 应用后 bump lexicon 版本号、归档旧版、更新 prompt frontmatter 引用。

**为什么不让 LLM 直接改 lexicon**：lexicon 是 Pipeline B 的 SSOT，错一字就影响所有未来卡风格；必须用户审过才落档。

---

## 1. 前置依赖

- sub1 完成；`tools/feedback_server.py` 已起服务且能 POST/GET feedback
- `users/qihaoyu/feedback.jsonl` 实有数据（≥ 20 行；本子 plan 不负责采集）
- `chains.json` 与 `data/chains.json` 存在；最近 push 卡的 `runs/<id>/b.json` 可读
- DeepSeek API key 已配置（`.env` DEEPSEEK_API_KEY）；`tools/llm_api.py` + `agents_runtime/llm_client.py` 可用
- 用户语言偏好已归档（sub1 Track 0 已做）

---

## 2. 必读上下文

| 文件 | 你为什么要读 |
|---|---|
| [agentflow3-tocode/dogfood-subplans/sub1-feedback-server-and-ui.md](sub1-feedback-server-and-ui.md) §4.1 / §4.2 | feedback.jsonl line schema + server 路由表（你要加新路由） |
| [tools/feedback_server.py](../../tools/feedback_server.py)（sub1 产出） | 学其 routing / jsonl 读写 / fcntl lock 风格，新增路由保持一致 |
| [context/pipeline-b-style-lexicon-v1.md](../../context/pipeline-b-style-lexicon-v1.md) | 当前 lexicon 全文；理解 §0/§1/§2/§3/§4/changelog 结构 |
| [agent第二轮/pipeline-b-style.prompt.md](../../agent第二轮/pipeline-b-style.prompt.md) frontmatter | `inputs.style_lexicon.source` 字段；apply 时要更新这个引用 |
| [agents_runtime/llm_client.py](../../agents_runtime/llm_client.py) | 学其 reasoning model 调用方式（reasoning_effort / extra_body.thinking）|
| [agents_runtime/loader.py](../../agents_runtime/loader.py) | 学其 prompt md 解析方式；你要新建 `_prompts/synthesize-lexicon.prompt.md` |
| [agents_runtime/context_builder.py](../../agents_runtime/context_builder.py) | 学其 build_context；synthesize 可手写 context 不必走 builder |
| [crystallization-prototype/inbox.html](../../crystallization-prototype/inbox.html) + .js + .css | 学其前端风格；新建 `lexicon_review.html` 风格一致 |
| [.cursorrules](../../.cursorrules) Lessons 区 | 项目约定 + 用户语言偏好（sub1 已加）|

---

## 3. 任务清单（覆盖母 plan todos: B1 / B2）

### 3.1 B1 · synthesize_lexicon.py

新建 [agents_runtime/synthesize_lexicon.py](../../agents_runtime/synthesize_lexicon.py)：

CLI：

```bash
./venv/bin/python3 -m agents_runtime.synthesize_lexicon \
    --feedback users/qihaoyu/feedback.jsonl \
    --lexicon context/pipeline-b-style-lexicon-v1.md \
    --out users/qihaoyu/lexicon_proposals/ \
    [--min-feedback 20] \
    [--since 2026-05-15] \
    [--model deepseek-reasoner]
```

逻辑：

1. 读 `feedback.jsonl` 全部行；若 `--since` 过滤；统计总数与 4 维平均分
2. 若 `< --min-feedback` 行：输出 `WARN: 仅 N 条 feedback，建议先攒到 ≥ 20 再 synthesize`，退出非 0
3. 读当前 lexicon 全文 + 提取版本号（从 frontmatter 或文件名 v\d+）
4. 对每条 feedback line：若 `target_type=run` 找 `runs/<run_id>/b.json` 取 final mech/anchor/steps；若 `target_type=card` 从 `data/chains.json` 拿对应卡
5. 装配 context 调 flagship 模型：
   - system = 新建 `agents_runtime/_prompts/synthesize-lexicon.prompt.md` 全文
   - user = JSON: `{feedback_rows: [...], lexicon_current: "<md>", b_outputs: {<run_id>: {mech, anchor, steps}, ...}}`
6. 模型输出 **structured JSON**（不要 markdown patch；理由见 §7 风险 1）：

   ```json
   {
     "base_version": "v1",
     "next_version": "v2",
     "hypotheses": [
       {"id": "h1", "text": "你 4+ 分 anchor 平均字数 8.3，1-2 分平均 14.7 → 短二元结构持续胜出", "evidence_rows": [3, 12, 17]}
     ],
     "patches": [
       {
         "id": "p1",
         "section": "§1",
         "action": "insert_row",
         "anchor_text": "| **抽象正确的废话** | \"重要的是 mindset\"、\"找到自己\" | 删；改成可观察行为 |",
         "position": "after",
         "new_content": "| **过密英文术语 / 黑话堆积** | ... | ... |",
         "hypotheses": ["h1"],
         "evidence_rows": [7]
       },
       {
         "id": "p2",
         "section": "§3 attention 主轴",
         "action": "append",
         "new_content": "- **得失心异步结算** | \"得失心还给昨天的你。\" | [user-feedback#15 score=5]",
         "hypotheses": ["h1"],
         "evidence_rows": [15]
       }
     ],
     "withheld": [
       {"section": "§2 写作规则", "reason": "本批 feedback 仅 3 条涉及，<阈值 5，不敢动"},
       {"section": "§4 刺痛着陆配对", "reason": "本批 feedback 完全没提到"}
     ],
     "meta_stats": {
       "feedback_total": 23,
       "feedback_window": "2026-05-15..2026-05-21",
       "patches_count": 2,
       "evidence_min_per_patch": 1
     }
   }
   ```

7. 写两份文件到 `users/qihaoyu/lexicon_proposals/`：
   - `<ISO_timestamp>_proposal.json`（structured，给 sub3 / apply 用）
   - `<ISO_timestamp>_proposal.md`（人类可读，给 review UI 渲染：把 hypotheses + patches + withheld + meta_stats 渲染成 markdown，每个 patch 显示 anchor_text 上下文 + new_content）

action 枚举（必须支持）：

- `insert_row`：在 anchor_text 这一行 `after` / `before` 插入 new_content（用于表格 / 列表新增）
- `replace_line`：把 anchor_text 整行替换为 new_content
- `append`：在 section 末尾追加 new_content
- `replace_block`：把 anchor_text 起止到 next section heading 之间的内容替换为 new_content（慎用，patch 要写大上下文）

### 3.2 _prompts/synthesize-lexicon.prompt.md

新建 [agents_runtime/_prompts/synthesize-lexicon.prompt.md](../../agents_runtime/_prompts/synthesize-lexicon.prompt.md)：

frontmatter：

```yaml
---
agent_id: synthesize-lexicon
version: v1
model_tier: flagship
single_responsibility: "读 feedback.jsonl + 当前 lexicon + 被打分的 b.json → 输出结构化 patches 候选；不直接改 lexicon"
forbidden_inputs:
  - "agent第二轮/pipeline-b-style.prompt.md（你不调 B，不该读它的内部）"
  - "外部source/*.md（用户原始对话不需要）"
created: 2026-05-21
---
```

正文要点：

- 你的角色：**lexicon 维护者助手**——你不写卡、不评分，只提改 lexicon 的候选
- 输出契约：**严格** §3.1 schema 的 JSON，不要 markdown，不要 ```json fence
- 硬约束：
  - 每个 patch **必须**引用 ≥ 1 条 feedback row（`evidence_rows`）；最好 ≥ 2 条
  - 某 section feedback 涉及 < 3 条 → 放进 `withheld` 不动它
  - hypotheses 必须从数据推（"4+ 分 anchor 字数 X" 这种可量化表述）；不准凭空写"我觉得用户会更喜欢..."
  - patch 的 `anchor_text` **必须**在当前 lexicon 里能字符串匹配到（否则 apply 时找不到位置）
- 内容方向偏好（用户已实证）：
  - 短锚胜过长锚；二元结构胜过转折结构
  - 生活 / 身体 / 关系隐喻胜过 CS / 工程 / 公式
  - 拒杞表新增项要优先（删词比加规则更省 attention）
- **本 prompt 自身**也守用户语言偏好：中英混合 OK，专有名词外用中文，避免黑话堆积

### 3.3 B2 · lexicon_review.html + apply

新建 [crystallization-prototype/lexicon_review.html](../../crystallization-prototype/lexicon_review.html) + `.js` + `.css`：

UI 结构：

- 顶栏：proposal 选择下拉（列 `lexicon_proposals/` 所有 `*.json`，默认选最新）+ 当前 lexicon 版本徽标 + 「应用 N 个采纳」按钮（disabled 直到至少 1 patch 被采纳）
- 主区：左右 split
  - 左：proposal 渲染（hypotheses 卡片 + 每条 patch 卡片 + withheld 折叠区 + meta_stats 角标）
  - 右：当前 lexicon 全文（带 anchor scroll：点左侧 patch 卡，右侧滚到对应位置高亮 anchor_text）
- 每个 patch 卡片含：
  - section / action / hypothesis 引用 / evidence_rows 引用（点击 evidence_rows 弹出该 feedback 行原文 modal）
  - anchor_text 与 new_content（pre 显示）
  - 三按钮：`采纳` / `拒绝` / `改后采纳`（点后展开 textarea 编辑 new_content）
  - 状态徽标：默认未决；采纳 → 绿；拒绝 → 灰；改后采纳 → 黄
- 底栏：`应用 N 个采纳` → 弹确认 modal 「将创建 `pipeline-b-style-lexicon-v<N+1>.md`，归档旧版到 `_archive/lexicon-v<N>-<date>.md`，并更新 prompt frontmatter 引用」→ 确认 → POST → 成功后页面跳到「已落档」状态

**修改** [tools/feedback_server.py](../../tools/feedback_server.py) 加路由：

| Method | Path | 入参 | 出参 |
|---|---|---|---|
| `GET` | `/api/lexicon/current` | - | `{version: "v1", path: "...", content: "<md>"}` |
| `GET` | `/api/lexicon/proposals` | - | `[{ts, filename, patches_count, applied: false/true}, ...]` 倒序 |
| `GET` | `/api/lexicon/proposal/<ts>` | - | `{proposal_json, proposal_md}` |
| `POST` | `/api/lexicon/apply` | body `{proposal_ts, accepted_patches: [{id, action, anchor_text, new_content}], reject_reasons?: {patch_id: reason}}` | `{ok, new_version, new_path, archive_path, prompt_updated: true}` |
| `GET` | `/api/feedback/row?index=N` | feedback.jsonl 0-based 行号 | 整行 JSON（供 evidence_rows modal 用）|

`/api/lexicon/apply` server 实现：

1. 读当前 lexicon
2. 对每个 accepted_patches 按 action 执行字符串 op（用 Python 的 str.replace / 切片）
3. 写 `context/pipeline-b-style-lexicon-v<N+1>.md`（frontmatter `last_synced` 改今天；changelog 末尾追加一段「v<N+1>: applied <K> patches from proposal <ts>」）
4. `mv` 旧 `context/pipeline-b-style-lexicon-v<N>.md` → `context/_archive/lexicon-v<N>-<date>.md`
5. 改 [agent第二轮/pipeline-b-style.prompt.md](../../agent第二轮/pipeline-b-style.prompt.md) frontmatter:
   - `inputs.style_lexicon.source` 字段值改新路径
   - 文件级 `last_iter` 改 ISO 日期 + 一行 reason
   - `version` bump（v2.2 → v2.3）
6. 写一份 apply 记录 `users/qihaoyu/lexicon_proposals/<ts>_applied.json` 包含 accepted_patches 与 reject_reasons（之后 sub3 trial、sub2 下一轮 synthesize 能读到「上次拒了什么 → 别再提」）
7. 调 `runs/_index.py` 刷新（确保 inbox 显示最新）

---

## 4. 输入 / 输出契约

### 4.1 proposal.json schema（严格）

见 §3.1 第 6 步示例；workhorse 实施时把 schema 写入 prompt 内 + 在 synthesize_lexicon.py 里用 `jsonschema` 库验证（如果没装就跳过；不强求新依赖）。

### 4.2 patch action 字符串 op 实现

```python
def apply_patch(lexicon_text: str, patch: dict) -> str:
    section_text = locate_section(lexicon_text, patch["section"])  # 用 § 标题切
    action = patch["action"]
    anchor = patch.get("anchor_text", "")
    new = patch["new_content"]
    if action == "insert_row":
        # 在 anchor 行 after/before 插入
        ...
    elif action == "replace_line":
        return lexicon_text.replace(anchor, new, 1)
    elif action == "append":
        # 在 section 末尾（next ## heading 前）插入
        ...
    elif action == "replace_block":
        # anchor 开始到下一 § 标题之间替换
        ...
    else:
        raise ValueError(f"unknown action: {action}")
```

每个 apply 后**重新读 anchor 验证生效**；若失败回滚整次 apply（不留半成品 lexicon）。

### 4.3 lexicon 文件 / 归档命名

- 当前活跃 lexicon：`context/pipeline-b-style-lexicon-v<N>.md`（N 单调递增）
- 归档：`context/_archive/lexicon-v<N>-<YYYY-MM-DD>.md`（保留原 frontmatter）
- prompt 引用：`agent第二轮/pipeline-b-style.prompt.md` frontmatter 唯一权威；apply 必须改

---

## 5. 验收清单

- [ ] `./venv/bin/python3 -m agents_runtime.synthesize_lexicon --feedback users/qihaoyu/feedback.jsonl --lexicon context/pipeline-b-style-lexicon-v1.md` 能跑通
- [ ] 输出两份文件：`<ts>_proposal.json` + `<ts>_proposal.md`
- [ ] proposal.json 通过 schema 校验（patches 数组每条都有 id/section/action/anchor_text/new_content/hypotheses/evidence_rows）
- [ ] 每条 patch 的 anchor_text 都能在当前 lexicon 字符串匹配（dry-run 输出验证）
- [ ] `< --min-feedback` 时退出非 0 且打印 WARN
- [ ] `http://localhost:8765/lexicon_review.html` 能渲染最新 proposal
- [ ] 点 evidence_rows 数字弹出对应 feedback 原文 modal
- [ ] 采纳 / 拒绝 / 改后采纳 按钮状态切换正确
- [ ] 点「应用 N 个采纳」→ 弹确认 → 确认后 server 端：
  - [ ] 新建 `context/pipeline-b-style-lexicon-v2.md`（版本号正确）
  - [ ] 旧 v1 已 mv 到 `context/_archive/lexicon-v1-<date>.md`
  - [ ] `agent第二轮/pipeline-b-style.prompt.md` frontmatter 引用已改 + version bump + last_iter 改今天
  - [ ] `users/qihaoyu/lexicon_proposals/<ts>_applied.json` 写入
- [ ] apply 后页面状态变「已落档」并显示新版本号
- [ ] apply 失败任何一步都回滚（lexicon 文件不留半成品）
- [ ] 跑 `./venv/bin/python3 -m agents_runtime.run_b ...`（任意已有 a.json）验证 B 能正常加载新 lexicon
- [ ] 所有代码 / 注释 / commit message 中文为主

---

## 6. 范围边界（绝对不做）

- ❌ **不**让 LLM 直接改 lexicon（必须经用户 review）
- ❌ **不**实现 patch 的 markdown unified diff 解析（用 structured JSON action 避免脆弱）
- ❌ **不**自动定期跑 synthesize（手动 CLI 触发；cron 留给以后）
- ❌ **不**实现 sub3 的 trial 重跑 UI（本子 plan 只到 apply 结束）
- ❌ **不**实现回滚 lexicon 版本到旧的 UI（apply 后想反悔只能手动 mv archive 回去 + 改 prompt frontmatter；用户已知）
- ❌ **不**碰 sub4 的 synthesis_review（C 模式复制时间到 sub4 再做）
- ❌ **不**动 `chains.json` / 已 merged 卡（lexicon 改了只影响未来卡）

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM 输出 markdown patch 易脆弱（unified diff 行号偏移 / 缩进差异） | **改用 structured JSON action** + anchor_text 字符串匹配 + apply 后验证 |
| LLM 写的 anchor_text 在 lexicon 找不到（hallucinate） | synthesize 时 prompt 强约束 anchor_text 必须字符串匹配；synthesize_lexicon.py 收到响应后预校验，找不到的 patch 自动放进 withheld + WARN |
| 早期 feedback 少 (< 20)，LLM 强行 propose 会噪声大 | `--min-feedback` 阈值；少于阈值退出非 0 |
| LLM 给出违反「用户语言偏好」的 lexicon 候选（堆英文） | synthesize prompt 里明示该规则；review UI 默认折叠，用户人审是最后防线 |
| apply 时 prompt frontmatter 改错破坏整个 Pipeline B | apply 前先 backup `pipeline-b-style.prompt.md` 到 `.bak`；apply 失败 mv 回 |
| 同时多个 review tab apply 冲突 | server 端用全局锁；一次只允许一个 apply pending |
| proposal 文件多了找不到 | UI 下拉列表按 ts 倒序；每个 proposal 标注 applied/pending 状态 |

---

## 8. 实施建议

1. **先写 prompt md**（_prompts/synthesize-lexicon.prompt.md）——决定输入输出契约
2. **再写 synthesize_lexicon.py 骨架**（不调 LLM，先 mock 一份 proposal.json + .md 让前端可开发）
3. **server 加 5 个新路由**（先 GET，后 POST apply）
4. **前端 lexicon_review.html 主区 + 提交按钮**（先用 mock 数据跑通交互）
5. **接通真 LLM**（synthesize_lexicon.py 实跑一次，看输出质量）
6. **apply 实现**（最后做；最危险，先 dry-run 打印 diff 再真写）
7. **端到端验证**：跑 run_b 用新 lexicon 看 B 没崩

### 关键代码线索

**调 flagship 模型**（参考 [agents_runtime/llm_client.py](../../agents_runtime/llm_client.py)）：

```python
from agents_runtime.llm_client import call_llm
response = call_llm(
    system_prompt=prompt_md_body,
    user_content=json.dumps({...}, ensure_ascii=False, indent=2),
    model_tier="flagship",
    response_format="json",  # 强制 JSON
)
```

**locate_section**（按 § 标题切）：

```python
import re
def locate_section_bounds(text: str, section_label: str) -> tuple[int, int]:
    # section_label 如 "§1" 或 "§3 attention 主轴"
    pat = re.compile(rf"^##+ {re.escape(section_label)}", re.M)
    m = pat.search(text)
    if not m:
        raise ValueError(f"section not found: {section_label}")
    start = m.start()
    next_pat = re.compile(r"^##+ ", re.M)
    m2 = next_pat.search(text, m.end())
    end = m2.start() if m2 else len(text)
    return start, end
```

**bump prompt frontmatter**：用现有 [agents_runtime/loader.py](../../agents_runtime/loader.py) 的解析能力（如其支持）或简单字符串替换 + YAML re-dump（PyYAML stdlib 不带；用 ruamel.yaml 或简单 sed）。**优先简单字符串替换**：找到 `source: "context/pipeline-b-style-lexicon-v1.md"` 替换为新路径；找到 `last_iter:` 行整行替换。

---

## 9. workhorse 完成后回报模板

参见 sub1 §9。额外强调：apply 之后**必须**跑一次 `./venv/bin/python3 -m agents_runtime.run_b ...`（找任一已有 run 复现）验证 B 没崩；崩了立刻回滚 lexicon。
