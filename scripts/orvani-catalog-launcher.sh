#!/usr/bin/env bash
set -euo pipefail

PROFILE="${HOME}/.local/share/orvani-sync/libreoffice-profile"
ENV_FILE="${HOME}/.config/orvani-sync/orvani.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Configuração Orvani não encontrada: ${ENV_FILE}" >&2
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

: "${ORVANI_WORKBOOK_PATH:?ORVANI_WORKBOOK_PATH não configurado}"

mkdir -p "${PROFILE}"
PROFILE_URI="$(
  python3 -c \
    'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())' \
    "${PROFILE}"
)"

exec /usr/bin/libreoffice \
  "-env:UserInstallation=${PROFILE_URI}" \
  '--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext' \
  --nodefault \
  --norestore \
  --nofirststartwizard \
  "${ORVANI_WORKBOOK_PATH}"
