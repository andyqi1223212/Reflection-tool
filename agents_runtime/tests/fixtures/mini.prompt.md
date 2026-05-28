---
agent_id: mini-test
version: v0
model_tier: plumbing
inputs:
  - { name: question_md, type: markdown_file, required: true }
outputs:
  - { name: out, type: json }
forbidden_inputs:
  - "外部source/*.md"
single_responsibility: "fixture only"
---

## Body

Hello **fixture**.

```json
{"x": 1}
```
