#!/usr/bin/env bash
# 已整合到仓库根统一开发台；本脚本转发，避免再起第二个 http.server
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "Context 审阅器已并入单端口开发台，正在启动…" >&2
echo "  审阅页: http://127.0.0.1:\${PORT:-8765}/context-curator/" >&2
exec "$ROOT/tools/start_dev_ui.sh" "$@"
