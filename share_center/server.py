from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .auth import (
    AccessConfig,
    LoginRateLimiter,
    SessionSigner,
    allowed_host,
    allowed_origin,
    is_private_peer,
    pin_matches,
)
from .source import SourceError, fetch_items
from .state import StateStore


HOST = "0.0.0.0"
PORT = 8765
SESSION_COOKIE = "orvani_share_session"
SESSION_TTL_SECONDS = 604800
STATIC = Path(__file__).with_name("static")
STATE_PATH = Path(os.environ.get(
    "ORVANI_SHARE_STATE_PATH",
    "~/.local/share/orvani-share/state.json",
)).expanduser()
_STATUS_PATH = re.compile(r"/api/items/([0-9a-f]{32})/status")
_MAX_JSON = 4096


class QueueCache:
    def __init__(self, ttl: float = 15.0):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._items = None
        self._at = 0.0

    def get(self):
        now = time.monotonic()
        with self._lock:
            if self._items is not None and now - self._at < self.ttl:
                return self._items
        items = fetch_items()
        with self._lock:
            self._items = items
            self._at = now
        return items


STORE = StateStore(STATE_PATH)
CACHE = QueueCache()


def _now_iso():
    return datetime.now(UTC).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


class Handler(BaseHTTPRequestHandler):
    server_version = "OrvaniShareCenter/1.1"

    def log_message(self, fmt, *args):
        print(
            f"orvani-share {self.client_address[0]} {fmt % args}",
            flush=True,
        )

    @property
    def _access(self):
        return self.server.access

    @property
    def _signer(self):
        return self.server.signer

    @property
    def _limiter(self):
        return self.server.limiter

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src https: data:; connect-src 'self'; "
            "script-src 'self'; style-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("Cache-Control", "no-store")

    def _bytes(
        self,
        status,
        body,
        content_type,
        *,
        headers=(),
    ):
        self.send_response(status)
        self._security_headers()
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value, *, headers=()):
        body = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self._bytes(
            status,
            body,
            "application/json; charset=utf-8",
            headers=headers,
        )

    def _request_invalid(self):
        client_ip = self.client_address[0]
        if not is_private_peer(client_ip):
            self._json(
                403,
                {"ok": False, "error": "Cliente fora da rede privada."},
            )
            return True
        if not allowed_host(self.headers.get("Host", ""), PORT):
            self._json(
                400,
                {"ok": False, "error": "Host inválido."},
            )
            return True
        return False

    def _origin_invalid(self):
        origin = self.headers.get("Origin", "")
        if allowed_origin(origin, PORT):
            return False
        self._json(
            403,
            {"ok": False, "error": "Origem inválida."},
        )
        return True

    def _session_token(self):
        header = self.headers.get("Cookie", "")
        if not header:
            return ""
        jar = cookies.SimpleCookie()
        try:
            jar.load(header)
        except cookies.CookieError:
            return ""
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel is not None else ""

    def _authenticated(self):
        return self._signer.verify(self._session_token())

    def _require_auth(self):
        if self._authenticated():
            return False
        self._json(
            401,
            {"ok": False, "error": "Autenticação necessária."},
        )
        return True

    def _read_json(self):
        content_type = self.headers.get(
            "Content-Type", ""
        ).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._json(
                415,
                {"ok": False, "error": "JSON obrigatório."},
            )
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 1 <= length <= _MAX_JSON:
            self._json(
                413,
                {"ok": False, "error": "Payload inválido."},
            )
            return None
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeError, json.JSONDecodeError):
            self._json(
                400,
                {"ok": False, "error": "JSON inválido."},
            )
            return None
        return value

    def do_GET(self):
        if self._request_invalid():
            return

        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "service": "orvani-share",
                    "bind": f"{HOST}:{PORT}",
                    "lan": True,
                },
            )
            return

        if path == "/api/session":
            self._json(
                200,
                {
                    "ok": True,
                    "authenticated": self._authenticated(),
                },
            )
            return

        if path == "/api/items":
            if self._require_auth():
                return
            try:
                payload = []
                for item in CACHE.get():
                    entry = STORE.get_entry(item.share_id)
                    payload.append(
                        item.as_dict(
                            status=entry.get("status"),
                            status_updated_at=entry.get(
                                "updatedAt", ""
                            ),
                        )
                    )
            except SourceError as error:
                self._json(
                    503,
                    {"ok": False, "error": str(error)},
                )
                return
            except RuntimeError:
                self._json(
                    500,
                    {
                        "ok": False,
                        "error": "Estado local indisponível.",
                    },
                )
                return
            self._json(200, {"ok": True, "items": payload})
            return

        static_map = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        target = static_map.get(path)
        if target is None:
            self._json(
                404,
                {"ok": False, "error": "Não encontrado."},
            )
            return
        filename, content_type = target
        try:
            body = (STATIC / filename).read_bytes()
        except OSError:
            self._json(
                500,
                {"ok": False, "error": "Interface indisponível."},
            )
            return
        self._bytes(200, body, content_type)

    def do_POST(self):
        if self._request_invalid() or self._origin_invalid():
            return

        path = urlsplit(self.path).path

        if path == "/api/login":
            client_ip = self.client_address[0]
            if not self._limiter.allowed(client_ip):
                self._json(
                    429,
                    {
                        "ok": False,
                        "error": "Muitas tentativas. Tente novamente mais tarde.",
                        "retryAfter": self._limiter.retry_after(client_ip),
                    },
                )
                return
            value = self._read_json()
            if value is None:
                return
            if (
                not isinstance(value, dict)
                or set(value) != {"pin"}
                or not isinstance(value["pin"], str)
            ):
                self._json(
                    400,
                    {"ok": False, "error": "Payload inválido."},
                )
                return
            if not pin_matches(self._access.pin, value["pin"]):
                self._limiter.record_failure(client_ip)
                self._json(
                    401,
                    {"ok": False, "error": "PIN inválido."},
                )
                return
            self._limiter.record_success(client_ip)
            token = self._signer.issue()
            cookie = (
                f"{SESSION_COOKIE}={token}; Path=/; "
                f"Max-Age={SESSION_TTL_SECONDS}; HttpOnly; SameSite=Strict"
            )
            self._json(
                200,
                {"ok": True, "authenticated": True},
                headers=(("Set-Cookie", cookie),),
            )
            return

        if path == "/api/logout":
            cookie = (
                f"{SESSION_COOKIE}=; Path=/; Max-Age=0; "
                "HttpOnly; SameSite=Strict"
            )
            self._json(
                200,
                {"ok": True, "authenticated": False},
                headers=(("Set-Cookie", cookie),),
            )
            return

        if self._require_auth():
            return

        match = _STATUS_PATH.fullmatch(path)
        if match is None:
            self._json(
                404,
                {"ok": False, "error": "Não encontrado."},
            )
            return

        value = self._read_json()
        if value is None:
            return
        if (
            not isinstance(value, dict)
            or set(value) != {"status"}
            or not isinstance(value["status"], str)
        ):
            self._json(
                400,
                {"ok": False, "error": "Payload inválido."},
            )
            return
        try:
            STORE.set_status(
                match.group(1),
                value["status"],
                now=_now_iso(),
            )
        except ValueError:
            self._json(
                400,
                {"ok": False, "error": "Status inválido."},
            )
            return
        except RuntimeError:
            self._json(
                500,
                {"ok": False, "error": "Estado local indisponível."},
            )
            return
        self._json(200, {"ok": True})


def main():
    access = AccessConfig.from_env()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    server.access = access
    server.signer = SessionSigner(
        access.session_secret,
        ttl_seconds=SESSION_TTL_SECONDS,
    )
    server.limiter = LoginRateLimiter(
        max_failures=5,
        window_seconds=300,
        block_seconds=900,
    )
    print(
        f"Orvani Central de Divulgação: http://127.0.0.1:{PORT} "
        f"(LAN habilitada em porta {PORT})",
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
