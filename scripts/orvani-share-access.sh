#!/usr/bin/env bash
set -euo pipefail

CONFIG="${HOME}/.config/orvani-share/share.env"

if [[ ! -r "${CONFIG}" ]]; then
  echo "Configuração de acesso não encontrada: ${CONFIG}" >&2
  exit 1
fi

set -a
source "${CONFIG}"
set +a

if [[ ! "${ORVANI_SHARE_PIN:-}" =~ ^[0-9]{8}$ ]]; then
  echo "PIN local inválido." >&2
  exit 1
fi

echo "Orvani — Central de Divulgação"
echo "Notebook: http://127.0.0.1:8765"
echo "Celular na mesma rede Wi-Fi:"

python3 - <<'PY'
import ipaddress
import subprocess

addresses = set()

try:
    output = subprocess.check_output(
        ["hostname", "-I"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
except (OSError, subprocess.CalledProcessError):
    output = ""

for token in output.split():
    try:
        address = ipaddress.ip_address(token)
    except ValueError:
        continue
    if address.version != 4 or address.is_loopback:
        continue
    allowed = (
        address in ipaddress.ip_network("10.0.0.0/8")
        or address in ipaddress.ip_network("172.16.0.0/12")
        or address in ipaddress.ip_network("192.168.0.0/16")
        or address in ipaddress.ip_network("169.254.0.0/16")
    )
    if allowed:
        addresses.add(str(address))

if not addresses:
    print("  (nenhum IPv4 privado detectado agora)")
else:
    for address in sorted(addresses):
        print(f"  http://{address}:8765")
PY

echo "PIN: ${ORVANI_SHARE_PIN}"
echo
echo "Use o PIN somente em dispositivos seus e na mesma rede privada."
