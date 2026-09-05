from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .source import SourceError, fetch_items
from .state import StateStore

HOST = "127.0.0.1"
PORT = 8765
STATIC = Path(__file__).with_name("static")
STATE_PATH = Path(os.environ.get(
    "ORVANI_SHARE_STATE_PATH",
    "~/.local/share/orvani-share/state.json",
)).expanduser()
_STATUS_PATH = re.compile(r"/api/items/([0-9a-f]{32})/status")
_ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
_ALLOWED_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}", ""}
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
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

class Handler(BaseHTTPRequestHandler):
    server_version = "OrvaniShareCenter/1.0"

    def log_message(self, fmt, *args):
        print(f"orvani-share {self.client_address[0]} {fmt % args}", flush=True)

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

    def _bytes(self, status, body, content_type):
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._bytes(status, body, "application/json; charset=utf-8")

    def _host_invalid(self):
        if self.headers.get("Host", "") in _ALLOWED_HOSTS:
            return False
        self._json(400, {"ok": False, "error": "Host inválido."})
        return True

    def do_GET(self):
        if self._host_invalid():
            return
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "orvani-share", "bind": f"{HOST}:{PORT}"})
            return
        if path == "/api/items":
            try:
                payload = []
                for item in CACHE.get():
                    entry = STORE.get_entry(item.share_id)
                    payload.append(item.as_dict(
                        status=entry.get("status"),
                        status_updated_at=entry.get("updatedAt", ""),
                    ))
            except SourceError as error:
                self._json(503, {"ok": False, "error": str(error)})
                return
            except RuntimeError:
                self._json(500, {"ok": False, "error": "Estado local indisponível."})
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
            self._json(404, {"ok": False, "error": "Não encontrado."})
            return
        filename, content_type = target
        try:
            body = (STATIC / filename).read_bytes()
        except OSError:
            self._json(500, {"ok": False, "error": "Interface indisponível."})
            return
        self._bytes(200, body, content_type)

    def do_POST(self):
        if self._host_invalid():
            return
        if self.headers.get("Origin", "") not in _ALLOWED_ORIGINS:
            self._json(403, {"ok": False, "error": "Origem inválida."})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._json(415, {"ok": False, "error": "JSON obrigatório."})
            return
        match = _STATUS_PATH.fullmatch(urlsplit(self.path).path)
        if match is None:
            self._json(404, {"ok": False, "error": "Não encontrado."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 1 <= length <= _MAX_JSON:
            self._json(413, {"ok": False, "error": "Payload inválido."})
            return
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeError, json.JSONDecodeError):
            self._json(400, {"ok": False, "error": "JSON inválido."})
            return
        if not isinstance(value, dict) or set(value) != {"status"} or not isinstance(value["status"], str):
            self._json(400, {"ok": False, "error": "Payload inválido."})
            return
        try:
            STORE.set_status(match.group(1), value["status"], now=_now_iso())
        except ValueError:
            self._json(400, {"ok": False, "error": "Status inválido."})
            return
        except RuntimeError:
            self._json(500, {"ok": False, "error": "Estado local indisponível."})
            return
        self._json(200, {"ok": True})

def main():
    if HOST != "127.0.0.1":
        raise RuntimeError("A Central deve usar somente loopback.")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"Orvani Central de Divulgação: http://{HOST}:{PORT}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
