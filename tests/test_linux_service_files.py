from pathlib import Path


def _desktop_entry_block(text: str) -> str:
    start = text.index("[Desktop Entry]")
    end = text.index("EOF", start)
    return text[start:end]


def test_systemd_service_uses_user_paths():
    text = Path("systemd/orvani-sync.service").read_text(encoding="utf-8")
    assert "ExecStart=%h/.local/bin/orvani-sync-launcher" in text
    assert "WantedBy=default.target" in text
    assert "GITHUB_TOKEN" not in text
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in text


def test_sync_launcher_does_not_start_libreoffice():
    text = Path("scripts/orvani-sync-launcher.sh").read_text(encoding="utf-8")

    assert "/usr/bin/libreoffice" not in text
    assert "UserInstallation" not in text
    assert "port=2002" not in text
    assert "PYTHONPATH" in text
    assert 'exec "${VENV}/bin/python" -m libreoffice_sync.main run' in text


def test_catalog_launcher_owns_visible_dedicated_uno_instance():
    path = Path("scripts/orvani-catalog-launcher.sh")
    assert path.exists()

    text = path.read_text(encoding="utf-8")
    assert 'PROFILE="${HOME}/.local/share/orvani-sync/libreoffice-profile"' in text
    assert 'source "${ENV_FILE}"' in text
    assert 'mkdir -p "${PROFILE}"' in text
    assert "Path(sys.argv[1]).resolve().as_uri()" in text
    assert '"-env:UserInstallation=${PROFILE_URI}"' in text
    assert "host=127.0.0.1,port=2002" in text
    assert "0.0.0.0" not in text
    assert '"${ORVANI_WORKBOOK_PATH}"' in text
    assert ">/dev/null" not in text


def test_installer_uses_system_uno_secure_env_and_catalog_entry():
    text = Path("scripts/install-orvani-sync.sh").read_text(encoding="utf-8")

    assert "python3-uno" in text
    assert "libreoffice" in text
    assert "--system-site-packages" in text
    assert "chmod 600" in text
    assert "systemctl --user daemon-reload" in text
    assert "systemctl --user enable" not in text

    assert '"${ROOT}/scripts/orvani-catalog-launcher.sh"' in text
    assert '"${USER_BIN}/orvani-catalog-launcher"' in text
    assert 'APPLICATIONS_DIR="${HOME}/.local/share/applications"' in text
    assert "orvani-catalog.desktop" in text

    desktop = _desktop_entry_block(text)
    assert "Name=Orvani Catálogo" in desktop
    assert "Terminal=false" in desktop
    assert "Icon=libreoffice-calc" in desktop
    assert "ORVANI_SYNC_SECRET" not in desktop


def test_uno_launchers_ignore_activated_virtualenv_python():
    installer = Path("scripts/install-orvani-sync.sh").read_text(encoding="utf-8")
    catalog = Path("scripts/orvani-catalog-launcher.sh").read_text(encoding="utf-8")

    assert 'SYSTEM_PYTHON="/usr/bin/python3"' in installer
    assert '"${SYSTEM_PYTHON}" -c \'import uno\'' in installer
    assert '"${SYSTEM_PYTHON}" -m venv --system-site-packages "${VENV}"' in installer
    assert 'SYSTEM_PYTHON="/usr/bin/python3"' in catalog
    assert '"${SYSTEM_PYTHON}" -c' in catalog
