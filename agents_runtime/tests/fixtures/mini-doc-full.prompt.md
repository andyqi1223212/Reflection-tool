---
agent_id: mini-doc-full
version: v0
model_tier: plumbing
inputs:
  - { name: lexicon, type: doc_full, source: "agents_runtime/tests/fixtures/mini-lexicon.md", required: true }
outputs:
  - { name: out, type: json }
forbidden_inputs:
  - "外部source/*.md"
single_responsibility: "fixture for doc_full input type"
---

## Body

Mini doc_full fixture.
