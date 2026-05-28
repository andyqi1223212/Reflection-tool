# Agentflow Context 审阅器

可视化查看 **Pipeline A / B / Judge** 实际装配的上下文（与 `agents_runtime` 的 `build_context()` + `run_a` / `run_b` / `run_judge` 一致），支持勾选模拟瘦身。

**数据单一来源**：

- `tools/export_agentflow_context_chunks.py` 读取各 prompt **frontmatter `inputs[]`**
- 导出前对每条 pipeline 做 **crosscheck**（重组块 vs `build_context()` 字节级一致）

## 打开

**推荐（与主站 / Inbox 同一端口）：**

```bash
cd <repo-root>
bash tools/start_dev_ui.sh
```

开发台导航 → **Context 审阅器**，或直接打开 `http://127.0.0.1:8765/context-curator/`。

`bash ./start.sh` 会转发到上述命令（不再单独起第二个 `http.server`）。启动时会按需刷新 `chunks.data.js`。

## 页面说明

| 区域 | 含义 |
|------|------|
| **crosscheck** 条 | 导出脚本实测：块重组是否与 `build_context()` 一致 |
| **当前 runtime** | 当前 pipeline 的 `inputs[]`、禁止列表、orchestrate 顺序 |
| **① 正在使用** | `status: active`，与对应 `run_*` 一致 |
| **② 已停用** | 如 B v2.2 不再喂入的 brief/schema/标注册章节 |
| **对齐当前 runtime** | 勾选集 = 实测装配字符量 |

## 手动刷新数据

```bash
cd <repo-root>
venv/bin/python3 tools/export_agentflow_context_chunks.py
```

旧入口 `export_pipeline_b_context_chunks.py` 会转调上述脚本。

## 相关文档

- [pipeline-b-context-curation-plan.md](../agentflow3-tocode/pipeline-b-context-curation-plan.md)
- [pipeline-b-context-curation-audit.md](../agentflow3-tocode/pipeline-b-context-curation-audit.md)
- [codemap-agentflow.md](../agentflow3-tocode/codemap-agentflow.md)
