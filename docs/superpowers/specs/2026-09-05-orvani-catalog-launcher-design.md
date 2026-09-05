# Orvani Catalog Launcher Design

**Date:** 2026-09-05
**Status:** Approved architecture, pending implementation plan
**Scope:** Linux desktop / LibreOffice local synchronization

## Problem

The current `orvani-sync` service starts a hidden LibreOffice process with a dedicated profile and exposes UNO on `127.0.0.1:2002`. This solved the earlier profile collision that prevented the user's normal LibreOffice Calc from opening, but it created a second, isolated LibreOffice instance.

The visible `Orvani.ods` is opened in the user's normal LibreOffice instance, while `orvani-sync` connects to the hidden dedicated-profile instance. Because `LibreOfficeWorkbook.attach_expected_document()` only searches documents inside the UNO-connected instance, the service cannot see the visible `Orvani.ods` and therefore never installs the `OnSaveDone` / `OnSaveAsDone` listener. Pressing `Ctrl+S` in the visible workbook consequently does not trigger synchronization.

A second observed failure mode is startup timing: `orvani-sync` can attempt to connect to UNO before a listener exists and exit with `NoConnectException`, relying on systemd restart behavior.

## Goals

1. Keep the Orvani LibreOffice profile isolated from the user's normal LibreOffice profile.
2. Ensure the visible `Orvani.ods` and the UNO endpoint used by `orvani-sync` belong to the same LibreOffice process.
3. Preserve `Ctrl+S` as the user's synchronization trigger.
4. Require no terminal commands during normal daily use.
5. Keep UNO bound only to `127.0.0.1:2002`.
6. Allow the `orvani-sync` user service to start at login even when the Orvani workbook has not yet been opened.
7. Avoid reintroducing the old profile-lock conflict.
8. Preserve the existing Google/Apps Script synchronization protocol and workbook schema.

## Non-goals

- Do not move the Central de Divulgação to the cloud.
- Do not change the WhatsApp discount feature.
- Do not change the Google Sheets / Apps Script API contract.
- Do not watch the `.ods` file with filesystem polling.
- Do not expose UNO to the LAN.
- Do not change the user's normal LibreOffice, Writer, or Calc launchers.
- Do not remove the dedicated Orvani LibreOffice profile.

## Architecture

The Orvani catalog becomes an explicitly launched desktop application.

```text
Normal LibreOffice
  profile: normal user profile
  purpose: ordinary Writer/Calc use
  no dependency on Orvani UNO

Orvani Catálogo desktop launcher
  |
  +--> LibreOffice GUI (visible)
       profile: ~/.local/share/orvani-sync/libreoffice-profile
       opens: ORVANI_WORKBOOK_PATH
       UNO: 127.0.0.1:2002
                |
                v
           orvani-sync
                |
                +--> waits until UNO exists
                +--> attaches the same visible Orvani.ods
                +--> installs save listener
                +--> Ctrl+S -> upload changed rows
```

The service no longer owns the LibreOffice process. The graphical launcher owns it.

## Components

### 1. `scripts/orvani-catalog-launcher.sh`

New user-facing launcher responsible only for starting the visible Orvani LibreOffice instance.

Responsibilities:

- Load `~/.config/orvani-sync/orvani.env`.
- Reuse the existing dedicated profile at:
  `~/.local/share/orvani-sync/libreoffice-profile`.
- Convert the profile path to a proper `file://` URI.
- Start `/usr/bin/libreoffice` visibly.
- Pass:
  `-env:UserInstallation=<profile-uri>`.
- Bind UNO exclusively to:
  `socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext`.
- Open `ORVANI_WORKBOOK_PATH` directly.
- Keep first-start and restore prompts suppressed where already appropriate.
- Never use `0.0.0.0`.

A second click while the dedicated Orvani instance is already running may be delegated by LibreOffice to the existing dedicated-profile process; that is acceptable because the profile belongs only to Orvani.

### 2. `scripts/orvani-sync-launcher.sh`

This launcher becomes service-only.

Responsibilities:

- Load the Orvani environment file.
- Set `PYTHONPATH`.
- Execute:
  `python -m libreoffice_sync.main run`.

It must no longer:

- start `/usr/bin/libreoffice`;
- create the LibreOffice profile;
- poll TCP port 2002 in shell.

This removes process ownership ambiguity.

### 3. `libreoffice_sync/main.py`

The `run` command must tolerate the service starting before the GUI.

Current behavior performs a one-shot `LibreOfficeWorkbook.connect()` and fails if UNO is unavailable. The new behavior will retry connection to the configured loopback UNO endpoint at a small fixed interval until the Orvani LibreOffice instance is available.

After connection:

1. Search for the exact configured `ORVANI_WORKBOOK_PATH`.
2. If the UNO instance is available but the workbook is not yet visible, continue waiting using the existing attach loop.
3. Once attached, apply the existing workbook visual contract.
4. Start the existing `SyncService`.
5. Preserve existing API error handling.

If the active LibreOffice session later terminates and causes a fatal UNO error, the process may exit. The existing `Restart=on-failure` systemd policy will restart `orvani-sync`, which returns to the safe UNO-wait state. This deliberately avoids broad exception swallowing inside the synchronization loop.

### 4. Desktop entry

The installer creates a user-level desktop entry:

`~/.local/share/applications/orvani-catalog.desktop`

Visible name:

`Orvani Catálogo`

Properties:

- `Type=Application`
- `Terminal=false`
- Executes `~/.local/bin/orvani-catalog-launcher`
- Uses a standard spreadsheet/LibreOffice Calc icon unless a stable Orvani icon installation path is explicitly added later
- Office/spreadsheet category

This becomes the normal way to open the catalog.

### 5. `scripts/install-orvani-sync.sh`

The existing installer remains responsible for the local runtime and additionally installs:

- `scripts/orvani-catalog-launcher.sh` -> `~/.local/bin/orvani-catalog-launcher`
- generated or repository desktop entry -> `~/.local/share/applications/orvani-catalog.desktop`

It continues to:

- preserve `orvani.env`;
- keep it mode `0600`;
- install the Python runtime;
- install the systemd user service.

No router, firewall, sudo, or global LibreOffice configuration changes are introduced.

## Daily User Flow

Normal operation becomes:

1. User clicks **Orvani Catálogo** from the applications menu.
2. A visible LibreOffice Calc window opens `Orvani.ods` using the isolated Orvani profile.
3. `orvani-sync`, already running as a user service, detects UNO on `127.0.0.1:2002`.
4. The service finds the exact workbook and installs the save listener.
5. User adds or edits a product.
6. User presses `Ctrl+S`.
7. `OnSaveDone` marks the workbook as changed.
8. `SyncService` validates and uploads changed rows using the existing API.
9. Backend status polling continues as today.

No terminal interaction is required.

## Startup and Failure Behavior

### Service starts before Orvani Catálogo

Expected and normal.

`orvani-sync` remains alive waiting for UNO. It must not launch a hidden LibreOffice instance and must not repeatedly fail solely because port 2002 is closed.

### Orvani Catálogo starts before the service

The GUI opens normally and UNO listens on loopback. When the service starts, it connects and attaches the workbook.

### User closes Orvani Catálogo

The dedicated LibreOffice process exits. If this invalidates the active UNO session and causes the sync process to fail, systemd restarts it after the existing restart delay. The restarted process waits safely for the next Orvani Catálogo launch.

### User opens normal Calc separately

No conflict. Normal LibreOffice uses the normal user profile; Orvani Catálogo uses the dedicated Orvani profile.

### Port 2002 is already occupied by a non-Orvani process

The graphical launcher must not weaken security or bind another interface. Runtime diagnostics should make the failure visible through service status/journal; implementation should not kill unrelated processes automatically.

## Security

- UNO remains loopback-only at `127.0.0.1`.
- No LAN exposure is added.
- The dedicated Orvani profile remains isolated.
- Secrets remain in `~/.config/orvani-sync/orvani.env` with mode `0600`.
- The `.desktop` file contains no secrets.
- The launcher does not print `ORVANI_SYNC_SECRET`.
- The change does not alter Central de Divulgação authentication or firewall rules.

## Compatibility and Migration

The existing dedicated profile directory from the previous fix is reused; it does not need to be deleted.

During installation/activation of the new design:

1. Stop the currently hidden Orvani LibreOffice instance safely via the `orvani-sync` service lifecycle, not by deleting the profile.
2. Install the service-only sync launcher and graphical catalog launcher.
3. Restart `orvani-sync`; it should remain waiting rather than creating LibreOffice.
4. Launch **Orvani Catálogo**.
5. Verify that the UNO-connected component list contains the configured `Orvani.ods`.
6. Press `Ctrl+S` and verify that a changed row is processed.

Normal LibreOffice settings and documents remain untouched.

## Testing Strategy

Implementation follows TDD.

### Static service/launcher tests

Extend `tests/test_linux_service_files.py` to prove:

- `orvani-sync-launcher.sh` does not invoke `/usr/bin/libreoffice`;
- the new catalog launcher uses the dedicated `UserInstallation`;
- the catalog launcher binds only `127.0.0.1:2002`;
- the catalog launcher opens `ORVANI_WORKBOOK_PATH`;
- the installer installs both the launcher and desktop entry;
- no secrets are embedded in the desktop entry.

### Python startup tests

Extend `tests/libreoffice_sync/test_main.py` to prove:

- `run` retries when `LibreOfficeWorkbook.connect()` temporarily fails;
- it eventually proceeds after a later successful connection;
- it still waits for the exact workbook after UNO connects;
- existing `health` and argument parsing behavior remain unchanged.

Tests should inject/mocking sleep and connector behavior so they complete immediately and never require a real LibreOffice process.

### Focused regression tests

At minimum run the relevant Linux service, `libreoffice_sync` main/UNO/sync-service tests, shell syntax checks, and `git diff --check`.

The repository currently has unrelated pre-existing broad pytest collection/behavior failures; those are not part of this change and must not be silently fixed in this implementation.

### Runtime acceptance

On the real workstation:

1. Confirm only the normal LibreOffice instance exists before opening Orvani Catálogo.
2. Confirm `orvani-sync` is active while UNO port 2002 is absent.
3. Launch Orvani Catálogo.
4. Confirm a dedicated-profile `soffice.bin` is visible and has the loopback `--accept` argument.
5. Query UNO components and confirm the configured `Orvani.ods` is visible.
6. Edit a test product and press `Ctrl+S`.
7. Confirm the sync backend receives the change and the Calc status fields update.
8. Confirm a normal LibreOffice Calc window can still be opened independently.

## Success Criteria

The change is complete only when all of the following are true:

- No hidden LibreOffice instance is started by `orvani-sync`.
- The user can open normal LibreOffice independently.
- **Orvani Catálogo** opens the real editable `Orvani.ods` visibly.
- The visible Orvani workbook is the same document seen through UNO.
- `Ctrl+S` triggers synchronization again.
- `orvani-sync` can start before the GUI without failing on a closed UNO port.
- UNO remains loopback-only.
- No daily terminal commands are required.
- Existing catalog, Central de Divulgação, discount publication, and API contracts remain unchanged.
