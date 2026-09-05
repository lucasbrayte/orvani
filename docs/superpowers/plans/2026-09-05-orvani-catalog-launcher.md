# Orvani Catalog Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the visible `Orvani.ods` run in the same dedicated LibreOffice/UNO instance observed by `orvani-sync`, restoring `Ctrl+S` synchronization without blocking normal LibreOffice use.

**Architecture:** `orvani-sync` becomes a service-only Python client that waits for UNO instead of starting LibreOffice. A new visible `Orvani Catálogo` launcher owns the dedicated LibreOffice process, opens the configured workbook with the isolated Orvani profile, and exposes UNO only on `127.0.0.1:2002`.

**Tech Stack:** Bash, Python 3.12, PyUNO/LibreOffice, systemd user services, freedesktop `.desktop` entries, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md`

## Global Constraints

- Keep the dedicated Orvani LibreOffice profile at `~/.local/share/orvani-sync/libreoffice-profile`.
- Keep UNO bound only to `127.0.0.1:2002`; never bind `0.0.0.0`.
- `orvani-sync` must not start a hidden LibreOffice process.
- `Orvani Catálogo` must open the configured `ORVANI_WORKBOOK_PATH` visibly.
- Normal LibreOffice must remain independent.
- `Ctrl+S` / `OnSaveDone` remains the synchronization trigger.
- Preserve the existing Google Sheets / Apps Script API and workbook schema.
- Do not alter Central de Divulgação, discount publication logic, firewall rules, or cloud hosting.
- Secrets remain only in `~/.config/orvani-sync/orvani.env`, mode `0600`.
- The repository has pre-existing broad pytest collection/behavior failures; use the focused regression gates defined below rather than silently changing unrelated tests.
- Work in a fresh isolated Git worktree created from a clean `main`.
- Use TDD: demonstrate RED before each production change and GREEN afterward.
- Do not delete the existing `libreoffice-profile-isolation` worktree unless it is first proven clean and its branch is already an ancestor of `main`.

---

## File Structure

**Create**
- `scripts/orvani-catalog-launcher.sh` — visible user-facing LibreOffice launcher.
- `docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md` — approved design.
- `docs/superpowers/plans/2026-09-05-orvani-catalog-launcher.md` — this implementation plan.

**Modify**
- `scripts/orvani-sync-launcher.sh` — service-only Python launcher; remove LibreOffice ownership.
- `scripts/install-orvani-sync.sh` — install the catalog launcher and user desktop entry.
- `libreoffice_sync/main.py` — wait/retry for UNO before attaching the workbook.
- `tests/test_linux_service_files.py` — static launcher/installer/desktop contract tests.
- `tests/libreoffice_sync/test_main.py` — retry and workbook-wait behavior.

**No change expected**
- `systemd/orvani-sync.service` — existing `Restart=on-failure` remains appropriate.
- `libreoffice_sync/uno_client.py` — existing exact-document attachment and save listener remain the integration boundary.
- `libreoffice_sync/sync_service.py` — existing save-event upload behavior remains unchanged.

---

### Task 1: Establish the launcher and installation contract

**Files:**
- Create: `scripts/orvani-catalog-launcher.sh`
- Modify: `scripts/orvani-sync-launcher.sh`
- Modify: `scripts/install-orvani-sync.sh`
- Test: `tests/test_linux_service_files.py`

**Interfaces:**
- Consumes: `~/.config/orvani-sync/orvani.env` with `ORVANI_WORKBOOK_PATH`, `ORVANI_UNO_HOST=127.0.0.1`, and `ORVANI_UNO_PORT=2002`.
- Produces: executable `~/.local/bin/orvani-catalog-launcher`, service launcher `~/.local/bin/orvani-sync-launcher`, and user desktop entry `~/.local/share/applications/orvani-catalog.desktop`.

- [ ] **Step 1: Add failing static tests for the new ownership boundary**

Append tests equivalent to:

```python
from pathlib import Path


def test_sync_launcher_does_not_start_libreoffice():
    text = Path("scripts/orvani-sync-launcher.sh").read_text(encoding="utf-8")

    assert "/usr/bin/libreoffice" not in text
    assert "UserInstallation" not in text
    assert "port=2002" not in text
    assert 'exec "${VENV}/bin/python" -m libreoffice_sync.main run' in text


def test_catalog_launcher_owns_visible_dedicated_uno_instance():
    text = Path("scripts/orvani-catalog-launcher.sh").read_text(encoding="utf-8")

    assert 'PROFILE="${HOME}/.local/share/orvani-sync/libreoffice-profile"' in text
    assert 'source "${ENV_FILE}"' in text
    assert 'mkdir -p "${PROFILE}"' in text
    assert "Path(sys.argv[1]).resolve().as_uri()" in text
    assert '"-env:UserInstallation=${PROFILE_URI}"' in text
    assert "host=127.0.0.1,port=2002" in text
    assert "0.0.0.0" not in text
    assert '"${ORVANI_WORKBOOK_PATH}"' in text
    assert ">/dev/null" not in text


def test_installer_creates_catalog_launcher_and_desktop_entry():
    text = Path("scripts/install-orvani-sync.sh").read_text(encoding="utf-8")

    assert '"${ROOT}/scripts/orvani-catalog-launcher.sh"' in text
    assert '"${USER_BIN}/orvani-catalog-launcher"' in text
    assert 'APPLICATIONS_DIR="${HOME}/.local/share/applications"' in text
    assert 'orvani-catalog.desktop' in text
    assert "Name=Orvani Catálogo" in text
    assert "Terminal=false" in text
    assert "Icon=libreoffice-calc" in text
    assert "ORVANI_SYNC_SECRET" not in _desktop_entry_block(text)
```

Also add a small test helper that isolates only the installer heredoc:

```python
def _desktop_entry_block(text: str) -> str:
    start = text.index("[Desktop Entry]")
    end = text.index("EOF", start)
    return text[start:end]
```

Keep the existing tests for systemd user paths, loopback-only behavior, system UNO, secure env permissions, and non-auto-enable behavior.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_linux_service_files.py
```

Expected: failures because `scripts/orvani-catalog-launcher.sh` does not exist, the sync launcher still starts LibreOffice, and the installer does not create a desktop entry.

- [ ] **Step 3: Create the visible catalog launcher**

Create `scripts/orvani-catalog-launcher.sh` with this behavior:

```bash
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
```

Important: do not background or redirect the GUI process in this script.

- [ ] **Step 4: Simplify the service launcher**

Replace `scripts/orvani-sync-launcher.sh` with the service-only contract:

```bash
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
```

This intentionally removes profile creation, LibreOffice startup, TCP polling, and hidden-process ownership.

- [ ] **Step 5: Extend the installer**

In `scripts/install-orvani-sync.sh`:

1. Add:

```bash
APPLICATIONS_DIR="${HOME}/.local/share/applications"
```

2. Include it in `mkdir -p`:

```bash
mkdir -p \
  "${RUNTIME}" \
  "${APP}" \
  "${CONFIG_DIR}" \
  "${USER_BIN}" \
  "${SYSTEMD_DIR}" \
  "${APPLICATIONS_DIR}"
```

3. Install the new launcher:

```bash
install -m 0755 \
  "${ROOT}/scripts/orvani-catalog-launcher.sh" \
  "${USER_BIN}/orvani-catalog-launcher"
```

4. Generate the user desktop entry with the resolved absolute user-bin path:

```bash
cat >"${APPLICATIONS_DIR}/orvani-catalog.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Orvani Catálogo
Comment=Abrir o catálogo Orvani com sincronização
Exec=${USER_BIN}/orvani-catalog-launcher
Icon=libreoffice-calc
Terminal=false
Categories=Office;Spreadsheet;
StartupNotify=true
EOF

chmod 0644 "${APPLICATIONS_DIR}/orvani-catalog.desktop"
```

Do not place any environment variable values or secrets inside the desktop entry.

- [ ] **Step 6: Run static and shell tests for GREEN**

Run:

```bash
./.venv/bin/python -m pytest -q tests/test_linux_service_files.py
bash -n scripts/orvani-sync-launcher.sh
bash -n scripts/orvani-catalog-launcher.sh
bash -n scripts/install-orvani-sync.sh
git diff --check
```

Expected: all pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add \
  scripts/orvani-catalog-launcher.sh \
  scripts/orvani-sync-launcher.sh \
  scripts/install-orvani-sync.sh \
  tests/test_linux_service_files.py
git commit -m "feat: add visible Orvani catalog launcher"
```

---

### Task 2: Make `orvani-sync` wait safely for UNO and the exact workbook

**Files:**
- Modify: `libreoffice_sync/main.py`
- Test: `tests/libreoffice_sync/test_main.py`

**Interfaces:**
- Consumes: `LocalSettings.uno_host`, `LocalSettings.uno_port`, `LocalSettings.workbook_path`, and `LibreOfficeWorkbook.connect(host, port)`.
- Produces:
  - `_wait_for_uno(settings, *, connector=None, sleeper=time.sleep)`
  - `_wait_for_workbook(workbook, path, *, sleeper=time.sleep)`
  - `_run(settings)` that waits instead of failing when the GUI has not yet opened.

- [ ] **Step 1: Add failing retry tests**

Expand `tests/libreoffice_sync/test_main.py`:

```python
from pathlib import Path
from types import SimpleNamespace

from libreoffice_sync.main import (
    _wait_for_uno,
    _wait_for_workbook,
    build_parser,
)


def test_wait_for_uno_retries_until_catalog_instance_exists():
    expected = object()
    attempts = []
    sleeps = []

    def connector(*, host, port):
        attempts.append((host, port))
        if len(attempts) == 1:
            raise RuntimeError("UNO indisponível")
        return expected

    settings = SimpleNamespace(
        uno_host="127.0.0.1",
        uno_port=2002,
    )

    result = _wait_for_uno(
        settings,
        connector=connector,
        sleeper=sleeps.append,
    )

    assert result is expected
    assert attempts == [
        ("127.0.0.1", 2002),
        ("127.0.0.1", 2002),
    ]
    assert sleeps == [2]


def test_wait_for_workbook_retries_exact_expected_path():
    attempts = []
    sleeps = []

    class Workbook:
        def attach_expected_document(self, path):
            attempts.append(path)
            return len(attempts) == 3

    path = Path("/home/lucas/Documents/Orvani.ods")

    _wait_for_workbook(
        Workbook(),
        path,
        sleeper=sleeps.append,
    )

    assert attempts == [path, path, path]
    assert sleeps == [2, 2]
```

Keep the existing CLI command test unchanged.

- [ ] **Step 2: Run these tests and verify RED**

Run:

```bash
./.venv/bin/python -m pytest -q tests/libreoffice_sync/test_main.py
```

Expected: import failures for `_wait_for_uno` and `_wait_for_workbook`.

- [ ] **Step 3: Add the minimal waiting helpers**

In `libreoffice_sync/main.py`, add:

```python
def _wait_for_uno(
    settings: LocalSettings,
    *,
    connector=None,
    sleeper=time.sleep,
):
    connector = connector or LibreOfficeWorkbook.connect
    print(
        "Aguardando Orvani Catálogo em "
        f"{settings.uno_host}:{settings.uno_port}"
    )
    while True:
        try:
            return connector(
                host=settings.uno_host,
                port=settings.uno_port,
            )
        except Exception:
            sleeper(2)


def _wait_for_workbook(
    workbook,
    path,
    *,
    sleeper=time.sleep,
) -> None:
    print(f"Aguardando Orvani.ods: {path}")
    while not workbook.attach_expected_document(path):
        sleeper(2)
```

The broad exception is intentionally confined to the single UNO connection attempt after `LocalSettings` validation; no synchronization/API exceptions are swallowed.

- [ ] **Step 4: Route `_run()` through the waiting helpers**

Replace the immediate connection and inline attach loop with:

```python
def _run(settings: LocalSettings) -> int:
    workbook = _wait_for_uno(settings)
    _wait_for_workbook(workbook, settings.workbook_path)

    initialize_document(workbook.document)

    api = OrvaniApiClient(settings.webapp_url, settings.sync_secret)
    try:
        SyncService(
            workbook,
            api,
            poll_seconds=settings.poll_seconds,
        ).run_forever()
    finally:
        api.close()
    return 0
```

Do not add a hidden LibreOffice start anywhere in Python.

- [ ] **Step 5: Run targeted Python tests for GREEN**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/libreoffice_sync/test_main.py \
  tests/libreoffice_sync/test_uno_client.py \
  tests/libreoffice_sync/test_sync_service.py
```

Expected: all pass.

- [ ] **Step 6: Run focused combined regression**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_linux_service_files.py \
  tests/libreoffice_sync/test_main.py \
  tests/libreoffice_sync/test_uno_client.py \
  tests/libreoffice_sync/test_sync_service.py
bash -n scripts/orvani-sync-launcher.sh
bash -n scripts/orvani-catalog-launcher.sh
bash -n scripts/install-orvani-sync.sh
git diff --check
```

Expected: all pass.

Do not use the unrelated broad `pytest -q` suite as the merge gate for this feature because the clean `main` already reproduces independent collection/behavior failures.

- [ ] **Step 7: Commit Task 2**

```bash
git add libreoffice_sync/main.py tests/libreoffice_sync/test_main.py
git commit -m "fix: wait for visible Orvani UNO session"
```

---

### Task 3: Add the approved architecture documents

**Files:**
- Create: `docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md`
- Create: `docs/superpowers/plans/2026-09-05-orvani-catalog-launcher.md`

**Interfaces:**
- Consumes: the user-approved design and this implementation plan.
- Produces: durable project documentation describing the new ownership boundary, migration, testing, and daily flow.

- [ ] **Step 1: Add the approved design verbatim**

Copy the approved design artifact into:

```text
docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md
```

Verify the file contains these mandatory phrases:

```text
Orvani Catálogo
127.0.0.1:2002
Ctrl+S
No hidden LibreOffice instance is started by orvani-sync
```

- [ ] **Step 2: Add this implementation plan verbatim**

Copy this plan into:

```text
docs/superpowers/plans/2026-09-05-orvani-catalog-launcher.md
```

- [ ] **Step 3: Check documentation integrity**

Run:

```bash
grep -F "Orvani Catálogo" \
  docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md
grep -F "127.0.0.1:2002" \
  docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md
grep -F "Task 1: Establish the launcher" \
  docs/superpowers/plans/2026-09-05-orvani-catalog-launcher.md
git diff --check
```

Expected: all commands succeed.

- [ ] **Step 4: Commit Task 3**

```bash
git add \
  docs/superpowers/specs/2026-09-05-orvani-catalog-launcher-design.md \
  docs/superpowers/plans/2026-09-05-orvani-catalog-launcher.md
git commit -m "docs: document Orvani catalog launcher"
```

---

### Task 4: Install and verify the new process ownership on the workstation

**Files:**
- Runtime install only; no new repository files expected.

**Interfaces:**
- Consumes: the committed launcher, installer, systemd service, and existing `orvani.env`.
- Produces: installed desktop entry, service waiting state, visible dedicated Orvani LibreOffice instance, and restored save-event synchronization.

- [ ] **Step 1: Verify Git/worktree preconditions before runtime migration**

From the main repository:

```bash
git status --porcelain
git log -3 --oneline
git worktree list
```

Expected: main clean and feature worktree clean after commits.

If `.worktrees/libreoffice-profile-isolation` still exists, inspect before cleanup:

```bash
git -C .worktrees/libreoffice-profile-isolation status --porcelain
git merge-base --is-ancestor fix/libreoffice-profile-isolation main
```

Only if the first output is empty and the second command exits `0`:

```bash
git worktree remove .worktrees/libreoffice-profile-isolation
git branch -d fix/libreoffice-profile-isolation
```

Otherwise preserve it and stop for diagnosis.

- [ ] **Step 2: Stop the old service-owned LibreOffice instance**

Run:

```bash
systemctl --user stop orvani-sync
```

Then confirm the old dedicated-profile process is gone:

```bash
pgrep -a -f 'soffice.bin.*orvani-sync/libreoffice-profile' || true
```

Expected: no dedicated Orvani `soffice.bin`.

Do not kill unrelated normal LibreOffice processes.

- [ ] **Step 3: Install the new runtime**

Run from the feature/main checkout:

```bash
bash scripts/install-orvani-sync.sh
```

Verify:

```bash
test -x "${HOME}/.local/bin/orvani-sync-launcher"
test -x "${HOME}/.local/bin/orvani-catalog-launcher"
test -f "${HOME}/.local/share/applications/orvani-catalog.desktop"
grep -F "Name=Orvani Catálogo" \
  "${HOME}/.local/share/applications/orvani-catalog.desktop"
```

Expected: all succeed.

- [ ] **Step 4: Start `orvani-sync` before opening the catalog**

Run:

```bash
systemctl --user start orvani-sync
sleep 3
systemctl --user is-active orvani-sync
```

Expected:

```text
active
```

Confirm the service itself did not start LibreOffice:

```bash
pgrep -a -f 'soffice.bin.*orvani-sync/libreoffice-profile' || true
```

Expected: no dedicated Orvani `soffice.bin`.

Confirm the service is waiting rather than failing:

```bash
journalctl --user -u orvani-sync -n 20 --no-pager
```

Expected: a line containing:

```text
Aguardando Orvani Catálogo em 127.0.0.1:2002
```

and no restart loop caused solely by `Connection refused`.

- [ ] **Step 5: Launch the visible Orvani application**

Use the applications menu and click **Orvani Catálogo**.

Expected: a visible LibreOffice Calc window opens the configured `Orvani.ods`.

Verify process ownership:

```bash
pgrep -a -f 'soffice.bin'
```

Expected: one Orvani process containing both:

```text
-env:UserInstallation=file:///.../.local/share/orvani-sync/libreoffice-profile
--accept=socket,host=127.0.0.1,port=2002
```

Normal LibreOffice processes, if open, must not use that Orvani profile.

- [ ] **Step 6: Verify the same visible workbook is present through UNO**

Run:

```bash
PYTHONPATH="${HOME}/.local/share/orvani-sync/app" \
"${HOME}/.local/share/orvani-sync/venv/bin/python" - <<'PY'
from libreoffice_sync.uno_client import LibreOfficeWorkbook

workbook = LibreOfficeWorkbook.connect()
components = workbook.desktop.getComponents().createEnumeration()

urls = []
while components.hasMoreElements():
    component = components.nextElement()
    urls.append(getattr(component, "URL", ""))

print("\n".join(urls))
PY
```

Expected: output includes the configured `Orvani.ods` `file://` URI. It must no longer report an empty component list while the visible Orvani window is open.

- [ ] **Step 7: Verify `Ctrl+S` synchronization end to end**

In the visible **Orvani Catálogo** window:

1. Use the already-created test/new product row, or change one harmless editable field.
2. Press `Ctrl+S` once.
3. Wait for the normal sync/status cycle.

Verify service health:

```bash
systemctl --user is-active orvani-sync
journalctl --user -u orvani-sync -n 40 --no-pager
```

Expected: service remains active and no UNO connection failure occurs.

Acceptance in Calc: the row receives/updates its automation/status fields as it did before the profile-isolation regression. This is the proof that the save listener is attached to the visible workbook.

- [ ] **Step 8: Verify normal LibreOffice remains independent**

While Orvani Catálogo is open, start normal Calc from the standard LibreOffice launcher.

Expected:
- normal Calc opens;
- Orvani Catálogo stays open;
- the normal process does not use `~/.local/share/orvani-sync/libreoffice-profile`;
- `orvani-sync` remains active.

- [ ] **Step 9: Final focused verification before integration**

Run:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_linux_service_files.py \
  tests/libreoffice_sync/test_main.py \
  tests/libreoffice_sync/test_uno_client.py \
  tests/libreoffice_sync/test_sync_service.py
bash -n scripts/orvani-sync-launcher.sh
bash -n scripts/orvani-catalog-launcher.sh
bash -n scripts/install-orvani-sync.sh
git diff --check
git status --porcelain
```

Expected: focused tests pass, shell syntax passes, diff check passes, status is clean.

- [ ] **Step 10: Fast-forward main and push**

After runtime acceptance succeeds:

```bash
git checkout main
git merge --ff-only <feature-branch>
git push origin main
```

Then verify:

```bash
git status --porcelain
git log -4 --oneline
systemctl --user is-active orvani-sync
```

Expected: clean main, new commits visible, service active.

- [ ] **Step 11: Remove only the feature worktree/branch**

After confirming the pushed main contains the feature commits:

```bash
git worktree remove <feature-worktree>
git branch -d <feature-branch>
```

Do not remove any other worktree unless it separately passed the clean/ancestor checks in Step 1.

---

## Final Acceptance Checklist

The implementation is complete only when all items below are observed on the actual workstation:

- [ ] `orvani-sync` starts and stays active while no Orvani LibreOffice instance exists.
- [ ] `orvani-sync` does not start `/usr/bin/libreoffice`.
- [ ] **Orvani Catálogo** is present in the desktop application menu.
- [ ] Clicking **Orvani Catálogo** opens the configured `Orvani.ods` visibly.
- [ ] The visible Orvani process uses the dedicated Orvani profile.
- [ ] UNO is exposed only on `127.0.0.1:2002`.
- [ ] The configured `Orvani.ods` appears in the UNO component enumeration.
- [ ] Pressing `Ctrl+S` triggers synchronization of changed catalog rows.
- [ ] Normal LibreOffice Calc can be opened independently at the same time.
- [ ] Existing Central de Divulgação and discount-publication behavior are unchanged.
- [ ] Focused automated regression tests pass.
- [ ] `main` is clean and pushed to `origin/main`.
