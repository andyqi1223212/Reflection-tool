#!/usr/bin/env bash
# 兼容旧名：转发到统一开发台
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/start_dev_ui.sh" "$@"
