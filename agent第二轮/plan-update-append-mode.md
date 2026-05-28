# Plan：route=update 的 append-only 落地（schema / merge / export / UI）

> 触发源：`agent第二轮/第二轮摩擦.md §9`（用户 2026-05-15 决议）
> 已完成（prompt 层 / 2026-05-15 上午）：`pipeline-a-diagnose.prompt.md` v2.3 + `pipeline-b-style.prompt.md` v2.1 + `push.prompt.md` last_iter 同步
>
> **执行 status（2026-05-15 PM，composer 已落 §1-§5 + §6 dogfood 入口；push.prompt 已解锁 --mode update 路由与 exit code 6/7）**：
>
> | 章节 | 项 | 状态 |
> |---|---|---|
> | §1 | schema 加可选 `updates: []` 数组 + items（含 patterns_added enum / source_refs_added / questions_appended / trigger_addendum / crystallization 子对象 ≤200/≤20/≤60×3） | ✅ done — `data/inquiry-chain.schema.json` |
> | §2 | `run_pipeline.py merge --mode {new,update}` 双分支；mode=update 校验 `output_kind=update_entry` + `_validate_update_entry` + `append_update_entry_to_md`；新 exit code 6/7；dry-run 双形态 | ✅ done — `round2/run_pipeline.py` |
> | §3 | `export_v3_chains.py` 新增 `update_entry_to_details_markdown` / `append_update_entry_to_md` / `_parse_ic_update_inner` / `_parse_updates_from_chunk`；序列化用 `<!-- BEGIN UPDATES --> <details class="ic-update">` 模板；parse 回填进卡 `updates` | ✅ done — `tools/export_v3_chains.py` |
> | §4 | `validate_chains_json.py` 跟随 schema 自动覆盖 | ✅ done（无需改） |
> | §5 | prototype UI：`<details class="card-updates">` 折叠 / 每 entry 渲染 date+patch_reasoning+新增 crystal+delta；检索 `updateKeywordScore` 合入 `keywordScore` 并自动展开命中卡 | ✅ done — `crystallization-prototype/app.js` + `styles.css` |
> | §6 | IC-012 全链路 dogfood | ⏳ 待用户跑（A v2.3 重跑 update_directives → B v2.1 → 手判 verdict / 或等 judge 同步 → push --mode update） |
> | §7 | `judge.prompt.md` 同步到 update_entry 语义 | ⛔ **断点**：judge 仍按旧 `output_kind=patch` 评分；update 链路 Judge 这一步会大量 fail。需用户单独一轮 prompt iteration（本 plan §7 列了字段差异表） |
> | §8 | 风险与回退 | 备忘 |
> | §9 | 实施顺序 | 备忘 |
>
> push.prompt.md 已同步加上"按 `b_output.output_kind` 选 `--mode`"路由表 + exit 6/7 行 + 触发方式 3（route=update 已可用）/ 触发方式 4（route=meta 仍待）。
>
> **第一性原理**：route=update 的原卡 mechanism / anchor / micro_steps / patterns / source_refs / chain 是历史资产，**永不被任何下游环节覆盖**；新增的"层"以 append-only 形式累积到 `card.updates[]`。单次写入仍守原 schema 限制（mechanism 30-200 / anchor 4-20 / micro_steps 1-3×5-60），但卡的累积总和通过追加叠层。

## 0. 改动总览

| # | 文件 | 性质 | 风险 | 估时 |
|---|---|---|---|---|
| §1 | `data/inquiry-chain.schema.json` | 加可选 `updates` 数组 | 低（向后兼容） | 10 min |
| §2 | `round2/run_pipeline.py` | 增 `--mode update` + append 逻辑 | 中（新增子分支，原 new 路径不动） | 60 min |
| §3 | `tools/export_v3_chains.py` | 序列化 updates 到 md / chains.json | 中（v3 md 模板要加 update 段） | 45 min |
| §4 | `tools/validate_chains_json.py` | 跟随 schema 自动覆盖（无需改） | — | 0 |
| §5 | `crystallization-prototype/` (`app.js` / `styles.css` / `index.html`) | 渲染原卡 + 折叠"更新历史 (N)" | 中 | 60 min |
| §6 | 回归 dogfood：在 IC-012 上跑一遍 A→B→Judge→push update | 验证 | — | 30 min |

**总估时**：3-4 小时单次专注开发；可按 §1 → §2 → §3 → §5 → §6 顺序串行；§4 自动满足。

## 1. Schema 改动（`data/inquiry-chain.schema.json`）

### 1.1 目标

在 root 加可选 `updates` 数组字段。原 `crystallization` / `chain` / `patterns` / `source_refs` 全部保持不变（向后兼容：现有 23 张卡无 `updates` 字段也合法）。

### 1.2 字段定义

```json
{
  "properties": {
    "updates": {
      "type": "array",
      "description": "v2.1+ append-only update entries；每张卡在多轮 update 后累积。无此字段或空数组都合法",
      "items": {
        "type": "object",
        "required": ["updated_at", "patch_reasoning"],
        "additionalProperties": false,
        "properties": {
          "updated_at":         { "type": "string", "format": "date" },
          "patch_reasoning":    { "type": "string", "maxLength": 200 },
          "crystallization": {
            "type": "object",
            "additionalProperties": false,
            "description": "本次新增的三层文本，全部可选；空对象等价于本次未补三层文本",
            "properties": {
              "mechanism":   { "type": "string", "minLength": 30, "maxLength": 200 },
              "anchor":      { "type": "string", "minLength": 4, "maxLength": 20 },
              "micro_steps": { "type": "array", "minItems": 1, "maxItems": 3, "items": { "type": "string", "minLength": 5, "maxLength": 60 } }
            }
          },
          "patterns_added": {
            "type": "array",
            "items": { "enum": ["P-EVAL","P-OVER","P-SPIRAL","P-EFF","P-UNDER","P-EXIST","P-KNOW-DO","P-FAMILY"] }
          },
          "source_refs_added": {
            "type": "array",
            "items": { "type": "string" }
          },
          "questions_appended": {
            "type": "array",
            "items": { "type": "string", "minLength": 4 }
          },
          "trigger_addendum": { "type": "string" }
        }
      }
    }
  }
}
```

把上面块插入 `properties` 里（与 `created_at` 平级）。注意 `additionalProperties: false` 是 root 层既有的——不要破坏。

### 1.3 验收

- `python3 tools/validate_chains_json.py` 对现有 23 张卡仍 pass（向后兼容）
- 手写一张含 `updates: [{...}]` 的临时卡，schema validate 通过

## 2. `round2/run_pipeline.py` — 增 `--mode update`

### 2.1 命令形态

```bash
./venv/bin/python3 round2/run_pipeline.py merge \
    --b <update_entry_json> \
    --judge <judge_json> \
    --mode update \                # ← 新增；默认 new 保持现行为
    [--dry-run]
```

- `--mode new`（默认，**不传也是 new**）：完全沿用现行逻辑（写新卡到 v3 md → export）
- `--mode update`：走新逻辑（append update_entry 到现有卡）

**注意**：保持 `merge` 子命令不变，**新增**一个 `--mode` 选项，**不**破坏现有 `--mode new`（默认）行为。

### 2.2 update 路径行为

伪代码：

```python
def cmd_merge(args):
    ...
    judge = json.loads(j_path.read_text())
    if judge.get("verdict") != "pass":
        raise SystemExit(2)

    b_obj = json.loads(b_path.read_text())
    b_obj = _strip_card_payload(b_obj)  # 剥 _meta

    if args.mode == "new":
        ...原有逻辑...
        return

    # --- mode == "update" ---
    if b_obj.get("output_kind") != "update_entry":
        print(f"[merge] mode=update but b output_kind={b_obj.get('output_kind')!r}", file=sys.stderr)
        raise SystemExit(1)

    target_id = b_obj["target_ic_id"]
    update_entry = b_obj["update_entry"]

    # 校验 update_entry 子 schema（用 schema 的 updates.items 片段独立校验）
    _validate_update_entry(update_entry, schema)

    # 读 chains.json 找原卡（注意：chains.json 是 export 的产物——下面 §3 解决"如何回写"的问题）
    # 因为 export_v3_chains.py 是从 v3 md 全量重生 chains.json 的，所以 update 入口仍是改 v3 md
    # → §3 详述 v3 md 里如何挂载 updates；这里只负责"把 update_entry 写进 v3 md 对应卡的 updates 段"

    md = md_path.read_text()
    new_md = _append_update_entry_in_md(md, target_id, update_entry)
    if new_md == md:
        print(f"[merge] {target_id} not found in v3 md or update段插入失败; abort", file=sys.stderr)
        raise SystemExit(6)  # new exit code: target_not_found

    if args.dry_run:
        print("[merge] --dry-run: would inject update entry; diff:", file=sys.stderr)
        # print diff between md and new_md (or just print update entry markdown)
        return

    md_path.write_text(new_md, encoding="utf-8")
    print(f"[merge] appended update_entry to {target_id} in {md_path}", file=sys.stderr)

    # 触发 export → chains.json + chains.data.js
    r = subprocess.run([sys.executable, str(export_script), "--md", str(md_path)], cwd=str(root))
    if r.returncode != 0:
        raise SystemExit(r.returncode)

    print(f"✓ update 已入库: {target_id}（updates[{N}]）")
    print(f"  UI: file://{proto.resolve()}")
```

### 2.3 新 exit code

| Exit | 含义 |
|---|---|
| 6 | mode=update 时找不到 target_ic_id 对应的卡（v3 md 里没有 `### IC-NNN：` 段） |
| 7 | mode=update 时 update_entry 子 schema 校验失败 |

记得在 `push.prompt.md` §3 表格里加这两行（push 改动小，不必再来一次 plan）。

### 2.4 `_append_update_entry_in_md(md, target_id, entry)`

需要在 v3 md 里找到目标卡（按 `### IC-NNN：` heading），在该卡 markdown 块**内部**追加 update 子块。具体 md 模板见 §3.2。

定位策略（基于现行 `_card_to_markdown` 的格式）：

```
### IC-012：xxx
... (原卡 markdown) ...
----     ← 卡分隔符（已存在）
```

`updates` 段插在该卡的 `----` **之前**：

```
### IC-012：xxx
... (原卡 markdown) ...

<details>
<summary>更新 2026-05-15</summary>

机制（更新）：xxxx

入口句（更新）：

> 先睡，憋醒了再起。

小动作（更新）：

1. ...
2. ...

新增 patterns：`P-EFF` `P-KNOW-DO`
新增 source_refs：B14 B10 B13
追加问题：
- ...
trigger 补充：仅在学校发生……

> patch_reasoning: …

</details>

----
```

实现：用正则或简单字符串匹配定位 `### {target_id}：` 与下一个 `### IC-` 或 EOF，在该段最后一个 `----` 之前插入 update markdown 段。**注意**：要处理"该卡已有若干 update 段"的情况——按 updates 数组顺序串接即可。

### 2.5 验收

- mode=new 默认行为完全不变（回归原有 dogfood case）
- mode=update 跑一次 IC-012 的 update_entry，v3 md 里出现新的 `<details><summary>更新 2026-05-15</summary>...` 段
- export 后 chains.json 里 IC-012 多了 `updates: [{...}]` 字段
- prototype 刷新看到原卡 + 折叠更新历史

## 3. `tools/export_v3_chains.py` — v3 md ↔ chains.json 双向支持 updates

### 3.1 当前行为速记

`export_v3_chains.py` 从 v3 md 解析 23 张卡，全量重写 `data/chains.json` + `crystallization-prototype/chains.data.js`。**所以 update 的真相在 v3 md**，chains.json 是派生物。

### 3.2 v3 md 里 update 段的标准格式

为可解析，约定如下（一张卡可有 0..N 个 update 段，都用 `<details>` 包裹）：

```markdown
### IC-012：标题

**Crystallization**

机制：原 mechanism

入口句：

> 原 anchor

小动作：

1. 原 step 1
2. 原 step 2
3. 原 step 3

**Pattern tags**：`P-X` `P-Y`

**Axis**：`attention`

**Source refs**：H05 F10

<details>
<summary>Trigger / 追问路径</summary>
... 既有的 trigger / questions 折叠 ...
</details>

<!-- BEGIN UPDATES -->

<details class="ic-update">
<summary>更新 2026-05-15</summary>

> patch_reasoning：本次新增 context-bound 因果 + state-vs-content 元层……

**新增机制**：你只在学校这样——是因为学校把控制感切薄了……

**新增入口句**：

> 先睡，憋醒了再起。

**新增小动作**：

1. 想刷新时先做 3 次延长呼气（呼比吸长一倍）
2. 把脑中的念头写一句到手机备忘录，再决定要不要做

**新增 patterns**：`P-EFF` `P-KNOW-DO`

**新增 source_refs**：B14 B10 B13

**追加问题**：

- 我完全可以先睡，被憋醒了再去上厕所。
- 调整状态吧，告诉自己进入那个感受的 state。

**trigger 补充**：仅在学校发生——回家则无；床上学习让『床＝休息』的物理锚被污染。

</details>

<!-- END UPDATES -->

----
```

`<!-- BEGIN UPDATES -->` / `<!-- END UPDATES -->` 注释对解析友好；如某卡无 updates，整段省略（不产生空注释对）。

### 3.3 export 解析逻辑

- 现有 parser 已切分到 `### IC-NNN：` 段；在该段内额外扫描 `<!-- BEGIN UPDATES -->` ~ `<!-- END UPDATES -->` 之间所有 `<details class="ic-update">` 块
- 每个块按上面 3.2 模板字段解析为 update_entry dict
- 写到 chains.json 对应卡的 `updates` 数组（按 md 出现顺序）

### 3.4 export 写回逻辑（merge 不直接调用）

merge 只追加 md（§2.4 已写）；export 只负责"读 md 全量重生 chains.json"。两侧职责清晰，不互相调用。

### 3.5 验收

- 现有 23 张卡无 updates 段——export 后 chains.json 里 `updates` 字段缺省（或空数组），向后兼容
- 手动给 IC-012 的 v3 md 加一个 `<!-- BEGIN UPDATES -->...<!-- END UPDATES -->` 段，re-export → chains.json 出现 `updates: [{...}]`

## 4. `tools/validate_chains_json.py`

- 此工具读 schema 校验 chains.json，schema 改动后自动覆盖新字段
- **不用改代码**；但建议增加一行 lint：若某卡有 `updates` 数组，提示"该卡有 N 个 update 历史"（friendly 日志）

## 5. Prototype UI（`crystallization-prototype/`）

### 5.1 数据流

- `chains.data.js` 由 export 自动生成；每张卡 object 可能含 `updates: [...]`
- UI 在 card 详情区原卡正面下方渲染折叠"更新历史 (N)" 块

### 5.2 渲染规则

- 卡正面：原 mechanism / anchor / micro_steps（始终展开显示）
- 若 `card.updates && card.updates.length > 0`：
  - 在正面下方加按钮 `[ ⬇ 更新历史 (${updates.length}) ]`
  - 点击展开列表：每个 update_entry 一张子卡
    - 顶部小字：`更新 ${updated_at}`
    - `> patch_reasoning`（引用块样式）
    - 若有 `crystallization.mechanism` → `**新增机制**：${...}`
    - 若有 `crystallization.anchor` → `**新增入口句**：${...}`
    - 若有 `crystallization.micro_steps` → 有序列表
    - `patterns_added` → tag 列表，区别配色（如绿色边框 vs 原 patterns 灰）
    - `source_refs_added` → 小字脚注
    - `questions_appended` → "追加问题" 列表
    - `trigger_addendum` → "trigger 补充"

### 5.3 检索

- 现有检索逻辑（按 patterns / axis / anchor / mechanism 关键字）应**同时**搜 updates 内文本——一个 update 的 mechanism 也能被检索命中并定位到原卡
- 命中 update 内容时，UI 默认自动展开该卡的更新历史

### 5.4 验收

- `python3 -m http.server` 起站，打开 IC-012 看到：原卡正面 + 折叠"更新历史 (1)"
- 检索关键词"先睡，憋醒了"能命中 IC-012（来自 update 内容）

## 6. 回归 dogfood

跑一遍 IC-012 的 update 全链路：

1. `agent第二轮/runtest/run_2026-05-15_pipeline-a_school-control.json` 已有；按 v2.3 改一下 update_directives 措辞（去掉"保留 X"语义）
2. 重跑 B v2.1：输出 `agent第二轮/runtest/run_2026-05-15_pipeline-b_school-control_v2.json`（output_kind=update_entry）
3. 跑 Judge：verdict=pass
4. 跑 push：`./venv/bin/python3 round2/run_pipeline.py merge --b ... --judge ... --mode update`
5. 浏览器刷新 prototype，确认 IC-012 卡面：原卡正面不变 + 折叠"更新历史 (1)" 显示本次新增层

## 7. 配套同步：`agent第二轮/judge.prompt.md`（prompt，不是代码；composer 不必动，但要让用户知道）

> **本次未改 judge.prompt.md**——因为用户本轮的 context curation 范围限定在 `pipeline-a-diagnose.prompt.md` / `pipeline-b-style.prompt.md` / `push.prompt.md`。但 judge 当前仍按 `output_kind=patch` + 旧 patch 字段（`alt_anchors` / `crystallization.anchor` 点路径 / `array_full_replacement` / `anchor_alt_handling` 等）做 route-aware 检查——append-only 切换后会全军覆没。

### 7.1 需要改的字段（参考 judge.prompt.md 内 §5.7、Example 2、Example 3）

| judge 内位置 | 旧 patch 语义 | 新 update_entry 语义 |
|---|---|---|
| frontmatter `output_kind` enum | `[full_card, patch, meta_card]` | `[full_card, update_entry, meta_card]` |
| `existing_card_json` 描述 | "patch 的基准卡" | "原卡（read-only 历史资产）" |
| §5.7 route-aware checks（route=update） | `patch_scope` / `patch_no_directive_leak` / `array_full_replacement` / `anchor_alt_handling` / `created_at_preserved` / `updated_at_today` | 替换为：`update_entry_scope`（字段只在 update_entry 子对象内 / 未塞 id/title/patterns 等原卡字段）/ `update_entry_no_directive_leak`（值是最终文本不是 directive 元语言）/ `append_arrays_delta_only`（patterns_added / source_refs_added / questions_appended 是 delta，**不是**完整新数组）/ `mechanism_independent`（update_entry.crystallization.mechanism 是独立新层，没复制原 mechanism）/ `original_untouched`（id/title/原 crystallization/原 chain 一字未动） |
| §6 评分流程 | "把 patch 应用在 existing_card_json 上得到合并后卡再打分" | "把 update_entry append 到 existing_card_json.updates 末尾，对**整张累积卡**打分；同时单独看 update_entry 自身的良质（机制独立性 / anchor 与原 anchor 的张力 / steps 与原 steps 的互补性）" |
| Example 2 / Example 3 | output_kind=patch 的全样例 | 改写为 output_kind=update_entry 的样例 |

### 7.2 建议处理顺序

- composer 完成 §1-§5 代码改动后，跑 dogfood 时 judge 一旦报"按 patch 规则评 update_entry 全 fail"——这是预期信号，**不是 bug**
- 此时由用户（或下一轮 prompt iteration）单独迭代 judge.prompt.md 到 v2.1，与 B v2.1 / A v2.3 对齐
- 在 judge 迭代完之前，dogfood 可以**跳过 judge 自动评分**，由用户手动看 update_entry + 原卡合并后的整张卡是否合用

## 8. 风险与回退

- **回退**：`--mode new` 默认值保持不变；schema 的 `updates` 是 optional——回退仅需 `git revert` 本批 commit，已写入的 v3 md updates 段会被下一次 export 全量重生时按"无 updates parser"忽略（如果 parser 也被 revert）；如果不 revert parser，老 chains.json 仍带 updates 字段，prototype 即使没渲染逻辑也只是"看不到"，不会崩
- **核心风险**：`_append_update_entry_in_md` 的字符串定位脆弱——v3 md 模板若被人手编辑过会失败。**保险措施**：mode=update 失败时只打 stderr，不写文件（用临时 path + rename 模式）
- **不在本 plan 范围**：route=meta 的 `--mode meta`、批量多卡 push、SDK/API 模式（push.prompt.md §未来 code+api 备忘）——独立任务

## 9. 实施顺序建议

```
§1 (schema)  →  §3.2/3.3 模板与 parser  →  §3.5 验收
                            ↓
                §2 (run_pipeline.py merge --mode update)  →  §2.5 验收
                            ↓
                §5 (prototype UI)  →  §5.4 验收
                            ↓
                §6 dogfood 全链路
```

`§3` 与 `§2` 可并行——但 §3 的 md 模板要先冻结，§2 才能确定怎么写。
