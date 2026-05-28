# 环境与 CLI（plan §4.3 + §1）

## 环境变量

与 plan §4.3 一致（**不**自动写入用户 `.env`）：

```bash
# 必填（真跑 A/B/Judge）
DEEPSEEK_API_KEY=sk-...

# 可选（缺省由代码 fallback，当前默认 v4）
DEEPSEEK_REASONING_MODEL=deepseek-v4-pro    # A、Judge
DEEPSEEK_CHAT_MODEL=deepseek-v4-flash        # B
```

## Pipeline A 与 route_helper（必读）

`pipeline-a-diagnose.prompt.md` 把 `route_helper_output` 标为 **required**，`failure_mode` 规定：调用方未提供时须输出 `{"status": "missing_route_helper", ...}`。  
因此只执行 `run_a <question.md>`（不传路由 JSON）时，模型**按契约**返回该状态，**不是程序坏了**。

**两步行：**

```bash
./venv/bin/python3 round2/route_helper.py \
  --question 外部source/球场垃圾话应对策略.md \
  --top-k 5 \
  --include-raw-answer-excerpt > /tmp/route_helper.json

./venv/bin/python3 -m agents_runtime.agents run_a \
  外部source/球场垃圾话应对策略.md \
  /tmp/route_helper.json
```

`llm_client` 在首次调用前从 **仓库根** 依次尝试 `load_dotenv`：`.env.local`、`.env`、`.env.example`（与 `tools/llm_api.py` 行为对齐，但不依赖其 import 时 cwd）。

**运行体感（2026-05-19 E2E）**：`run_a` 在打印 JSON 前可能 **1～数分钟** 无终端输出（长 system + v4-pro 思考），属正常；失败时看 stderr 或 `agents_runtime/_stats/parse_stats.jsonl`、`_debug/parse_fail_*.txt`。

## Python 依赖

- `openai`（已有）
- `pyyaml`（本 Phase 已 `pip install`，用于 `yaml.safe_load` 解析 frontmatter）
- `python-dotenv`（仓库已有）

## CLI

在**仓库根**执行（保证相对路径与 `.env` 解析正确）：

```bash
# A：第二个参数为 route_helper  stdout 存成的 JSON（见上一节）
./venv/bin/python3 -m agents_runtime.agents run_a \
  外部source/球场垃圾话应对策略.md \
  /tmp/route_helper.json

# B（读入 A 的 JSON；可选第二个文件为 existing_card，仅 route=update）
./venv/bin/python3 -m agents_runtime.agents run_b agents/runs/run_2026-05-11_pipeline-a_ball-trash-talk.json

# Judge
./venv/bin/python3 -m agents_runtime.agents run_judge \
  agents/runs/run_2026-05-12_pipeline-b_ball-trash-talk.json \
  agentflow3-tocode/phase1产出/route_context.example.new.json
```

可选：`--debug-dir /path` 指定 JSON 解析失败时落盘目录（默认当前工作目录下的 `_debug/`）。

## 编程接口（plan §8.1）

```python
from agents_runtime import run_a, run_b, run_judge
import json

with open("/tmp/route_helper.json", encoding="utf-8") as f:
    rh = json.load(f)
a_out = run_a("外部source/球场垃圾话应对策略.md", route_helper_output=rh, fewshot=[])
```

`Prompt` / `build_context` / `call_json` 不列入公开 API（plan §8.3）。
