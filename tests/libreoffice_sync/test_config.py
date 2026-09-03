
import pytest

from libreoffice_sync.config import ConfigurationError, LocalSettings


def base_env(monkeypatch):
    monkeypatch.setenv(
        "ORVANI_WEBAPP_URL",
        "https://script.google.com/macros/s/deployment/exec",
    )
    monkeypatch.setenv("ORVANI_SYNC_SECRET", "a" * 64)
    monkeypatch.setenv("ORVANI_WORKBOOK_PATH", "/tmp/Orvani.ods")


def test_settings_require_google_https_webapp(monkeypatch):
    base_env(monkeypatch)
    monkeypatch.setenv("ORVANI_WEBAPP_URL", "http://example.com/x")
    with pytest.raises(ConfigurationError):
        LocalSettings.from_env()


def test_poll_default_is_20(monkeypatch):
    base_env(monkeypatch)
    monkeypatch.delenv("ORVANI_STATUS_POLL_SECONDS", raising=False)
    assert LocalSettings.from_env().poll_seconds == 20


def test_workbook_path_must_be_absolute(monkeypatch):
    base_env(monkeypatch)
    monkeypatch.setenv("ORVANI_WORKBOOK_PATH", "Orvani.ods")
    with pytest.raises(ConfigurationError):
        LocalSettings.from_env()


def test_uno_host_is_loopback_only(monkeypatch):
    base_env(monkeypatch)
    monkeypatch.setenv("ORVANI_UNO_HOST", "0.0.0.0")
    with pytest.raises(ConfigurationError):
        LocalSettings.from_env()
