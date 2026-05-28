# `round2/route_helper.py` — 实施 Spec（给 composer）

> **角色**：这份 md 是给 composer / workhorse coder 的**实施契约**。本 spec 由架构层（Claude/architect）写定，py 落地交由 composer 完成。两方互不越界——架构层不直接写脚本逻辑，composer 不改 spec 与 prompt 契约。
>
> **状态**：未实施。本仓库根目录已删除上次的 throwaway 实现，请按本 spec 重写到 `round2/route_helper.py`。
>
> **依赖**：Python 3.10+（已有 `./venv`）；只依赖标准库（`json`/`re`/`pathlib`/`argparse`）。**禁** 任何 LLM SDK、向量库、第三方依赖。

---

## 1. 第一性原理：这个工具解决什么

新的 question_md 进来时，Pipeline A 需要决定路由 ∈ `{new, update, meta}`（详见 `.cursor/plans/round_2_dogfood_80c6df8a.plan.md` §10）。让 A 在不读全量 `chains.json` 的前提下做出这个判断，需要一层 **retrieval helper**——把 chains.json 里 24+ 张卡按"和新 md 字符层重叠度"排序，输出 top-K candidates + 一个**启发性**（不绝对的）route_hint。

**两个不可越的边界**（守住 v0.5 plan §8 / agents/conventions.md 铁律 6）：

1. **不调 LLM SDK**——`route_helper.py` 是纯字符匹配的工具，不引入 OpenAI/Anthropic SDK；语义路由判定**只能**由 Pipeline A 做。
2. **不写文件**——stdout 输出一段 JSON，由用户 / Cursor 把 stdout 复制粘进 A 的 chat。**不**直接修改 chains.json / question_md / 任何 prompt。

如果未来要升级到 sentence embedding，加在 v1 schema 钩子里，**不**在 v0.5 阶段引入。

---

## 2. 接口契约（CLI）

### 2.1 调用形态

```bash
./venv/bin/python3 round2/route_helper.py \
    --question 外部source/学校压力下的代偿性控制.md \
    [--chains data/chains.json] \
    [--top-k 5] \
    [--update-high 0.40] \
    [--update-medium 0.13] \
    [--meta-min-cross-axis 0.10] \
    [--include-raw-answer-excerpt]
```

### 2.2 参数

| 参数 | 必填 | 类型 | 默认 | 含义 |
|---|---|---|---|---|
| `--question` | ✅ | Path | — | 新 question_md 路径（绝对或仓库根相对） |
| `--chains` | ❌ | Path | `<repo>/data/chains.json` | chains.json 路径 |
| `--top-k` | ❌ | int | 5 | 输出 candidates 个数 |
| `--update-high` | ❌ | float | 0.40 | top1 score ≥ → `route_hint=update, confidence=high` |
| `--update-medium` | ❌ | float | 0.13 | top1 score 落在 [medium, high) → `route_hint=update, confidence=medium`（**A 必须复核**） |
| `--meta-min-cross-axis` | ❌ | float | 0.10 | top-K 横跨 ≥2 axis 且 top2 score ≥ → `route_hint=meta, confidence=medium` |
| `--include-raw-answer-excerpt` | ❌ | flag | false | 额外输出 question_md 里 raw answer 段的 1200 字摘要（若有） |

`repo_root` 推断：`Path(__file__).resolve().parents[1]`（沿 round2/ 的 next_ic_id.py 同款约定）。

### 2.3 失败时的退出码

| Exit | 触发条件 | 行为 |
|---|---|---|
| 0 | 成功 | stdout = JSON；stderr = 空或 `[debug] ...` |
| 1 | `question_md` 不存在 / chains.json 不存在 / question_md 抽不出用户文本 | stderr 打印 `FAIL: <reason>`；stdout 空 |

不要用 try/except 吞掉文件解码错；就让 traceback 报到 stderr——composer 实现时直接让 Python 默认错误处理。

---

## 3. 输出 JSON Schema

stdout 输出**单段 JSON**（`json.dumps(..., ensure_ascii=False, indent=2)`），结构如下：

```json
{
  "question_md": "外部source/学校压力下的代偿性控制.md",
  "question_excerpt": "<前 240 字，去掉了 gemini/ds response 段的剩余用户原话>",
  "candidates": [
    {
      "ic_id": "IC-012",
      "title": "睡前上厕所 / 入睡失败后的刷新机制",
      "axis": "attention",
      "patterns": ["P-SPIRAL", "P-EXIST", "P-OVER"],
      "score": 0.1426,
      "overlap": 0.1667,
      "jaccard": 0.0065,
      "trigger_excerpt": "睡前控制床单、喝水、上厕所。状态差、晚睡、没容错时，会不断用上厕所刷新状态，越刷新越焦虑。",
      "matched_keywords": ["上厕所", "刷新"]
    }
    /* ... 共 top-K 条，按 score 降序 ... */
  ],
  "route_hint": "new | update | meta",
  "confidence": "high | medium | low",
  "route_hint_reason": "<≤240 字白话，给 A 看的；引用具体阈值与命中分数>",
  "thresholds": {
    "update_high": 0.40,
    "update_medium": 0.13,
    "meta_min_cross_axis": 0.10
  },
  "raw_answer_present": true,
  "raw_answer_excerpt": "<仅当 --include-raw-answer-excerpt 且 md 含 raw answer 段时存在；≤1200 字>"
}
```

**字段细节**：

- `question_excerpt`：用 `extract_question_text()` 去掉 `# *response` 段后的前 240 字；保留换行；strip 前后空白。
- `candidates[].score`：`overlap * 0.85 + jaccard * 0.15`，保留 4 位小数。
- `candidates[].overlap` / `.jaccard`：单独输出，方便 A 回查"为什么是这个分"。
- `candidates[].matched_keywords`：用 title 切出 2-8 字的片段，检查 normalize 后 question_md 里**实际出现**的那些，最多 5 个。
- `route_hint`：三选一，见 §4 决策树。
- `confidence`：三选一，见 §4。**A 在 confidence != high 时必须仔细审 top-3**，不能盲信 hint。
- `route_hint_reason`：一行白话，含 top1 IC id / score / 引用的阈值 / 触发的判定分支。
- `raw_answer_present` / `raw_answer_excerpt`：仅当传 `--include-raw-answer-excerpt` 时才出现这两字段。

---

## 4. 算法详细规格

### 4.1 文本归一化

```python
def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\s\u3000]+", " ", text)
    # 去除中英标点（保中文字 / 英数字 / 单空格）
    text = re.sub(r"[、，。；：！？,.;:!?\"'`~（）()\[\]【】<>《》—\-_/\\|*#@%&=+]", " ", text)
    return text.strip()
```

### 4.2 question_md 抽取

`extract_question_text(md_path: Path) -> str`：

- 逐行扫描 md：
  - 当遇到 `# *response` 开头的标题（如 `# gemini response`、`# ds response`、`# claude response`），进入 `skip_response = True`
  - 当遇到 `# you asked` / `# You asked`，退出 `skip_response`
  - `---` 分隔线跳过
  - 引用前缀（`> ...`）保留（用户可能贴别人写的引用进来，包含语言肌理）
- 返回拼接后的文本

**测试断言**：对 `外部source/学校压力下的代偿性控制.md`，抽出来的文本**不**含 `# gemini response` 后那段长 prompt（"神经动力学 ATD 飞轮"），但含每一段 `# you asked` 下面的用户原话。

### 4.3 raw answer 抽取（可选）

`extract_raw_answer_text(md_path: Path) -> str | None`：

与 §4.2 相反——只收集 `# *response` 段到下一个 `# you asked` 之间的文本。无则返回 None。

**测试断言**：对同一份 md，能抽到 "为了将我们讨论过的神经科学..." 那段。

### 4.4 char-trigram

```python
def char_trigrams(text: str) -> set[str]:
    text = normalize(text)
    if len(text) < 3:
        return set()
    return {text[i:i+3] for i in range(len(text) - 2)}
```

不分词、不去停用词——中文文本短，停用词反而损失信号。

### 4.5 卡片特征提取

`card_feature(card: dict) -> tuple[str, list[str]]`：

- feature 字符串 = `title + " " + chain.trigger + " " + " ".join(chain.questions)`
- keywords 列表：title 用 `[，。、,.;:！？!?]` 切分；每段 strip 后长度 2-8 的纳入；最多 5 个

### 4.6 相似度

```python
def jaccard(a, b): return |a ∩ b| / |a ∪ b|  # 空 set 返回 0.0
def overlap_coefficient(query, card): return |query ∩ card| / |card|  # card 空返回 0.0

score = overlap * 0.85 + jaccard * 0.15
```

**为什么 overlap 主轴**：question_md 通常几千字（trigram 数千个），IC 特征通常几百字（trigram 几百个）。Jaccard 对这种不对称严重偏低。Overlap = "IC 描述的东西被 question 覆盖多少"，正好是我们要的。

### 4.7 路由决策树（带 confidence）

设 `top1 = candidates[0].score`，`top2 = candidates[1].score`，`cross_axis = candidates 里 axis 字段值的去重个数 ≥ 2`。

```text
if top1 >= update_high:                     # 默认 0.40
    hint = "update"; confidence = "high"
elif top1 >= update_medium:                 # 默认 0.13
    hint = "update"; confidence = "medium"  # A 必须复核 top-3
elif cross_axis and top2 >= meta_min_cross_axis:  # 默认 0.10
    hint = "meta";   confidence = "medium"
else:
    hint = "new"
    confidence = "high" if top1 < meta_min_cross_axis else "low"
```

`reason` 字段必须引用具体的阈值名 + 触发分支，便于回查。

---

## 5. Smoke Test（必须通过）

实施完后，composer 必须跑两个 smoke test 确认行为：

### 5.1 已知 update 场景

```bash
./venv/bin/python3 round2/route_helper.py \
    --question 外部source/学校压力下的代偿性控制.md \
    --top-k 8 \
    --include-raw-answer-excerpt
```

**期望**：
- `route_hint == "update"` **或** `route_hint == "meta"`（视当前 chains.json 状态，IC-012 应排进 top-3）
- `confidence ∈ {medium, low}`（字符相似度物理上限决定，几乎不会 high）
- `candidates[0..2]` 至少有一项是 IC-012
- `raw_answer_present == true`
- `raw_answer_excerpt` 包含 "神经动力学" 或 "状态" 或 "杏仁核"

### 5.2 已知 new 场景

```bash
./venv/bin/python3 round2/route_helper.py \
    --question 外部source/球场垃圾话应对策略.md \
    --top-k 5
```

**期望**：
- IC-024（球场垃圾话）已存在 → 应能命中 top1，hint=update
- 验证算法不会"全员 new"

> **注**：smoke test 通过 ≠ 算法完美。字符相似度有上限，最终路由仍由 A 判定。smoke test 只验证"工具没坏"。

---

## 6. 文件层契约

| 行为 | 允许？ |
|---|---|
| 读 `data/chains.json` | ✅ |
| 读 `--question` 指定的 md | ✅ |
| stdout 输出 JSON | ✅ |
| stderr 输出 `[debug] ...` | ✅ |
| 修改 chains.json | ❌ |
| 修改 question_md | ❌ |
| 创建任何文件 | ❌ |
| 调用 LLM SDK | ❌ |
| `import` 标准库以外的包 | ❌ |
| 抑制 Python 默认 traceback | ❌（让错误明确暴露） |

---

## 7. 文件位置 & 命名约定

- 实施文件：`round2/route_helper.py`
- 类型注释建议：`from __future__ import annotations`（py3.10 在用 `set[str]` 等 PEP 585 语法时更兼容）
- 文件顶部 docstring：照本 spec §1 + §2.1 写一版精简版，引用本 spec 路径

未来"转正"到 `tools/route_helper.py` 时，与 `next_ic_id.py` / `run_pipeline.py` 一并搬迁，**保留**接口契约不变（防 prompt 引用断链）。

---

## 8. 与 Pipeline A 的衔接（架构层，仅供 composer 理解上下文）

A 的 invocation template（详见 [`agent第二轮/pipeline-a-diagnose.prompt.md`](../agent第二轮/pipeline-a-diagnose.prompt.md)）会加一步：

```
# Step 0: 终端跑 route_helper，把 stdout 粘进来
./venv/bin/python3 round2/route_helper.py --question <md> --include-raw-answer-excerpt

# 然后把 stdout 作为 route_helper_output 字段塞给 A
```

A 看到 `route_helper_output` 后：

- 拿 `candidates` + `route_hint` + `confidence` + `route_hint_reason` 作为**参考**
- 仍要自己读 question_md 全文做语义判定
- 在 `diagnostic_notes.route_reasoning` 里**必须**引用 helper 的 top1 IC + score，并说"我接受 helper 的建议"或"我覆盖 helper 的建议，因为…"
- 如果 confidence != high，A **必须**展开 top-3 candidates 的 trigger 各自看一遍再决定

Composer 不需要在 py 里实现这条约束——A 的 prompt 自己会强制。py 只负责提供干净的 JSON。

---

## 9. v1 钩子（不实施，留接口）

未来想升级到语义相似度：

- 加一个 `--embedding` flag（默认 false）
- true 时跑一份 sentence embedding（`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 一类）
- 复合 score：`overlap * 0.5 + embedding_cos * 0.5`（embedding 主导，overlap 留作 explainable 辅助）

但这要 v1，**不**在 v0.5 落地。v0.5 阶段如果 char-trigram 准确度不够，先调阈值 / 让 A prompt 更激进地复核——不要靠加包解决可解释性问题。

---

## 10. 提交时的自检（composer ship 前默念）

- [ ] 只依赖标准库
- [ ] `repo_root()` 用 `Path(__file__).resolve().parents[1]`（同 next_ic_id.py 约定）
- [ ] stdout 单段 JSON，`ensure_ascii=False, indent=2`
- [ ] §5 两个 smoke test 都跑通
- [ ] 不写任何文件
- [ ] 不抓 LLM SDK
- [ ] 文件顶部 docstring 引用本 spec
- [ ] 与 `round2/next_ic_id.py` 的代码风格一致（无 try/except 包装、无 logging 配置、stderr 用 `print(..., file=sys.stderr)`）

实施完成后在 [`round2/A1-A2与agent-workflow融合说明.md`](A1-A2与agent-workflow融合说明.md) §7（架构层会写）下追加一条 "✅ route_helper.py 已实施，本节命令可直接用"，并把本 spec §10 的 checklist 全勾上。
