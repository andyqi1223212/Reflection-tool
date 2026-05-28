# Phase 4 plan 逐条执行表

对照 `phase4-inbox-ui.md` 全文章节。

| Plan 章节 | 内容摘要 | 执行状态 | 证据 |
|-----------|----------|----------|------|
| **§0** 模块定位 | mermaid：runs → inbox → copy cmd / mv | 见 `03-实现对照.md` §0 | 无 fetch；accept/reject 仅字符串 |
| **§1** 验收 checklist（11 条） | file:// inbox | 见 `01-验收清单对照.md` | 3 fixture + `_index.js` 已生成 |
| **§2** 必读输入 | prototype 风格 + manifest | 已读 `index.html` / `styles.css` / `app.js` chip 模式；manifest 按 Phase 2 §5.2 + fixture | |
| **§3** 禁读列表 | 不读 py prompt / chains | 遵守；inbox 未 import `agents_runtime` | `04` §3 |
| **§4.1** 新增 4 文件 | inbox.* + `_index.py` | 已创建 | 见 `03` §4.1 |
| **§4.2** 修改 index.html | nav + inbox.css link | 已改 | `index.html` |
| **§4.3** 不动 app.js / styles 主逻辑 | 纪律 | `styles.css` 未改；`app.js` 未改 | |
| **§5.1** 方案 A `_index.js` | 无 fetch | `runs/_index.py` → `_index.js` | 本机 3 runs |
| **§5.2** inbox.html 骨架 | header / search / chips / dialog | `inbox.html` | |
| **§5.3** inbox.js | 过滤 / card / modal | `inbox.js` ~280 行 | debounce 150ms |
| **§5.4** inbox.css | verdict 色 + card 左条 | `inbox.css` | 硬编码 hex 不污染 `:root` |
| **§5.5** index 最小侵入 | top-nav + inbox.css | 已做 | |
| **§6** 不在范围 10 条 | 无后端/框架/npm | 满足 | `04` §6 |
| **§7** 风险表 | 缓解 | 见 `04` §7 | header 提示跑 `_index.py` |
| **§8.1** Phase 2 上游 | manifest + judge | fixture 对齐 `RunState` 字段；`a.json` 兜底 route/axis | `02` |
| **§8.2** 用户接口 | accept / reject 命令 | 与 `orchestrate --resume --from push --force-pass` 一致 | |
| **§8.3** 不暴露 | inbox STATE | 纯前端 IIFE | |
| **§9** 实施顺序 8 步 | fixture → index → QA | 已按序完成 | `01` |
| **§10** UX 暖提示 | 相对时间 / 色条 / 复制反馈 | 已实现 | hover `title` 绝对时间 |

**Crosscheck**：`02-与phase1-phase2-crosscheck.md`。
