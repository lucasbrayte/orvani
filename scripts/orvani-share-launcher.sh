#!/usr/bin/env bash
set -euo pipefail
RUNTIME="${HOME}/.local/share/orvani-share"
APP="${RUNTIME}/app"
export PYTHONPATH="${APP}"
export PYTHONUNBUFFERED=1
export ORVANI_SHARE_STATE_PATH="${RUNTIME}/state.json"
exec /usr/bin/python3 -m share_center.server
