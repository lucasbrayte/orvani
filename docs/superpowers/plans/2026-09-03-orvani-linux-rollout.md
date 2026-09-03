# Orvani LibreOffice Linux Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install, start, and verify the LibreOffice synchronization stack on the user's Linux desktop and prove one real product flows Calc → Importações → pending → Produtos → site with status returning to Calc.

**Architecture:** A `systemd --user` service runs a launcher that ensures LibreOffice starts with a loopback UNO listener before starting the Python sync client. An installer creates a dedicated venv with `--system-site-packages` so distro `python3-uno` is visible, installs only `requirements-libreoffice.txt`, writes a permission-restricted local environment file, installs the user service, and leaves Apps Script secret/deployment setup as explicit operator steps.

**Tech Stack:** Linux, LibreOffice Calc, `python3-uno`, Python venv, systemd user units, Bash, existing GitHub Actions/Google Sheets workflow.

**Spec:** `docs/superpowers/specs/2026-09-03-libreoffice-orvani-sync-design.md`

## Global Constraints

- Computer need not remain on after Google Sheets acknowledges an upload.
- Local config is `~/.config/orvani-sync/orvani.env` with mode `0600`.
- Local runtime must not contain `GITHUB_TOKEN` or Google service-account JSON.
- UNO listens only on `127.0.0.1:2002`.
- The service starts with the user graphical session.
- The normal user workflow remains: open `Orvani.ods`, edit, `Ctrl + S`.
- Initial rollout uses one controlled test product before normal catalog use.
- Existing Google Sheets/Apps Script/GitHub automation remains the cloud backbone.

---

### Task 1: Add the systemd launcher and user service

**Files:**
- Create: `scripts/orvani-sync-launcher.sh`
- Create: `systemd/orvani-sync.service`
- Create: `tests/test_linux_service_files.py`

**Interfaces:**
- Consumes: installed local venv at `%h/.local/share/orvani-sync/venv`.
- Produces: loopback UNO listener and `python -m libreoffice_sync.main run`.

- [ ] **Step 1: Write failing service-file tests**

```python
def test_systemd_service_uses_user_paths():
    text = Path("systemd/orvani-sync.service").read_text()
    assert "ExecStart=%h/.local/bin/orvani-sync-launcher" in text
    assert "WantedBy=default.target" in text
    assert "GITHUB_TOKEN" not in text
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in text


def test_launcher_binds_uno_to_loopback_only():
    text = Path("scripts/orvani-sync-launcher.sh").read_text()
    assert "host=127.0.0.1,port=2002" in text
    assert "0.0.0.0" not in text
```

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q tests/test_linux_service_files.py
```

Expected: FAIL because files are absent.

- [ ] **Step 3: Implement launcher**

Use:

```bash
#!/usr/bin/env bash
set -euo pipefail

VENV="${HOME}/.local/share/orvani-sync/venv"
ENV_FILE="${HOME}/.config/orvani-sync/orvani.env"

set -a
source "${ENV_FILE}"
set +a

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
```

The login-time service should normally start this LibreOffice process before the user opens Calc, so later `libreoffice Orvani.ods` joins the same profile process with UNO enabled.

- [ ] **Step 4: Implement user service**

```ini
[Unit]
Description=Orvani LibreOffice catalog sync
After=graphical-session.target network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=%h/.local/bin/orvani-sync-launcher
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

- [ ] **Step 5: Run tests and shell syntax check**

```bash
python3 -m pytest -q tests/test_linux_service_files.py
bash -n scripts/orvani-sync-launcher.sh
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/orvani-sync-launcher.sh systemd/orvani-sync.service \
  tests/test_linux_service_files.py
git commit -m "feat: add Linux sync service"
```

---

### Task 2: Add a safe Linux installer

**Files:**
- Create: `scripts/install-orvani-sync.sh`
- Modify: `tests/test_linux_service_files.py`
- Create: `docs/orvani-libreoffice-linux.md`

**Interfaces:**
- Produces:
  - runtime copy under `~/.local/share/orvani-sync`
  - launcher under `~/.local/bin/orvani-sync-launcher`
  - env file under `~/.config/orvani-sync/orvani.env`
  - user unit under `~/.config/systemd/user/orvani-sync.service`.

- [ ] **Step 1: Add installer-content tests**

```python
def test_installer_requires_linux_uno_packages():
    text = Path("scripts/install-orvani-sync.sh").read_text()
    assert "python3-uno" in text
    assert "libreoffice" in text
    assert "--system-site-packages" in text
    assert "chmod 600" in text
```

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q tests/test_linux_service_files.py
```

Expected: FAIL because installer is absent.

- [ ] **Step 3: Implement prerequisite checks**

The installer must fail with explicit Ubuntu/Debian guidance when commands/imports are missing:

```text
sudo apt install libreoffice python3-uno python3-venv
```

Do not run `sudo` automatically.

- [ ] **Step 4: Implement runtime installation**

Use:

```bash
python3 -m venv --system-site-packages "${HOME}/.local/share/orvani-sync/venv"
"${HOME}/.local/share/orvani-sync/venv/bin/pip" install \
  -r requirements-libreoffice.txt
```

Copy the `libreoffice_sync` package into `${HOME}/.local/share/orvani-sync/app/` and install it by adding that app directory to the service `PYTHONPATH`, or install the repository editable into the venv. Choose editable installation only when the repo remains at a stable path; for the user's normal installation, copy the package and export:

```bash
export PYTHONPATH="${HOME}/.local/share/orvani-sync/app"
```

from the launcher.

- [ ] **Step 5: Create local config securely**

If the env file does not exist, generate:

```bash
SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Write:

```text
ORVANI_WEBAPP_URL=
ORVANI_SYNC_SECRET=<generated 64-hex secret>
ORVANI_WORKBOOK_PATH=<absolute user-selected path>/Orvani.ods
ORVANI_STATUS_POLL_SECONDS=20
ORVANI_UNO_HOST=127.0.0.1
ORVANI_UNO_PORT=2002
```

Then:

```bash
chmod 600 "${ENV_FILE}"
```

Never overwrite an existing secret during reinstall.

- [ ] **Step 6: Install but do not auto-enable before configuration**

Copy files and run:

```bash
systemctl --user daemon-reload
```

Do not enable/start until `ORVANI_WEBAPP_URL` has been populated and the same secret has been set in Apps Script.

- [ ] **Step 7: Write operator documentation**

`docs/orvani-libreoffice-linux.md` must contain exact steps for:
- prerequisites
- running installer
- copying `ORVANI_SYNC_SECRET` into Apps Script Script Properties
- setting `ORVANI_WEBAPP_URL`
- initializing `Orvani.ods`
- health test
- enable/start
- logs with `journalctl --user -u orvani-sync -f`
- disable/uninstall commands.

- [ ] **Step 8: Run tests and syntax checks**

```bash
python3 -m pytest -q tests/test_linux_service_files.py
bash -n scripts/install-orvani-sync.sh
bash -n scripts/orvani-sync-launcher.sh
git diff --check
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/install-orvani-sync.sh scripts/orvani-sync-launcher.sh \
  systemd/orvani-sync.service tests/test_linux_service_files.py \
  docs/orvani-libreoffice-linux.md
git commit -m "feat: install Orvani sync on Linux"
```

---

### Task 3: Perform local installation and authenticated health check

**Files changed in repository:** none expected.
**User-machine files:** `~/.config/orvani-sync/orvani.env`, installed runtime/service files.

**Interfaces:**
- Consumes: deployed Apps Script `/exec` URL and shared `ORVANI_SYNC_SECRET`.
- Produces: successful API + UNO health status before catalog data is touched.

- [ ] **Step 1: Install Linux prerequisites if missing**

Run manually:

```bash
sudo apt install libreoffice python3-uno python3-venv
```

- [ ] **Step 2: Run installer**

```bash
bash scripts/install-orvani-sync.sh
```

Expected: installation succeeds but service is not enabled yet.

- [ ] **Step 3: Configure Apps Script secret**

Read the generated local value without copying it into chat/logs:

```bash
grep '^ORVANI_SYNC_SECRET=' ~/.config/orvani-sync/orvani.env
```

Set that exact value as Script Property `ORVANI_SYNC_SECRET`.

- [ ] **Step 4: Deploy Apps Script and configure Web App URL**

Place the `/exec` URL into:

```bash
nano ~/.config/orvani-sync/orvani.env
```

Set:

```text
ORVANI_WEBAPP_URL=https://script.google.com/macros/s/<deployment>/exec
```

Do not use `/dev`.

- [ ] **Step 5: Start the service once**

```bash
systemctl --user start orvani-sync
systemctl --user status orvani-sync --no-pager
```

Expected: active/running.

- [ ] **Step 6: Run health diagnostic**

```bash
set -a
source ~/.config/orvani-sync/orvani.env
set +a
~/.local/share/orvani-sync/venv/bin/python -m libreoffice_sync.main health
```

Expected:

```text
API: OK
UNO: OK
```

- [ ] **Step 7: Verify no public UNO listener**

```bash
ss -ltnp | grep ':2002'
```

Expected bind address: `127.0.0.1:2002`, never `0.0.0.0` or `[::]`.

---

### Task 4: Initialize the real `Orvani.ods` and verify live status writes

**Files changed in repository:** none expected.
**User artifact:** the real `Orvani.ods`.

- [ ] **Step 1: Initialize workbook**

With service/UNO listener running:

```bash
set -a
source ~/.config/orvani-sync/orvani.env
set +a
~/.local/share/orvani-sync/venv/bin/python -m libreoffice_sync.main init-workbook
```

Expected: workbook saved at `ORVANI_WORKBOOK_PATH`.

- [ ] **Step 2: Open it normally**

```bash
libreoffice "$ORVANI_WORKBOOK_PATH"
```

Expected: `Catálogo` visible; AB:AH hidden; dropdowns present.

- [ ] **Step 3: Enter a local-invalid test row**

Enter `Manual`, `Publicar=Sim`, but leave `Preço Atual` empty; press `Ctrl + S`.

Expected in the open Calc document:
- W: `ERRO LOCAL`
- X: price-required message
- no new `Importações` row.

- [ ] **Step 4: Correct the row but keep `Publicar=Não`**

Fill all required fields, keep `Publicar=Não`, save.

Expected:
- one `Importações` row with matching hidden `ID Automação`
- no duplicate after a second unchanged save
- status returns to Calc within ~20 seconds.

This is the safe bridge verification before actual publication.

---

### Task 5: Run one full real-product publication

**Files changed in repository:** none expected.

- [ ] **Step 1: Choose one controlled test product**

Use a valid product whose direct product URL, affiliate URL, price, image, category, and description are known. Use `Modo Atualização=Manual`.

- [ ] **Step 2: Save with `Publicar=Sim`**

Press `Ctrl + S` once.

Expected flow:

```text
Calc save
→ one Importações upsert
→ one pending workflow dispatch
→ one Produtos create/update
→ backend PUBLICADO
→ Calc W/X update within ~20 seconds
```

- [ ] **Step 3: Verify GitHub Actions**

Confirm the latest `Sync affiliate catalog` workflow:
- event: `workflow_dispatch`
- mode: `pending`
- `produtos_planejados=1`
- `estados=PUBLICADO:1`.

- [ ] **Step 4: Verify Sheets identity**

Confirm:
- `Importações` `ID Automação` equals hidden AB in Calc.
- Exactly one matching `Importações` row exists.
- `Produtos` contains one matching publication.
- Saving unchanged Calc content again causes no duplicate and no unnecessary publication rewrite.

- [ ] **Step 5: Verify site**

Wait for the existing frontend refresh interval or force-refresh the browser. Confirm the product is visible and the button uses the affiliate URL.

- [ ] **Step 6: Verify status return**

Without closing Calc, confirm W:AA show the backend publication status/message/timestamps.

---

### Task 6: Enable automatic startup and restart recovery

**Files changed in repository:** none expected.

- [ ] **Step 1: Enable service**

```bash
systemctl --user enable --now orvani-sync
```

- [ ] **Step 2: Confirm logs are clean**

```bash
journalctl --user -u orvani-sync -n 100 --no-pager
```

Expected: no credential dumps, no rapid restart loop.

- [ ] **Step 3: Test client restart with unsaved backend status**

Stop/start service while Calc is open:

```bash
systemctl --user restart orvani-sync
```

Expected: it reconnects and resumes status polling.

- [ ] **Step 4: Test offline retry semantics**

Temporarily disconnect network, edit/save one valid row, then restore network.

Expected:
- acknowledged hash does not advance while upload fails
- after connectivity returns, the changed row is retried
- only one `Importações` row exists for its ID.

- [ ] **Step 5: Test cloud independence**

Save a valid changed row and wait until the Apps Script upsert is acknowledged. Then stop the local service:

```bash
systemctl --user stop orvani-sync
```

Expected: the already-dispatched cloud pending workflow can still finish publication without the local computer/service.

- [ ] **Step 6: Re-enable after test**

```bash
systemctl --user start orvani-sync
```

Expected: latest backend status returns to Calc.

---

### Task 7: Final verification checkpoint

**Files changed in repository:** only test/doc fixes if verification reveals a defect.

- [ ] **Step 1: Run focused Python tests**

```bash
python3 -m pytest -q \
  tests/libreoffice_sync \
  tests/test_linux_service_files.py \
  tests/test_manual_update_mode.py \
  tests/test_mercado_livre_manual_fallback.py \
  tests/test_shein_manual_fallback.py \
  tests/test_security.py \
  tests/test_product_persistence_verification.py
```

Expected: PASS.

- [ ] **Step 2: Run JS tests**

```bash
node --test tests/js/catalog.test.js tests/js/apps_script_sync.test.js
```

Expected: PASS.

- [ ] **Step 3: Check shell and diff quality**

```bash
bash -n scripts/orvani-sync-launcher.sh
bash -n scripts/install-orvani-sync.sh
git diff --check
git status --short
```

Expected: no syntax/whitespace errors and only intentional changes.

- [ ] **Step 4: Run full Python regression-count check**

```bash
python3 -m pytest -q
```

Expected: no new failures relative to the repository's known baseline. Record exact counts.

- [ ] **Step 5: Commit any verification-only fixes**

If verification required code/test fixes:

```bash
git add <only the verified fix files>
git commit -m "fix: harden LibreOffice sync rollout"
```

If no fixes were necessary, make no empty commit.

---

## Plan Completion Gate

Rollout is complete when the user can log into Linux, open `Orvani.ods`, edit a product, press `Ctrl + S`, see one idempotent `Importações` update and one pending dispatch, see publication in `Produtos`/the site, receive backend status in the still-open Calc document, and restart the service without losing synchronization state.
