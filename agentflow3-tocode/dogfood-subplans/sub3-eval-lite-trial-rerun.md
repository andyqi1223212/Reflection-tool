# Subplan 3 · Eval-lite Trial 重跑

> 母 plan：`~/.cursor/plans/dogfood-feedback-loop-v0_d9ffe369.plan.md`
> **前置**：sub2 完成，且至少跑过一次 lexicon apply（已有 `pipeline-b-style-lexicon-v2.md`）
> **后置**：sub5 blog 大纲会引用本子 plan 产出的 diff 截图作为证据

---

## 0. 目标

让用户**批量验证**新 lexicon 的真实效果——选 3-5 张已 push 卡，复用其 `a.json`（省 token），用新 lexicon 重跑 b 阶段，把新旧 b.json 的 mech/anchor/steps 并排显示，用户单卡 / 整体 accept 或 reject。

accept 隐式回写 feedback（score=5 + tag），下次 sub2 synthesize 时这条新信号成为燃料——**lexicon 演化闭环就此形成**。

**为什么这不是「真 eval」**：没有固定 baseline、没有自动评分、没有 regression alert——它是「人审 diff」。但它**就是当前 taste 涌现阶段最合适的工具**：让用户看见 lexicon 改动的具体后果，而不是事后猜。

---

## 1. 前置依赖

- sub1 + sub2 完成
- `context/pipeline-b-style-lexicon-v2.md`（或更高版本）存在
- `agents_runtime/run_b` 可调用；`runs/<id>/a.json` 与 `runs/<id>/b.json`（旧）存在多张
- `data/chains.json` 与 existing_card 抽取逻辑正常（route=update 卡需要 existing_card_json）

---

## 2. 必读上下文

| 文件 | 你为什么要读 |
|---|---|
| [sub1-feedback-server-and-ui.md](sub1-feedback-server-and-ui.md) §4.1 | feedback line schema（你要隐式回写）|
| [sub2-lexicon-synthesize-and-apply.md](sub2-lexicon-synthesize-and-apply.md) §4.3 | lexicon 文件命名约定（你要按版本号找 lexicon 文件）|
| [agents_runtime/agents.py](../../agents_runtime/agents.py) | `run_b` 签名；你可能要扩展支持 `lexicon_path` override |
| [agents_runtime/orchestrate.py](../../agents_runtime/orchestrate.py) | 学其如何串 a → b（你只重跑 b，复用 a.json）|
| [agent第二轮/pipeline-b-style.prompt.md](../../agent第二轮/pipeline-b-style.prompt.md) | frontmatter 里 `inputs.style_lexicon.source`——run_b 默认读这里；你的 override 要绕过它 |
| [runs/2026-05-21_觉醒_0f898d/](../../runs/) 任一目录 | 看 a.json / b.json 真实格式 |
| [data/chains.json](../../data/chains.json) | 找 existing_card 用 |
| [tools/feedback_server.py](../../tools/feedback_server.py)（sub1+sub2 演进版本）| 加新路由保持风格一致 |
| [crystallization-prototype/lexicon_review.html](../../crystallization-prototype/lexicon_review.html)（sub2 产出）| 加 trial tab |

---

## 3. 任务清单（覆盖母 plan todos: B3 / B4）

### 3.1 B3 · eval_lite.py

新建 [agents_runtime/eval_lite.py](../../agents_runtime/eval_lite.py)：

CLI：

```bash
./venv/bin/python3 -m agents_runtime.eval_lite \
    --lexicon-version 2 \
    --pick last5_accepted \
    [--run-ids 2026-05-21_xxx,2026-05-19_yyy] \
    [--out eval/lexicon_trials/]
```

`--pick` 枚举：

- `last5_accepted`：从 `chains.json` 按 `created_at` desc 取最近 5 张（默认）
- `last5_pushed`：从 `runs/` 按 manifest.status=succeeded 取最近 5 个 run_id
- `judge_top5`：从 manifest 里 judge.overall_score top 5
- 用 `--run-ids` 显式指定逗号分隔列表（覆盖 --pick）

逻辑：

1. 解析 `--lexicon-version N` → 定位 `context/pipeline-b-style-lexicon-v<N>.md`（不存在退出非 0）
2. 按 `--pick` / `--run-ids` 拿 run_id 列表
3. 对每个 run_id：
   - 读 `runs/<run_id>/a.json` → `a_draft`
   - 读 `runs/<run_id>/b.json` → `b_old`（拷贝到 trial 目录留存）
   - 若 a_draft.route == 'update'：从 `data/chains.json` 抽 `existing_card_json`
   - 调 `run_b(a_draft, existing_card=..., lexicon_path=<v<N> 路径>)` → `b_new`
   - 写到 `eval/lexicon_trials/v<N>/<run_id>/`：
     - `b_old.json`（拷贝）
     - `b_new.json`（新跑）
     - `diff.md`（mech / anchor / micro_steps 三段并排 markdown）
     - `meta.json`（run_id, lexicon_version, ts, route, axis, source_chain_id_if_any）
4. 汇总写 `eval/lexicon_trials/v<N>/summary.md`：每张卡一行表格（id / title / route / mech 字数 旧→新 / anchor 字数 旧→新 / steps 数 旧→新 / 主要变化一句话）

需要扩展 [agents_runtime/agents.py](../../agents_runtime/agents.py) 的 `run_b`：

- 新增可选参数 `lexicon_path: str | None = None`
- 实现：若给了 lexicon_path，build_context 时把 `style_lexicon` input 的 source 临时改成这个路径
- **不影响**默认行为（None 时仍读 prompt frontmatter 的 source）

### 3.2 B4 · lexicon_review.html 加 trial tab

修改 [crystallization-prototype/lexicon_review.html](../../crystallization-prototype/lexicon_review.html)：

顶部加 tab 切换：

- **Tab 1：Proposal Review**（sub2 已实现，保持不变）
- **Tab 2：Trial Diff**（本子 plan 新加）

Trial tab 内容：

- 顶栏：lexicon version 下拉（列 `eval/lexicon_trials/` 所有 `v*` 子目录）+ pick 策略下拉 + 「跑 trial」按钮（点后 spinner + 调 POST /api/eval_lite/run）
- 列表区：渲染 `summary.md` 表格；每行可点展开
- 展开后：左右 split
  - 左：b_old（mech / anchor / micro_steps 三段，pre 显示，灰底）
  - 右：b_new（同三段，白底，diff 高亮变化字）
  - 底部三按钮：`👍 单卡 accept` / `👎 单卡 reject` / `📝 写 feedback`（弹小 modal 选分 + freeform，提交 = sub1 同款 POST /api/feedback）
- 底栏：
  - `整体 accept N 张 win` 按钮：把所有标 win 的卡批量隐式回写 feedback
  - `整体 reject 回滚 lexicon` 按钮：弹确认 → 提示「本 v0 不实现自动回滚，请手动 mv archive 回复并改 prompt frontmatter；或直接走 sub2 下一轮 propose 修复」（这是已知边界）

**修改** [tools/feedback_server.py](../../tools/feedback_server.py) 加路由：

| Method | Path | 入参 | 出参 |
|---|---|---|---|
| `GET` | `/api/eval_lite/versions` | - | `[{version: 2, trial_count: 5, ts}, ...]` |
| `GET` | `/api/eval_lite/trials?version=N` | - | summary.md 解析后的 JSON list |
| `GET` | `/api/eval_lite/trial/<version>/<run_id>` | - | `{meta, b_old, b_new, diff_md}` |
| `POST` | `/api/eval_lite/run` | body `{lexicon_version, pick, run_ids?}` | 异步 job ID 或同步等完成返回 `{summary, errors}` |
| `POST` | `/api/eval_lite/accept` | body `{lexicon_version, run_id, decision: "win"|"lose"|"skip", scores?, freeform?}` | 写 feedback line → `{ok, feedback_line_index}` |

POST `/api/eval_lite/run` 实现建议：

- 直接 subprocess 调 `python3 -m agents_runtime.eval_lite --lexicon-version N --pick ...`
- 同步等结果（5 张卡 × 调 LLM 大概 1-2 分钟，可接受）
- 返回 stdout 末尾的 summary 路径

POST `/api/eval_lite/accept` 隐式回写 feedback line：

```json
{
  "ts": "<now>",
  "uid": "qihaoyu",
  "target_type": "trial",
  "target_id": "v2/2026-05-21_觉醒_0f898d",
  "stage_focus": "b",
  "scores": {"overall": 5 if decision=="win" else 1},
  "freeform": "<freeform if provided else '(trial decision: <win|lose>)'>",
  "tags": ["lexicon-v2-win" if win else "lexicon-v2-lose"]
}
```

新增 target_type 枚举：`"trial"`（sub1 schema 要扩展，向后兼容；旧 row 仍合法）

---

## 4. 输入 / 输出契约

### 4.1 eval/lexicon_trials/ 目录结构

```
eval/
└── lexicon_trials/
    └── v2/
        ├── summary.md
        ├── meta.json     # {lexicon_version: 2, ts, pick, run_ids}
        ├── 2026-05-21_觉醒_0f898d/
        │   ├── meta.json
        │   ├── b_old.json
        │   ├── b_new.json
        │   └── diff.md
        └── 2026-05-19_球场垃圾话应对策略_182433/
            ├── ...
```

### 4.2 diff.md 格式

```markdown
# Trial Diff · IC-026 · 觉醒 · route=meta · axis=attention

> lexicon: v1 → v2 (apply ts 2026-05-21T15:00:00)
> trial ts: 2026-05-22T10:00:00

## mechanism

### v1 (旧)
> 你以为自己在收回控制感……（字数 142）

### v2 (新)
> 你不是在控制睡眠，是在用紧的脑子哄松的脑子……（字数 118）

**diff 标记**：v2 删了 "刷新机制" 这个 CS 词；新 anchor 短 24 字。

## anchor
| 旧 (v1) | 新 (v2) |
|---------|---------|
| 我在错的轨道上努力。 | 紧的脑子哄不松。 |

## micro_steps
| # | 旧 (v1) | 新 (v2) |
|---|---------|---------|
| 1 | ... | ... |
| 2 | ... | ... |
```

### 4.3 run_b 扩展签名

```python
def run_b(
    a_draft: dict,
    existing_card: dict | None = None,
    fewshot: list[str] | None = None,
    lexicon_path: str | None = None,  # ← 新增
) -> dict:
    ...
```

向后兼容：lexicon_path=None 时走原逻辑（读 prompt frontmatter）。

---

## 5. 验收清单

- [ ] `./venv/bin/python3 -m agents_runtime.eval_lite --lexicon-version 2 --pick last5_accepted` 跑通
- [ ] `eval/lexicon_trials/v2/` 下有 5 个 run_id 子目录 + summary.md + meta.json
- [ ] 每个 run_id 目录有 b_old.json + b_new.json + diff.md
- [ ] diff.md 显示 mech / anchor / steps 旧 vs 新对比
- [ ] `run_b(lexicon_path=...)` override 生效（验证：手动指一个完全不同的 lexicon → b 输出风格变化）
- [ ] `run_b(lexicon_path=None)` 仍按原 prompt frontmatter 读 lexicon（向后兼容）
- [ ] `http://localhost:8765/lexicon_review.html` Tab 2 可见 v2 trial 列表
- [ ] 展开某行可看到 left/right split + diff 高亮
- [ ] 「单卡 accept」按钮 → `feedback.jsonl` 多一行 target_type=trial + tag=lexicon-v2-win
- [ ] 「跑 trial」按钮 → 后端 subprocess 启动 → 等待 → 返回 → 前端刷新列表
- [ ] 一张 route=update 的卡能正确读 existing_card 跑通
- [ ] route=meta / route=new 卡也能跑通（无 existing_card）
- [ ] 跑完 trial 后 `feedback.jsonl` 新增 row 能被 sub2 的 synthesize_lexicon 正常读到（下次 propose 把 lexicon-v2 win/lose 当证据）

---

## 6. 范围边界（绝对不做）

- ❌ **不**实现自动回滚 lexicon（用户已知；UI 提示手动方式）
- ❌ **不**改 `chains.json`（trial 是观察工具，不影响真卡库）
- ❌ **不**重跑 a 阶段（复用 a.json 省 token；本子 plan 范围内 a 必须是给定的）
- ❌ **不**重跑 judge（trial 只看 b 风格变化；judge 评分轴不在本轮关注）
- ❌ **不**实现"批量 reject 自动生成 sub2 next proposal"（保持人为节奏；用户决定何时 synthesize）
- ❌ **不**做 regression alert（这是真 eval 的事；本子 plan 是 diff 工具，不是 alarm）
- ❌ **不**碰 sub4 的 synthesis trial（synthesis 不需要 trial：propose-review-apply 直接生效，没有"重跑"成本）

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| run_b 调用 LLM 耗时；5 张卡 1-2 分钟用户可能以为页面卡 | UI spinner + 后端逐张完成时 SSE 或轮询；最简版同步等也可接受 |
| existing_card 抽取错（chains.json 找不到对应 IC） | 跳过该 run，summary.md 注明 SKIP + 原因 |
| trial b_new 不合 schema（LLM 输出格式错）| eval_lite.py 捕获异常，写 `<run_id>/error.json` + 在 summary 标 FAIL |
| 同名 v 目录重复跑覆盖旧 trial | 默认覆盖（用户重新评估即可）；若想保留：建议加 `--ts-suffix` 选项 |
| 用户跑 trial 后忘了 accept/reject 就关页面 → 下次 sub2 没新 feedback | 设计上不阻塞；用户自然会回来看；不强提醒 |
| lexicon_path override 实现破坏 forbidden_inputs lint | override 后路径仍在 repo 内、不进 forbidden 范围；测试一次确认 |

---

## 8. 实施建议

1. **先扩展 run_b**（最小改动：lexicon_path 参数 + build_context 内临时覆盖 source）→ 单元跑通
2. **写 eval_lite.py 骨架**（CLI 参数解析 + run_id 选择 + 调 run_b + 写 b_new.json）
3. **diff.md 生成**（最简版：三段直接 pre 显示；后续可加 difflib HTML diff）
4. **summary.md 生成**（每 run 一行 markdown 表）
5. **server 加 5 路由**（GET 先，POST run 后）
6. **lexicon_review.html Tab 2**（先 mock 数据跑通交互）
7. **接通真后端**（点跑 trial 实跑）
8. **accept/reject 隐式回写 feedback**（用 sub1 已有 POST /api/feedback 复用）
9. **端到端**：跑一轮 sub2 apply → sub3 跑 trial → accept 3 张 → 看 `feedback.jsonl` 多 3 行 → 跑 sub2 next propose → 验证新 propose 引用了 trial 的 feedback rows

### 关键代码线索

**diff 高亮**：用 Python `difflib.HtmlDiff` 或前端 `diff` npm 库都重；最简：用 `difflib.unified_diff` 拿 line-level diff，前端用 `<ins>` / `<del>` 标签包变化部分。

**run_b lexicon override** 实现思路（参考 [agents_runtime/context_builder.py](../../agents_runtime/context_builder.py) 当前装配逻辑）：

```python
def run_b(a_draft, existing_card=None, fewshot=None, lexicon_path=None):
    prompt = load_prompt("pipeline-b-style.prompt.md")
    if lexicon_path:
        for spec in prompt.inputs:
            if spec.get("name") == "style_lexicon":
                spec["source"] = lexicon_path  # 临时覆盖
                break
    inputs = {"pipeline_a_draft": a_draft, ...}
    context = build_context(prompt, inputs)
    return call_llm(...)
```

---

## 9. workhorse 完成后回报模板

参见 sub1 §9。额外强调：跑通端到端闭环（sub2 propose → apply → sub3 trial → accept → sub2 next propose 引用上轮 accept 的 feedback rows）后才算 DONE；如果闭环跑不通要在报告里明确说明卡哪里。
