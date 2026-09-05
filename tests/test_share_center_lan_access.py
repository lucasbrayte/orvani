from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _auth():
    spec = importlib.util.find_spec("share_center.auth")
    assert spec is not None, "share_center.auth ainda não existe"
    return importlib.import_module("share_center.auth")

def test_private_network_policy_rejects_public_clients():
    auth = _auth()
    assert auth.is_private_peer("127.0.0.1") is True
    assert auth.is_private_peer("192.168.1.44") is True
    assert auth.is_private_peer("10.10.0.8") is True
    assert auth.is_private_peer("172.20.10.2") is True
    assert auth.is_private_peer("169.254.3.4") is True
    assert auth.is_private_peer("8.8.8.8") is False
    assert auth.is_private_peer("1.1.1.1") is False

def test_host_and_origin_must_be_private_and_use_port_8765():
    auth = _auth()
    assert auth.allowed_host("192.168.1.20:8765", 8765) is True
    assert auth.allowed_host("127.0.0.1:8765", 8765) is True
    assert auth.allowed_host("localhost:8765", 8765) is True
    assert auth.allowed_host("192.168.1.20:9999", 8765) is False
    assert auth.allowed_host("8.8.8.8:8765", 8765) is False
    assert auth.allowed_host("evil.example:8765", 8765) is False
    assert auth.allowed_origin("http://192.168.1.20:8765", 8765) is True
    assert auth.allowed_origin("http://127.0.0.1:8765", 8765) is True
    assert auth.allowed_origin("https://192.168.1.20:8765", 8765) is False
    assert auth.allowed_origin("http://8.8.8.8:8765", 8765) is False

def test_pin_config_session_and_tamper_detection(monkeypatch):
    auth = _auth()
    monkeypatch.setenv("ORVANI_SHARE_PIN", "48273195")
    monkeypatch.setenv("ORVANI_SHARE_SESSION_SECRET", "11" * 32)
    config = auth.AccessConfig.from_env()
    assert config.pin == "48273195"
    signer = auth.SessionSigner(bytes.fromhex("11" * 32), ttl_seconds=604800)
    token = signer.issue(now=1_000_000)
    assert signer.verify(token, now=1_000_001) is True
    assert signer.verify(token + "x", now=1_000_001) is False
    assert signer.verify(token, now=1_604_801) is False
    assert auth.pin_matches("48273195", "48273195") is True
    assert auth.pin_matches("48273195", "48273196") is False

def test_login_rate_limiter_blocks_after_five_failures():
    auth = _auth()
    limiter = auth.LoginRateLimiter(
        max_failures=5, window_seconds=300, block_seconds=900,
    )
    ip = "192.168.1.50"
    for attempt in range(5):
        assert limiter.allowed(ip, now=100 + attempt) is True
        limiter.record_failure(ip, now=100 + attempt)
    assert limiter.allowed(ip, now=106) is False
    assert limiter.retry_after(ip, now=106) > 0
    assert limiter.allowed(ip, now=1005) is True
    limiter.record_success(ip)
    assert limiter.allowed(ip, now=1006) is True

def test_ui_has_pin_login_logout_and_http_clipboard_fallback():
    html = (ROOT / "share_center/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "share_center/static/app.js").read_text(encoding="utf-8")
    assert 'id="login-panel"' in html
    assert 'id="login-form"' in html
    assert 'id="pin-input"' in html
    assert 'id="logout"' in html
    assert 'fetch("/api/session"' in js
    assert 'fetch("/api/login"' in js
    assert 'fetch("/api/logout"' in js
    assert 'document.execCommand("copy")' in js

def test_installer_generates_private_persistent_credentials_and_access_helper():
    installer = (ROOT / "scripts/install-orvani-share.sh").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts/orvani-share-launcher.sh").read_text(encoding="utf-8")
    helper = ROOT / "scripts/orvani-share-access.sh"
    assert helper.is_file()
    access = helper.read_text(encoding="utf-8")
    assert "ORVANI_SHARE_PIN" in installer
    assert "ORVANI_SHARE_SESSION_SECRET" in installer
    assert "secrets.randbelow" in installer
    assert "secrets.token_hex" in installer
    assert "chmod 600" in installer
    assert "systemctl --user restart orvani-share.service" in installer
    assert "share.env" in launcher
    assert "source" in launcher
    assert "PIN:" in access
    assert "8765" in access
    assert "ipaddress" in access
