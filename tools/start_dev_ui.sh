#!/usr/bin/env bash
# 统一开发台：主站 + Inbox + Context 审阅 + feedback API（单端口）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec ./venv/bin/python3 tools/feedback_server.py \
  --port "${PORT:-8765}" \
  --open \
  --open-page /dev-hub.html \
  --refresh-all \
  "$@"
