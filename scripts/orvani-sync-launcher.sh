#!/usr/bin/env bash
set -euo pipefail

VENV="${HOME}/.local/share/orvani-sync/venv"
APP="${HOME}/.local/share/orvani-sync/app"
ENV_FILE="${HOME}/.config/orvani-sync/orvani.env"

set -a
source "${ENV_FILE}"
set +a

export PYTHONPATH="${APP}"

if ! timeout 1 bash -c '</dev/tcp/127.0.0.1/2002' 2>/dev/null; then
  /usr/bin/libreoffice \
    '--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext' \
    --nodefault \
    --norestore \
    --nofirststartwizard \
    >/dev/null 2>&1 &

  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if timeout 1 bash -c '</dev/tcp/127.0.0.1/2002' 2>/dev/null; then
      break
    fi
    sleep 1
  done
fi

exec "${VENV}/bin/python" -m libreoffice_sync.main run
