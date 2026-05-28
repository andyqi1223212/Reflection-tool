# Examples

A synthetic conversation and the real pipeline outputs it produces. Use this to verify your installation works.

## Files

- **[sample-conversation.md](sample-conversation.md)** — a fully synthetic conversation (not from any real dialogue, see frontmatter)
- **[sample-run/a.json](sample-run/a.json)** — Pipeline A output: extracted trigger / axis / pattern diagnosis
- **[sample-run/b.json](sample-run/b.json)** — Pipeline B output: the crystallized card (mechanism + anchor + micro_steps)
- **[sample-run/judge.json](sample-run/judge.json)** — Judge verdict and scores

## Reproduce

```bash
# Make sure .env has DEEPSEEK_API_KEY
./venv/bin/python3 -m agents_runtime.orchestrate examples/sample-conversation.md
```

Output appears under `runs/<timestamp>_*/`. The exact JSON won't match `sample-run/` byte-for-byte (LLMs are non-deterministic), but the **structure** and **quality bar** should be similar:

- `a.json` should diagnose `axis` as `attention` (knowledge-action gap on self-organization), not `judgment`
- `b.json` should produce a card with `mechanism` reframing "willpower" as something else, a short `anchor` (≤20 chars), and 3 concrete `micro_steps`
- `judge.json` should return `verdict: "pass"` with scores ≥ 4 across the board

## Reading the outputs

The pipeline is a 4-stage flow: **A** (diagnose) → **B** (style) → **Judge** (verify) → **push** (merge into your card library).

| Stage | What it does | Input | Output |
|---|---|---|---|
| route_helper | Decides if this is a new card or update to existing | the .md file | `route_helper.json` |
| **A** | Extracts trigger / axis / patterns / mechanism sketch | route_helper + .md | `a.json` |
| **B** | Writes the crystallized card following style lexicon | a.json | `b.json` |
| **Judge** | Scores the card; returns pass/fail/revise verdict | b.json + a.json | `judge.json` |
| push | Appends to your `inquiry-chain-starter.md` (or your own SSOT) and re-exports | b.json | merged into SSOT |

See [`agentflow3-tocode/codemap-agentflow.md`](../agentflow3-tocode/codemap-agentflow.md) for the full architecture.
