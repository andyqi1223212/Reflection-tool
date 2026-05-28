# Phase 2 plan 逐条执行表

对照 `phase2-orchestrator.md` 全文章节；状态列指向代码或 `phase2产出` 其它文档。

| Plan 章节 | 内容摘要 | 执行状态 |
|-----------|----------|----------|
| **§0** 模块定位 | mermaid 数据流 | 见 `03-数据流与实现对照.md` §0 |
| **§1** 验收 checklist（10 条） | 可测试标准 | 见 `01-验收清单对照.md` |
| **§2** 必读输入表 | context curation | 已遵守；crosscheck 见 `02-与phase1-crosscheck.md` |
| **§3** 禁读列表 | 防越权 | 见 `04-范围边界与风险.md` §3 |
| **§4.1** 新增文件 5 个 | 代码文件 | 已创建；见 `03` §4.1 |
| **§4.2** `runs/` + `.gitignore` | 目录 | `runs/.gitignore` 已添加 |
| **§4.3** 修改文件无 | 不改既有 | 满足（未改 `agents.py` / `round2` / `__init__.py`） |
| **§5.1** run_id 形态 | slug + hash | `orchestrate.make_run_id` |
| **§5.2** manifest schema | JSON 字段 | `run_state.RunState`；`05` 记与示例细微差异 |
| **§5.3** stages 五段 | 顺序与产物 | `orchestrate.STAGE_ORDER` + 各 `run_stage_*` |
| **§5.4** `_load_existing_card` | chains 列表 | `orchestrate._load_existing_card` |
| **§5.5** push / mode / exit / force_pass 方案 A | merge 语义 | `run_stage_push` + `_subprocess.interpret_merge_exit` |
| **§5.6** resume 算法 | `--from` 截断+删文件 | `_truncate_completed_for_resume` + `_delete_artifacts_from` |
| **§5.7** CLI signature | 子命令 | `_cli`；`--list-pending` 已实现 |
| **§5.8** `run_stage` wrapper 心智 | try/fail 写 manifest | `run_single_case` 内层 try/except |
| **§6** 不在范围 10 条 | 防 scope creep | `04` §6 |
| **§7** 风险表 | 缓解 | `04` §7 |
| **§8.1** Phase 1 接口 | `run_a/b/judge` | 仅用 `agents` 包 |
| **§8.2** `run_single_case` | 给 Phase 3 | `orchestrate.run_single_case` |
| **§8.2** manifest 稳定 | 给 Phase 4 | 字段名固定；见 `03` §5.2 |
| **§8.3** 不暴露内部 | 私有模块 | `_subprocess` 未 re-export |
| **§9** 实施顺序 7 步 | 时间估算 | `04` §9 |

**与 Phase 1 产出总 crosscheck**：`02-与phase1-crosscheck.md`。
