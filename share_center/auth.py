from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit


_PIN = re.compile(r"\d{8}")
_SECRET = re.compile(r"[0-9a-fA-F]{64}")
_PRIVATE_V4 = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
)
_PRIVATE_V6 = (
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
)


def _ip(value: str):
    try:
        return ipaddress.ip_address(str(value).strip())
    except ValueError:
        return None


def is_private_peer(value: str) -> bool:
    address = _ip(value)
    if address is None:
        return False
    networks = _PRIVATE_V4 if address.version == 4 else _PRIVATE_V6
    return any(address in network for network in networks)


def _host_parts(host_header: str):
    value = str(host_header).strip()
    if not value:
        return None
    try:
        parsed = urlsplit("//" + value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if not host:
        return None
    return host, port


def allowed_host(host_header: str, expected_port: int) -> bool:
    parts = _host_parts(host_header)
    if parts is None:
        return False
    host, port = parts
    if port != expected_port:
        return False
    if host.casefold() == "localhost":
        return True
    return is_private_peer(host)


def allowed_origin(origin: str, expected_port: int) -> bool:
    try:
        parsed = urlsplit(str(origin).strip())
    except ValueError:
        return False
    if parsed.scheme != "http" or parsed.username or parsed.password:
        return False
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return False
    if parsed.port != expected_port or not parsed.hostname:
        return False
    if parsed.hostname.casefold() == "localhost":
        return True
    return is_private_peer(parsed.hostname)


def pin_matches(expected: str, submitted: str) -> bool:
    if not isinstance(expected, str) or not isinstance(submitted, str):
        return False
    if _PIN.fullmatch(expected) is None or _PIN.fullmatch(submitted) is None:
        return False
    return hmac.compare_digest(expected, submitted)


@dataclass(frozen=True, slots=True)
class AccessConfig:
    pin: str
    session_secret: bytes

    @classmethod
    def from_env(cls) -> "AccessConfig":
        pin = os.environ.get("ORVANI_SHARE_PIN", "").strip()
        secret = os.environ.get(
            "ORVANI_SHARE_SESSION_SECRET", ""
        ).strip()
        if _PIN.fullmatch(pin) is None:
            raise RuntimeError(
                "ORVANI_SHARE_PIN deve conter exatamente 8 dígitos."
            )
        if _SECRET.fullmatch(secret) is None:
            raise RuntimeError(
                "ORVANI_SHARE_SESSION_SECRET deve conter 64 caracteres hex."
            )
        return cls(pin=pin, session_secret=bytes.fromhex(secret))


class SessionSigner:
    def __init__(self, secret: bytes, *, ttl_seconds: int = 604800):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("Segredo de sessão inválido.")
        if (
            not isinstance(ttl_seconds, int)
            or isinstance(ttl_seconds, bool)
            or ttl_seconds < 60
        ):
            raise ValueError("TTL de sessão inválido.")
        self._secret = secret
        self.ttl_seconds = ttl_seconds

    def _signature(self, expires: int) -> str:
        payload = f"v1.{expires}".encode("ascii")
        return hmac.new(
            self._secret, payload, hashlib.sha256
        ).hexdigest()

    def issue(self, *, now: float | None = None) -> str:
        current = time.time() if now is None else float(now)
        expires = int(current) + self.ttl_seconds
        return f"v1.{expires}.{self._signature(expires)}"

    def verify(self, token: str, *, now: float | None = None) -> bool:
        if not isinstance(token, str):
            return False
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != "v1":
            return False
        try:
            expires = int(parts[1])
        except ValueError:
            return False
        current = time.time() if now is None else float(now)
        if expires < current:
            return False
        expected = self._signature(expires)
        return hmac.compare_digest(expected, parts[2])


class LoginRateLimiter:
    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 300,
        block_seconds: int = 900,
    ):
        if min(max_failures, window_seconds, block_seconds) <= 0:
            raise ValueError("Configuração de rate limit inválida.")
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}
        self._blocked_until: dict[str, float] = {}

    def _now(self, value: float | None) -> float:
        return time.monotonic() if value is None else float(value)

    def _prune(self, key: str, current: float) -> list[float]:
        cutoff = current - self.window_seconds
        attempts = [
            item
            for item in self._failures.get(key, [])
            if item >= cutoff
        ]
        if attempts:
            self._failures[key] = attempts
        else:
            self._failures.pop(key, None)
        return attempts

    def allowed(self, key: str, *, now: float | None = None) -> bool:
        current = self._now(now)
        with self._lock:
            blocked_until = self._blocked_until.get(key, 0.0)
            if blocked_until > current:
                return False
            if blocked_until:
                self._blocked_until.pop(key, None)
            self._prune(key, current)
            return True

    def record_failure(
        self,
        key: str,
        *,
        now: float | None = None,
    ) -> None:
        current = self._now(now)
        with self._lock:
            attempts = self._prune(key, current)
            attempts.append(current)
            self._failures[key] = attempts
            if len(attempts) >= self.max_failures:
                self._blocked_until[key] = current + self.block_seconds
                self._failures.pop(key, None)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)

    def retry_after(
        self,
        key: str,
        *,
        now: float | None = None,
    ) -> int:
        current = self._now(now)
        with self._lock:
            remaining = self._blocked_until.get(key, 0.0) - current
        return max(0, int(remaining + 0.999))
