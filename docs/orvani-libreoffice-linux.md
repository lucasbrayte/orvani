# Orvani + LibreOffice no Linux

## Pré-requisitos

```bash
sudo apt install libreoffice python3-uno python3-venv
```

## Instalar

```bash
bash scripts/install-orvani-sync.sh
```

O instalador não habilita o serviço antes da configuração.

## Configurar

```bash
nano ~/.config/orvani-sync/orvani.env
```

Defina `ORVANI_WEBAPP_URL` com a URL `/exec`.

Leia localmente `ORVANI_SYNC_SECRET` e configure o mesmo valor na Script
Property `ORVANI_SYNC_SECRET` do Apps Script. Não envie o segredo por chat.

## Health check

```bash
systemctl --user start orvani-sync
systemctl --user status orvani-sync --no-pager

set -a
source ~/.config/orvani-sync/orvani.env
set +a
~/.local/share/orvani-sync/venv/bin/python -m libreoffice_sync.main health
```

Esperado:

```text
API: OK
UNO: OK
```

Confirme o bind:

```bash
ss -ltnp | grep ':2002'
```

Deve ser `127.0.0.1:2002`.

## Criar Orvani.ods

```bash
set -a
source ~/.config/orvani-sync/orvani.env
set +a
~/.local/share/orvani-sync/venv/bin/python -m libreoffice_sync.main init-workbook
```

Abra:

```bash
libreoffice "$ORVANI_WORKBOOK_PATH"
```

## Habilitar no login

Depois do health check:

```bash
systemctl --user enable --now orvani-sync
```

## Logs

```bash
journalctl --user -u orvani-sync -f
```

## Desabilitar

```bash
systemctl --user disable --now orvani-sync
```
