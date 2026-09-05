#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${HOME}/.local/share/orvani-share"
APP="${RUNTIME}/app"
USER_BIN="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
command -v python3 >/dev/null 2>&1 || { echo "python3 não encontrado." >&2; exit 1; }
mkdir -p "${APP}" "${USER_BIN}" "${SYSTEMD_DIR}"
rm -rf "${APP}/share_center"
cp -a "${ROOT}/share_center" "${APP}/share_center"
install -m 0755 "${ROOT}/scripts/orvani-share-launcher.sh" "${USER_BIN}/orvani-share-launcher"
install -m 0644 "${ROOT}/systemd/orvani-share.service" "${SYSTEMD_DIR}/orvani-share.service"
if [[ -f "${RUNTIME}/state.json" ]]; then chmod 600 "${RUNTIME}/state.json"; fi
systemctl --user daemon-reload
systemctl --user enable --now orvani-share.service
echo "Central instalada em http://127.0.0.1:8765"
