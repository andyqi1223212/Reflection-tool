# Subplan 4 · Synthesis 自进化（Track C）

> 母 plan：`~/.cursor/plans/dogfood-feedback-loop-v0_d9ffe369.plan.md`
> **前置**：sub1 完成；sub2 完成（本子 plan 复用 sub2 的 apply 工具函数与 review UI 模式）
> **可与 sub3 并行**

---

## 0. 目标

把 sub2 的「propose-review-apply」工作流复制到另一个 sink：[context/raw-questions-synthesis.md](../../context/raw-questions-synthesis.md) 的 §2 童年时间线 / §5 用户语言肌理 / §6 已被打动过的素材库。

让 Pipeline A 的"用户记忆库"自己积累——每次 push 成功后中间产物自然进 `runs/<id>/`；周期 synthesize 一次，patch 候选 → 用户审 → apply 落 synthesis.md → A 下次跑就读到最新版。

**为什么用 synthesis 而不是 lexicon**：lexicon 是 B 的风格规则（文字怎么写）；synthesis 是 A 的用户记忆（用户是谁、他被什么打动）。两个 SSOT 不要混。

---

## 1. 前置依赖

- sub1 完成；feedback_server 跑得起来
- sub2 完成；`agents_runtime/synthesize_lexicon.py` + apply 模式可参考复用（建议把 apply 的 markdown patch 工具函数 refactor 进 `agents_runtime/_patch_utils.py` 供两者共用——本子 plan 范围内可改）
- `runs/` 至少有 5 个 status=succeeded 的 run
- `users/qihaoyu/feedback.jsonl` 可读（synthesis 也会用 feedback 作为信号源之一）

---

## 2. 必读上下文

| 文件 | 你为什么要读 |
|---|---|
| [sub2-lexicon-synthesize-and-apply.md](sub2-lexicon-synthesize-and-apply.md) 全文 | **核心参考**——本子 plan 80% 是它的模式复制 |
| [agents_runtime/synthesize_lexicon.py](../../agents_runtime/synthesize_lexicon.py)（sub2 产出） | 你的新脚本结构应基本一致 |
| [agents_runtime/_prompts/synthesize-lexicon.prompt.md](../../agents_runtime/_prompts/synthesize-lexicon.prompt.md)（sub2 产出） | 你的新 prompt 应同结构（只是任务对象不同）|
| [crystallization-prototype/lexicon_review.html](../../crystallization-prototype/lexicon_review.html)（sub2 产出） | 你要复用其大部分 dom / 样式；新建 `synthesis_review.html` 或加 tab |
| [context/raw-questions-synthesis.md](../../context/raw-questions-synthesis.md) | 当前 synthesis 全文；理解 §2 / §5 / §6 章节结构 |
| [agent第二轮/pipeline-a-diagnose.prompt.md](../../agent第二轮/pipeline-a-diagnose.prompt.md) frontmatter | `inputs.synthesis_excerpts.sections` 已切 §2/§5/§6；apply 后 A 自动读新版 |
| `runs/<id>/`（任一） | 看 question_md / a.json / b.json / manifest.json 真实格式 |

---

## 3. 任务清单（覆盖母 plan todos: C1 / C2）

### 3.1 _patch_utils.py（建议先 refactor）

把 sub2 `synthesize_lexicon.py` 里的 markdown patch apply 工具函数（locate_section / apply_patch 等）抽进 [agents_runtime/_patch_utils.py](../../agents_runtime/_patch_utils.py)：

- `locate_section_bounds(text, section_label) -> (start, end)`
- `apply_patch(text, patch_dict) -> str`（支持 insert_row / replace_line / append / replace_block 4 action）
- `validate_patches(text, patches) -> list[str]`（返回 anchor_text 找不到的 patch id 列表）
- `apply_patches_safely(text, patches) -> tuple[str, list[str]]`（全部成功才返回新 text；任一失败回滚并返回 [失败 id]）

sub2 的 `synthesize_lexicon.py` 改成 import 这些工具。**本子 plan 可以做这个 refactor**（属于"修复母 plan 没明说的复用债"）。

### 3.2 C1 · synthesize_user_memory.py

新建 [agents_runtime/synthesize_user_memory.py](../../agents_runtime/synthesize_user_memory.py)：

CLI：

```bash
./venv/bin/python3 -m agents_runtime.synthesize_user_memory \
    --synthesis context/raw-questions-synthesis.md \
    --runs-dir runs/ \
    --feedback users/qihaoyu/feedback.jsonl \
    --since 2026-05-15 \
    --out users/qihaoyu/synthesis_proposals/ \
    [--min-runs 5] \
    [--model deepseek-reasoner]
```

逻辑：

1. 扫 `runs/` 下所有 `manifest.json` status=succeeded 且 `created_at >= --since` 的 run
2. 每个 run 收集：`question_md` 全文 + `a.json` 的 patterns/axis/route + `b.json` 的 mech/anchor + feedback for this run
3. 读当前 `raw-questions-synthesis.md` 全文
4. 装配 context 调 flagship：
   - system = 新建 `agents_runtime/_prompts/synthesize-user-memory.prompt.md`
   - user = JSON: `{recent_runs: [...], synthesis_current: "<md>", feedback_signals: [...]}`
5. 模型输出**与 sub2 结构同形** structured JSON（差异：section 标签是 §2 / §5 / §6 等中文章节）：

   ```json
   {
     "base_path": "context/raw-questions-synthesis.md",
     "last_synced_was": "2026-05-08",
     "hypotheses": [
       {"id": "h1", "text": "最近 5 个 run 中 3 个 axis=attention，且都涉及『睡眠刷新』变体 → §5 用户语言肌理需新增『刷新动作』作为高频触发动词", "evidence_runs": ["2026-05-21_觉醒_0f898d", "2026-05-19_xxx"]}
     ],
     "patches": [
       {
         "id": "p1",
         "section": "§5 用户语言肌理",
         "action": "append",
         "new_content": "- **刷新动作家族**：用户在 attention 主轴里反复用『刷新』『往下拉』『再看一眼』这组动作隐喻表达控制焦虑；写晶体卡 trigger 可优先用这组词。",
         "hypotheses": ["h1"],
         "evidence_runs": ["2026-05-21_觉醒_0f898d", "2026-05-19_xxx"]
       },
       {
         "id": "p2",
         "section": "§6 已被打动过的素材库",
         "action": "insert_row",
         "anchor_text": "| 类型 | 句 | 来源 / 评分 |",
         "position": "section_table_end",
         "new_content": "| anchor | \"紧的脑子哄不松。\" | runs/2026-05-21_觉醒_0f898d · feedback#3 score=5 |"
       }
     ],
     "withheld": [
       {"section": "§2 童年时间线", "reason": "近期 runs 无新童年事件提及"}
     ],
     "meta_stats": {
       "runs_window_count": 5,
       "feedback_used_count": 12,
       "patches_count": 2
     }
   }
   ```

6. 写 `users/qihaoyu/synthesis_proposals/<ts>_proposal.json` + `<ts>_proposal.md`

### 3.3 _prompts/synthesize-user-memory.prompt.md

新建 [agents_runtime/_prompts/synthesize-user-memory.prompt.md](../../agents_runtime/_prompts/synthesize-user-memory.prompt.md)：

frontmatter（参考 sub2 同款）：

```yaml
---
agent_id: synthesize-user-memory
version: v1
model_tier: flagship
single_responsibility: "读最近 N 个 run + feedback + 当前 synthesis.md → 输出 §2/§5/§6 patches 候选"
forbidden_inputs:
  - "agent第二轮/pipeline-a-diagnose.prompt.md（你不是 A，不必读 A 的内部指令）"
  - "agent第二轮/pipeline-b-style.prompt.md（B 同理）"
created: 2026-05-21
---
```

正文要点：

- 你的角色：**用户记忆库维护者**——你不诊断、不写卡，只 propose synthesis.md 怎么补
- 限定区域：**只动 §2 / §5 / §6**；§1 沉淀摘要、§3 迭代脉络、§4 执行清单、§7 扩展阅读、§8 实证归纳 由人类亲自维护，你**禁止 propose**
- 硬约束：
  - 每个 patch 必须引用 ≥ 2 个 run_id 作为 evidence（feedback row 也可计入）
  - 涉及 < 3 个 run 的 hypothesis 放 withheld
  - patch new_content 要符合 synthesis.md 现有写作风格（短叙事 + 引用具体 run 或 feedback row）
  - **不**重复 §5 / §6 已有项；先用 anchor_text 字符串匹配验证
- 用户语言偏好：中英混合、专有名词外用中文

### 3.4 C2 · synthesis review UI（复用 lexicon_review）

**两种方案二选一**（workhorse 自决）：

**方案 A**：复用 lexicon_review.html 加 Tab 3「Synthesis Review」

- 优点：UI 一处维护
- 缺点：Tab 数变多

**方案 B**：新建独立 [crystallization-prototype/synthesis_review.html](../../crystallization-prototype/synthesis_review.html)

- 优点：路径清晰
- 缺点：复制大块 dom

**推荐方案 A**（更符合用户「少建文件」偏好），但若 lexicon_review.js 已经很大（>500 行）则用方案 B。

复用 sub2 的 patch 卡片组件 / 接受拒绝按钮 / apply 确认 modal——仅 fetch 端点不同。

**修改** [tools/feedback_server.py](../../tools/feedback_server.py) 加路由（与 sub2 lexicon 路由同形）：

| Method | Path | 入参 | 出参 |
|---|---|---|---|
| `GET` | `/api/synthesis/current` | - | `{path, content, last_synced}` |
| `GET` | `/api/synthesis/proposals` | - | 列出 `synthesis_proposals/*.json` |
| `GET` | `/api/synthesis/proposal/<ts>` | - | `{proposal_json, proposal_md}` |
| `POST` | `/api/synthesis/apply` | body `{proposal_ts, accepted_patches: [...]}` | `{ok, archive_path, last_synced_updated_to}` |

`/api/synthesis/apply` 实现：

1. 备份 `raw-questions-synthesis.md` → `context/_archive/synthesis-<date>.md`
2. apply patches（复用 sub2 的 `_patch_utils.apply_patches_safely`）
3. 改 synthesis.md 末尾「文档版本：YYYY-MM-DD」行为今天
4. 写 `users/qihaoyu/synthesis_proposals/<ts>_applied.json`
5. **不需要**改 `pipeline-a-diagnose.prompt.md` 的 source 引用——同一文件路径，只是内容变了；A 下次跑自动读最新

---

## 4. 输入 / 输出契约

### 4.1 proposal.json schema

见 §3.2 第 5 步。与 sub2 的差异：

- `base_version` → `base_path` + `last_synced_was`
- `evidence_rows` → `evidence_runs`（也可带 `evidence_feedback_rows`）
- `next_version` 字段去掉（synthesis 不 bump 版本号，只 bump `文档版本：` 日期）

### 4.2 文件落点

- 新建：`agents_runtime/_patch_utils.py`（refactor 自 sub2）
- 新建：`agents_runtime/synthesize_user_memory.py`
- 新建：`agents_runtime/_prompts/synthesize-user-memory.prompt.md`
- 新建：`users/qihaoyu/synthesis_proposals/.gitkeep`
- 新建或修改：`crystallization-prototype/lexicon_review.html|.js|.css` （方案 A）或 `synthesis_review.html|.js|.css`（方案 B）
- 修改：`tools/feedback_server.py` 加 4 路由
- 修改：`context/raw-questions-synthesis.md`（每次 apply 后）
- 写入：`context/_archive/synthesis-<date>.md`

---

## 5. 验收清单

- [ ] `_patch_utils.py` 抽出且 sub2 的 `synthesize_lexicon.py` import 后 sub2 测试仍跑通
- [ ] `./venv/bin/python3 -m agents_runtime.synthesize_user_memory --since 2026-05-15` 能跑通
- [ ] 输出 `<ts>_proposal.json` + `<ts>_proposal.md`，schema 正确
- [ ] 每个 patch 引用 ≥ 2 个 evidence（runs 或 feedback rows）
- [ ] propose 只动 §2/§5/§6；§1/§3/§4/§7/§8 任何 patch → schema 验证失败
- [ ] `http://localhost:8765/lexicon_review.html` Tab 3（或新页面）能渲染最新 synthesis proposal
- [ ] apply 后：
  - [ ] `raw-questions-synthesis.md` 内容已更新
  - [ ] `_archive/synthesis-<date>.md` 备份存在
  - [ ] 文档末尾「文档版本」日期改今天
  - [ ] `synthesis_proposals/<ts>_applied.json` 写入
- [ ] apply 后跑 `./venv/bin/python3 -m agents_runtime.run_a "外部source/<某题>.md"` 验证 A 能正常加载新 synthesis（不崩 + 引用 §5/§6 新内容时显式 cite）
- [ ] 一次 apply 失败（手工破坏 anchor_text 验证）→ synthesis.md 不变；server 返回 4xx + 失败 patch id 列表
- [ ] 所有代码 / 注释 / commit message 中文为主

---

## 6. 范围边界（绝对不做）

- ❌ **不**让 LLM propose §1 / §3 / §4 / §7 / §8（这些是人类维护区）
- ❌ **不**自动 cron 定期跑 synthesize（手动 CLI；用户自决何时积累够了）
- ❌ **不**改 `pipeline-a-diagnose.prompt.md` 的 inputs schema（synthesis 文件路径不变，只是内容变）
- ❌ **不**实现 synthesis trial 重跑（A 不像 B 那样需要 trial——synthesis 只是给 A 多一些参考，影响不剧烈；若真要测可手动跑一题对比，不进 sub plan）
- ❌ **不**碰 lexicon 相关任何文件（那是 sub2/sub3 的事；本子 plan 只动 synthesis sink）
- ❌ **不**触碰 `chains.json` / 已 merged 卡

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM propose 涉及禁区 §1/§3/§4/§7/§8 | prompt 硬约束 + 后端 schema 验证（section 字段白名单）|
| synthesis.md apply 改坏导致 A 下次崩 | apply 前备份 `.bak`；apply 后立即跑一次 `run_a` 冒烟测试；崩了 mv 回 |
| 同时 propose lexicon 与 synthesis 容易混淆 | UI 上两 tab 显著区分；apply 端点路径区分 `/api/lexicon/apply` vs `/api/synthesis/apply` |
| evidence_runs 引用已被删 / 移走的 run | propose 时验证 run 目录仍存在；apply 时不再验证（已经写进 patch 就当人话）|
| §6 表格越追越长，难维护 | 不在本轮处理；用户人审时可手动 reject 老旧 row 的 propose；以后增 `--prune-stale` 选项 |

---

## 8. 实施建议

1. **先 refactor _patch_utils.py**（拉出 sub2 的工具函数；跑一遍 sub2 测试确认不破坏）
2. **写 prompt md** + **synthesize_user_memory.py 骨架**（mock LLM 输出跑通文件落点）
3. **server 加 4 路由**（与 sub2 lexicon 路由完全镜像）
4. **UI 复用**（方案 A：加 Tab 3 复用 patch 卡片组件；方案 B：新建独立页面 + 复制 css）
5. **接通真 LLM**
6. **apply 端到端 + 冒烟 run_a**

### 关键代码线索

**section 白名单验证**：

```python
ALLOWED_SECTIONS = {"§2 用户原文反馈归档", "§5 禁忌 ↔ 替代", "§6 Pattern tags"}
# 注：以 raw-questions-synthesis.md 实际 § 标题为准；先 grep 看清楚

for patch in proposal["patches"]:
    if patch["section"] not in ALLOWED_SECTIONS:
        raise ValueError(f"section {patch['section']} 不在白名单")
```

注：**先实读 [context/raw-questions-synthesis.md](../../context/raw-questions-synthesis.md) 确认真实 § 标题字面**——母 plan 写"§2 / §5 / §6"是按 pipeline-a frontmatter 的引用顺序；实际 markdown 章节名要以文件为准。

---

## 9. workhorse 完成后回报模板

参见 sub1 §9。额外强调：refactor `_patch_utils.py` 不能破坏 sub2；apply 后必须跑一次 `run_a` 冒烟验证 A 不崩。
