#!/bin/bash
# First-run bootstrap: create personal-content files from templates so the pipeline can run.
# Safe to re-run — uses `cp -n` (no-clobber); existing files are not overwritten.

set -e
cd "$(dirname "$0")/.."

echo "Bootstrapping personal content files from templates..."

cp -n inquiry-chain-starter.md inquiry-chain-demo-v3-good-answer.md \
    && echo "  ✓ inquiry-chain-demo-v3-good-answer.md (from starter)" \
    || echo "  - inquiry-chain-demo-v3-good-answer.md already exists, skipping"

cp -n context/raw-questions-synthesis.template.md context/raw-questions-synthesis.md \
    && echo "  ✓ context/raw-questions-synthesis.md (from template)" \
    || echo "  - context/raw-questions-synthesis.md already exists, skipping"

cp -n 回答版本explore/良质回答标注册.template.md 回答版本explore/良质回答标注册.md \
    && echo "  ✓ 回答版本explore/良质回答标注册.md (from template)" \
    || echo "  - 回答版本explore/良质回答标注册.md already exists, skipping"

echo ""
echo "Exporting initial chains.json..."
python3 tools/export_v3_chains.py --md inquiry-chain-starter.md

echo ""
echo "Bootstrap done. Next:"
echo "  python -m agents_runtime.orchestrate examples/sample-conversation.md"
