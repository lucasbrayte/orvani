#!/usr/bin/env bash
set -euo pipefail

VENV="${HOME}/.local/share/orvani-sync/venv"
APP="${HOME}/.local/share/orvani-sync/app"
ENV_FILE="${HOME}/.config/orvani-sync/orvani.env"

set -a
source "${ENV_FILE}"
set +a

export PYTHONPATH="${APP}"

exec "${VENV}/bin/python" -m libreoffice_sync.main run
