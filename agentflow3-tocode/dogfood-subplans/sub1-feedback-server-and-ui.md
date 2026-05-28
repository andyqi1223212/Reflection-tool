# Subplan 1 · Feedback Server + 打分 UI

> 母 plan：`~/.cursor/plans/dogfood-feedback-loop-v0_d9ffe369.plan.md`（背景；workhorse 不必读，本文件已自包含）
> 前置：无（这是依赖链起点）
> 后置：sub2 / sub3 / sub4 都依赖本子 plan 产出的 `users/qihaoyu/feedback.jsonl` 作为数据燃料

---

## 0. 目标

让用户在浏览器里点几下 / 写几句话，就能把对一张晶体卡的「打分 + 感受」自动落到 `users/qihaoyu/feedback.jsonl`，零摩擦。

**为什么这件事是项目最关键的基础设施**：当前 lexicon / synthesis 都是用户手写脑补；要让 Pipeline B 自己进化，必须先有结构化的「用户喜不喜欢」信号源。

---

## 1. 前置依赖

- 本仓库 `agents_runtime/`、`crystallization-prototype/`、`runs/` 已存在并工作
- Python 3 venv 在 `./venv/`，无需安装新依赖（仅用 stdlib `http.server`）
- 用户偏好：中英混合可以、回答 / 注释 / commit message 易于理解，专有名词外尽量中文，避免黑话堆积

---

## 2. 必读上下文

在动手前，**workhorse 必须读这些文件**（不读会写出风格漂移的代码）：

| 文件 | 你为什么要读 |
|---|---|
| [.cursorrules](../../.cursorrules) | 项目通用约定 + Lessons 区；你要在末尾追加一条 |
| [context/pipeline-b-style-lexicon-v1.md](../../context/pipeline-b-style-lexicon-v1.md) §1 拒杞表 | 你要在表里加一行；理解现表结构 |
| [crystallization-prototype/inbox.html](../../crystallization-prototype/inbox.html) | 现有 UI 结构 + 复制命令交互；你要在卡片内嵌入打分表单 |
| [crystallization-prototype/inbox.js](../../crystallization-prototype/inbox.js) | 卡片渲染逻辑；学其 dom 创建 + event 绑定风格 |
| [crystallization-prototype/inbox.css](../../crystallization-prototype/inbox.css) | 现有样式变量与命名规范 |
| [crystallization-prototype/index.html](../../crystallization-prototype/index.html) | 主站结构；你要给已 push 卡也加打分 |
| [crystallization-prototype/app.js](../../crystallization-prototype/app.js) | 主站卡片渲染；同上 |
| [runs/_index.py](../../runs/_index.py) | 当前 inbox 数据生成脚本；你要扩展它聚合 feedback_summary |
| [runs/_index.js](../../runs/_index.js) | 看生成结果格式，理解前端怎么消费 |

---

## 3. 任务清单（覆盖母 plan todos: track0 / A1 / A2 / A3 / A4）

### 3.1 Track 0 · 偏好归档（先做，5 分钟）

- [ ] [.cursorrules](../../.cursorrules) 的 `## Cursor learned` 末尾追加一行 Lessons：

  ```
  - **用户语言偏好**：中英混合可以、但回答 / 注释 / commit message 易于理解；专有名词外尽量中文，避免黑话堆积（例：用「上下文装配」而非 "context assembly"）。
  ```

- [ ] [context/pipeline-b-style-lexicon-v1.md](../../context/pipeline-b-style-lexicon-v1.md) §1 拒杞表追加一行：

  ```markdown
  | **过密英文术语 / 黑话堆积** | "context wall"、"attention dilution"、"single source of truth" 连用 | 改写为同义中文 + 必要英文括注；一段最多 1 个英文专有名词 |
  ```

  并在 §1 末尾「实证」一行后补一句：「**本 lexicon 自身也守此规则**——meta；维护时若发现自己堆英文，先修自己再传播」。

  注意：**lexicon 改后 frontmatter 的 `last_synced` 字段** 同步改成今天日期；**不**要 bump 版本号（这只是微调，正式 bump 留给 sub2）。

### 3.2 A1 · feedback_server.py

新建 [tools/feedback_server.py](../../tools/feedback_server.py)：

- 基于 Python stdlib `http.server.ThreadingHTTPServer` + `BaseHTTPRequestHandler`
- 启动参数：`--port 8765` (默认) / `--open` (自动 `open http://...`) / `--root <repo_root>` (默认自动定位)
- 路由表见 §4 输入输出契约
- 启动时若发现 `runs/_index.js` mtime > 24h 或不存在 → 自动调 `runs/_index.py` 刷新（用 subprocess）
- POST `/api/feedback` 失败时返回 4xx + JSON `{"error": "..."}`，不抛 stack trace
- 写 jsonl 时用文件锁（`fcntl.flock`）避免并发；每行 append + flush
- 启动横幅打印：端口 / jsonl 路径 / 当前 feedback 总数

新建 [tools/start_feedback_server.sh](../../tools/start_feedback_server.sh)：

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./venv/bin/python3 tools/feedback_server.py --port "${PORT:-8765}" --open
```

`chmod +x`。

### 3.3 用户目录 + gitignore

- 新建目录 `users/qihaoyu/`（带 `.gitkeep`）
- 新建 `users/.gitignore`：

  ```
  */feedback.jsonl
  */lexicon_proposals/
  */synthesis_proposals/
  !*/.gitkeep
  ```

  （理由：feedback 是个人数据，不应进公开 repo；后续 sub2/sub4 产物同理）

### 3.4 A2 · inbox.html 打分表单

在 [crystallization-prototype/inbox.html](../../crystallization-prototype/inbox.html) + `.js` + `.css` 里给每张待审 run 卡加打分表单：

- 表单位置：放在 accept/reject 命令复制区**下方**（不要挤掉现有功能）
- 用 `<details class="ic-feedback">` 默认折叠，标题 `打分 / 感受 ▼`
- 展开后含：
  - 4 个独立 `<input type="range" min="1" max="5" step="1">`：mechanism / anchor / micro_steps / overall。每个滑块旁显示当前数值。**4 个都允许留空**（用 checkbox `<label><input type="checkbox" checked> 评分此项</label>` 控制）
  - `<textarea name="freeform" placeholder="一句感受，可写：哪里好 / 哪里别扭 / 我希望 lexicon 怎么改">`
  - `<fieldset>` 多选 tags：`stylewin`（这张风格好）/ `stylelose`（风格差）/ `lexicon-cand`（候选 lexicon 启发）
  - `<input name="lexicon_hypothesis" placeholder="(可选) 我猜 lexicon 应该补什么">`
  - 提交按钮 `提交 feedback`
- 提交逻辑：
  - `fetch('/api/feedback', { method: 'POST', body: JSON.stringify({...}) })`
  - 成功 → 表单变绿底 + 显示 `已记录 · 共 N 条 (server 返回 N)`
  - 失败 → 表单变红底 + 显示 server 错误文本
- 渲染已有 feedback：卡片首次渲染时 `GET /api/feedback?target_type=run&target_id=<run_id>`；若有数据，在 `<details>` 标题旁加徽标 `(N 条已记录)`，且展开后列出每条简短摘要（ts + overall 分 + freeform 前 30 字）
- target_type / target_id：对 inbox = `run` / `<run_id>`；对主站 = `card` / `<IC-NNN>`（见 A3）

### 3.5 A3 · index.html 主站打分

[crystallization-prototype/index.html](../../crystallization-prototype/index.html) + `app.js` + `styles.css` 同款表单：

- 嵌在每张卡的展开区（点击卡片展开后看到，与「我的笔记」并排或下方）
- target_type = `card`，target_id = 卡的 `id` 字段（如 `IC-024`）
- 其它字段、样式、提交逻辑与 A2 一致
- 复用 inbox.css 的样式类（建议把表单 CSS 抽到 `crystallization-prototype/feedback-form.css`，inbox.html + index.html 都引用）

### 3.6 A4 · runs/_index.py 聚合 feedback_summary

修改 [runs/_index.py](../../runs/_index.py)：

- 启动时读 `users/qihaoyu/feedback.jsonl`（不存在则空数组），按 target_id 聚合：
  ```python
  feedback_summary = {
      "<run_id_or_card_id>": {
          "count": N,
          "avg_overall": float | None,  # 仅 overall 维有评分时计算
          "latest_ts": "...",
          "latest_freeform_preview": "首 30 字...",
          "tags": ["stylewin", ...]  # 去重并集
      }
  }
  ```
- 把 `feedback_summary` 写入生成的 `_index.js` 顶层对象（不破坏现有字段）
- 前端 inbox.js / app.js 渲染卡片时若 `feedback_summary[id]` 存在，在卡顶徽标显示 `已 N 条 · 平均 X.X`

---

## 4. 输入 / 输出契约

### 4.1 feedback.jsonl 行 schema

每行一个 JSON 对象，UTF-8，行尾 `\n`：

```json
{
  "ts": "2026-05-21T15:30:00+08:00",
  "uid": "qihaoyu",
  "target_type": "run",
  "target_id": "2026-05-21_觉醒_0f898d",
  "stage_focus": "b",
  "scores": {
    "mechanism": 4,
    "anchor": 5,
    "micro_steps": null,
    "overall": 4
  },
  "freeform": "anchor 短得能默念，但 mechanism 第二句感觉在堆术语。",
  "tags": ["stylewin", "lexicon-cand"],
  "lexicon_hypothesis": "§1 拒杞表应该加一行『动态 attention budget』这种词"
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ts` | ISO8601 string with TZ | yes | server 端生成 |
| `uid` | string | yes | server 从 env `IC_USER` 读，默认 `qihaoyu` |
| `target_type` | `"run"` \| `"card"` | yes | run = inbox 待审；card = 主站已 push |
| `target_id` | string | yes | run_id 或 IC-NNN |
| `stage_focus` | `"b"` \| `"merged"` | yes | run → `b`；card → `merged` |
| `scores.*` | int 1-5 \| null | 至少 1 项非 null | 4 维独立 |
| `freeform` | string | no | 用户自由文本 |
| `tags` | string[] | no | 枚举：`stylewin` / `stylelose` / `lexicon-cand` / `synthesis-cand` |
| `lexicon_hypothesis` | string | no | 用户猜测 lexicon 应该怎么改 |

### 4.2 server 路由表

| Method | Path | 入参 | 出参 |
|---|---|---|---|
| `GET` | `/` | - | 302 → `/inbox.html` |
| `GET` | `/<file>` | path 文件名 | 从 `crystallization-prototype/<file>` 服务 |
| `GET` | `/runs/_index.js` | - | 从 `runs/_index.js` 服务 |
| `GET` | `/runs/<run_id>/<file>` | run_id 必须存在 | 从 `runs/<run_id>/<file>` 服务（用于 inbox 内联查看 a/b/judge.json）|
| `GET` | `/api/feedback?target_type=X&target_id=Y` | 必填 | JSON `{count: N, items: [{ts, scores, freeform, tags}, ...]}` |
| `POST` | `/api/feedback` | body = feedback line schema (除 ts/uid，server 补) | JSON `{ok: true, total: N, line_index: K}` 或 `{error: "..."}` |
| `GET` | `/api/health` | - | JSON `{ok: true, jsonl_path, total_lines, server_started_at}` |

### 4.3 文件落点

- 新建：`tools/feedback_server.py`, `tools/start_feedback_server.sh`
- 新建：`users/.gitignore`, `users/qihaoyu/.gitkeep`
- 新建（运行时）：`users/qihaoyu/feedback.jsonl`
- 新建：`crystallization-prototype/feedback-form.css`（共享样式）
- 修改：`.cursorrules`, `context/pipeline-b-style-lexicon-v1.md`, `crystallization-prototype/inbox.html|.js|.css`, `crystallization-prototype/index.html|app.js|styles.css`, `runs/_index.py`

---

## 5. 验收清单

完成后自检每条；workhorse 报告里逐条 ✅/❌。

- [ ] `bash tools/start_feedback_server.sh` 起服务，浏览器自动开 `http://localhost:8765/inbox.html`
- [ ] inbox 至少 1 张待审卡可见打分表单；调到一些分 + 写一句话 + 选 1 个 tag → 提交 → 表单变绿 + `feedback.jsonl` 多 1 行
- [ ] 刷新页面 → 该卡 `<details>` 标题旁显示 `(1 条已记录)`
- [ ] 同一卡再提交一次 → jsonl 多第 2 行；徽标 → `(2 条已记录)`
- [ ] `http://localhost:8765/index.html` 主站任一卡展开 → 同样可打分；提交 → jsonl 多一行，target_type=card
- [ ] `GET /api/health` 返回 200 + 正确 total_lines
- [ ] 4 维评分允许全部留空（checkbox 取消）；但若全空 server 应拒绝（至少 1 项 score 或 freeform 非空才接受）
- [ ] 关掉 server / 用 `file://` 打开 inbox.html 仍能用 accept/reject 命令复制（不破坏现有功能）
- [ ] `runs/_index.py` 跑完后 `_index.js` 顶层有 `feedback_summary`；inbox 卡顶徽标显示已 N 条
- [ ] `.cursorrules` Lessons 已加；`lexicon-v1.md` §1 已加新行 + last_synced 改今天
- [ ] `users/.gitignore` 已加，`git status` 不应把 `users/qihaoyu/feedback.jsonl` 显示为 untracked
- [ ] 所有新代码 / 注释 / commit message 用中文为主，专有名词外尽量中文（违反 Track 0 偏好的直接打回）

---

## 6. 范围边界（绝对不做）

- ❌ **不引入** Flask / FastAPI / Tornado / aiohttp（用户偏好简洁，stdlib `http.server` 够用）
- ❌ **不实现** multi-user 切换（uid 从 env `IC_USER` 读，默认 `qihaoyu`；不做 login）
- ❌ **不实现** server 端 LLM 调用（synthesize 是 sub2 的事）
- ❌ **不实现** lexicon / synthesis review UI（sub2 / sub4 的事；本子 plan 不碰 `lexicon_review.html`）
- ❌ **不实现** eval_lite trial 重跑（sub3 的事）
- ❌ **不动** `agents_runtime/orchestrate.py` / `round2/*.py` / `tools/export_v3_chains.py`
- ❌ **不删 / 不破坏** inbox 现有 accept/reject 命令复制功能
- ❌ **不写** unit test（本项目目前没有 test 文化；先跑通；测试留给以后）

---

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 用户已习惯 `file://` 打开 inbox；新 server 模式需要记一条命令 | start_feedback_server.sh 一键起 + 自动 open 浏览器；README 写在 `crystallization-prototype/start.sh` 旁附近 |
| 多次提交同一卡造成 jsonl 膨胀 | 不做去重（用户可能确实多次评价不同维度）；sub2 的 synthesize 自己处理重复 |
| 浏览器 fetch 跨域 | server 同源服务静态文件 → 不存在跨域问题；不要给前端硬编码 `localhost:8765`，用相对路径 `/api/feedback` |
| jsonl 并发写损坏 | 用 `fcntl.flock` 独占锁；写后立刻 `flush + fsync` |
| 用户改了滑块但忘记勾 checkbox 评分 → 提交是空分 | UI 默认 checkbox 都选中；用户主动取消才空 |
| `runs/_index.py` 跑得慢拖慢 server 启动 | 仅当 `_index.js` mtime > 24h 才自动跑；用户也可手动跑一次后再起 server |

---

## 8. 实施建议（推荐顺序 + 关键代码线索）

1. **先 Track 0**（5 分钟，无代码风险，先建立偏好基线）
2. **再 A1 server 骨架**（不带 feedback 逻辑，只服务静态文件 + `/api/health`）→ 验证 `curl http://localhost:8765/inbox.html` 拿到 html
3. **加 POST /api/feedback**（先 console 打印 body，再写文件）
4. **加 GET /api/feedback**（让前端能查已有）
5. **A2 inbox 表单**（先 1 张卡试，跑通整链）
6. **A3 index 主站表单**（复制 A2 逻辑，target 不同）
7. **A4 _index.py 聚合**（最后；前面不依赖它，先有也不影响）

### 关键代码片段提示

**server 用 ThreadingHTTPServer 而非默认 HTTPServer**（默认是单线程，多 tab 会卡）：

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

**判定路由**：

```python
def do_GET(self):
    from urllib.parse import urlparse, parse_qs
    p = urlparse(self.path)
    if p.path == '/':
        return self._redirect('/inbox.html')
    if p.path.startswith('/api/'):
        return self._handle_api_get(p)
    return self._serve_static(p.path)
```

**jsonl 安全写**：

```python
import fcntl, json
with open(jsonl_path, 'a', encoding='utf-8') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    try:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())
    finally:
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

**前端 fetch**：

```js
async function submitFeedback(targetType, targetId, payload) {
  const body = { target_type: targetType, target_id: targetId, stage_focus: targetType === 'run' ? 'b' : 'merged', ...payload };
  const res = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error((await res.json()).error || res.statusText);
  return res.json();
}
```

---

## 9. workhorse 完成后回报模板

```
sub1 完成报告
==============
新建文件 (N):
  - tools/feedback_server.py (XXX 行)
  - tools/start_feedback_server.sh
  - users/.gitignore, users/qihaoyu/.gitkeep
  - crystallization-prototype/feedback-form.css

修改文件 (M):
  - .cursorrules (+1 行 Lessons)
  - context/pipeline-b-style-lexicon-v1.md (+1 行 §1 + last_synced 改日期)
  - crystallization-prototype/inbox.html (+ 表单 dom)
  - crystallization-prototype/inbox.js (+ feedback fetch 逻辑)
  - ...

验收清单:
  [✅] start_feedback_server.sh 起服务
  [✅] inbox 表单提交落 jsonl
  [...] ...

未做的事 / 偏离 plan 处:
  - <如有，说明原因>
```
