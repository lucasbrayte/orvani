
from pathlib import Path


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
    assert "PYTHONPATH" in text


def test_installer_uses_system_uno_and_secure_env():
    text = Path("scripts/install-orvani-sync.sh").read_text()
    assert "python3-uno" in text
    assert "libreoffice" in text
    assert "--system-site-packages" in text
    assert "chmod 600" in text
    assert "systemctl --user daemon-reload" in text
    assert "systemctl --user enable" not in text
