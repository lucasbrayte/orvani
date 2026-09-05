#!/usr/bin/env bash
set -euo pipefail

RUNTIME="${HOME}/.local/share/orvani-share"
APP="${RUNTIME}/app"
CONFIG="${HOME}/.config/orvani-share/share.env"

if [[ ! -r "${CONFIG}" ]]; then
  echo "Configuração de acesso não encontrada: ${CONFIG}" >&2
  exit 1
fi

set -a
source "${CONFIG}"
set +a

export PYTHONPATH="${APP}"
export PYTHONUNBUFFERED=1
export ORVANI_SHARE_STATE_PATH="${RUNTIME}/state.json"

exec /usr/bin/python3 -m share_center.server
