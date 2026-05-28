# Phase 4 产出索引

本目录为 [`phase4-inbox-ui.md`](../phase4-inbox-ui.md) 的**执行级交付**：对照 plan 全文（§0–§10）说明实现位置、验收状态，并与 Phase 1 / Phase 2 产出 crosscheck。

**状态摘要（2026-05-21）**：inbox 纯前端 + `runs/_index.py` 已落地；3 条 `sample_fixture_*` 供 `file://` QA；本机需在仓库根执行 `python runs/_index.py` 后打开 `crystallization-prototype/inbox.html`。

| 文档 | 内容 |
|------|------|
| [00-plan逐条执行表.md](./00-plan逐条执行表.md) | plan §0–§10 逐条 ↔ 代码/产出 |
| [01-验收清单对照.md](./01-验收清单对照.md) | plan §1 checklist 11 条 |
| [02-与phase1-phase2-crosscheck.md](./02-与phase1-phase2-crosscheck.md) | 与 phase1/phase2 产出对照 |
| [03-实现对照.md](./03-实现对照.md) | §4 交付物 + §5 实现要点 |
| [04-范围边界与风险.md](./04-范围边界与风险.md) | §3 禁读 / §6 不在范围 / §7 风险 |
| [05-摩擦与后续.md](./05-摩擦与后续.md) | 摩擦、后续 hook |

**代码与页面**

| 路径 | 职责 |
|------|------|
| `crystallization-prototype/inbox.html` | 页面骨架 |
| `crystallization-prototype/inbox.js` | 列表 / 过滤 / modal / 复制 |
| `crystallization-prototype/inbox.css` | inbox 专有样式 |
| `runs/_index.py` | 生成 `runs/_index.js` |
| `runs/sample_fixture_*` | dev fixture（3 种 verdict/error 形态） |
| `crystallization-prototype/index.html` | 增加 → inbox 链接 + `inbox.css` |
