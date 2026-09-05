#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${HOME}/.local/share/orvani-share"
APP="${RUNTIME}/app"
USER_BIN="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
CONFIG_DIR="${HOME}/.config/orvani-share"
ENV_FILE="${CONFIG_DIR}/share.env"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 não encontrado." >&2
  exit 1
}

mkdir -p "${APP}" "${USER_BIN}" "${SYSTEMD_DIR}" "${CONFIG_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  PIN="$(
    python3 -c 'import secrets; print(f"{secrets.randbelow(100000000):08d}")'
  )"
  SESSION_SECRET="$(
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  )"
  umask 077
  {
    printf 'ORVANI_SHARE_PIN=%s\n' "${PIN}"
    printf 'ORVANI_SHARE_SESSION_SECRET=%s\n' "${SESSION_SECRET}"
  } > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
else
  chmod 600 "${ENV_FILE}"
fi

set -a
source "${ENV_FILE}"
set +a

if [[ ! "${ORVANI_SHARE_PIN:-}" =~ ^[0-9]{8}$ ]]; then
  echo "ORVANI_SHARE_PIN inválido em ${ENV_FILE}." >&2
  exit 1
fi
if [[ ! "${ORVANI_SHARE_SESSION_SECRET:-}" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo "ORVANI_SHARE_SESSION_SECRET inválido em ${ENV_FILE}." >&2
  exit 1
fi

rm -rf "${APP}/share_center"
cp -a "${ROOT}/share_center" "${APP}/share_center"

install -m 0755 \
  "${ROOT}/scripts/orvani-share-launcher.sh" \
  "${USER_BIN}/orvani-share-launcher"
install -m 0755 \
  "${ROOT}/scripts/orvani-share-access.sh" \
  "${USER_BIN}/orvani-share-access"
install -m 0644 \
  "${ROOT}/systemd/orvani-share.service" \
  "${SYSTEMD_DIR}/orvani-share.service"

if [[ -f "${RUNTIME}/state.json" ]]; then
  chmod 600 "${RUNTIME}/state.json"
fi

systemctl --user daemon-reload
systemctl --user enable orvani-share.service
systemctl --user restart orvani-share.service

echo
echo "Central atualizada com acesso protegido pela rede local."
"${USER_BIN}/orvani-share-access"
