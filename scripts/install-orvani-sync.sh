#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${HOME}/.local/share/orvani-sync"
VENV="${RUNTIME}/venv"
APP="${RUNTIME}/app"
CONFIG_DIR="${HOME}/.config/orvani-sync"
ENV_FILE="${CONFIG_DIR}/orvani.env"
USER_BIN="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"

missing=0
command -v libreoffice >/dev/null 2>&1 || missing=1
command -v python3 >/dev/null 2>&1 || missing=1
python3 -c 'import uno' >/dev/null 2>&1 || missing=1

if [[ "${missing}" -ne 0 ]]; then
  echo "Dependências ausentes."
  echo "No Ubuntu/Debian, instale manualmente:"
  echo "  sudo apt install libreoffice python3-uno python3-venv"
  exit 1
fi

mkdir -p "${RUNTIME}" "${APP}" "${CONFIG_DIR}" "${USER_BIN}" "${SYSTEMD_DIR}"

if [[ ! -x "${VENV}/bin/python" ]]; then
  python3 -m venv --system-site-packages "${VENV}"
fi

"${VENV}/bin/pip" install -r "${ROOT}/requirements-libreoffice.txt"

rm -rf "${APP}/libreoffice_sync"
cp -a "${ROOT}/libreoffice_sync" "${APP}/libreoffice_sync"

install -m 0755 \
  "${ROOT}/scripts/orvani-sync-launcher.sh" \
  "${USER_BIN}/orvani-sync-launcher"

install -m 0644 \
  "${ROOT}/systemd/orvani-sync.service" \
  "${SYSTEMD_DIR}/orvani-sync.service"

if [[ ! -f "${ENV_FILE}" ]]; then
  SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  cat >"${ENV_FILE}" <<EOF
ORVANI_WEBAPP_URL=
ORVANI_SYNC_SECRET=${SECRET}
ORVANI_WORKBOOK_PATH=${HOME}/Documents/Orvani.ods
ORVANI_STATUS_POLL_SECONDS=20
ORVANI_UNO_HOST=127.0.0.1
ORVANI_UNO_PORT=2002
EOF
fi

chmod 600 "${ENV_FILE}"
systemctl --user daemon-reload

echo
echo "Instalação local concluída, mas o serviço NÃO foi habilitado."
echo "Configure agora: ${ENV_FILE}"
echo "Use a mesma ORVANI_SYNC_SECRET na Script Property do Apps Script."
