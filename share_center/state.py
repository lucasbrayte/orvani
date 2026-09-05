from __future__ import annotations

import json
import os
import re
from pathlib import Path

STATUSES = frozenset({"PENDENTE", "PUBLICADO", "ARQUIVADO"})
_SHARE_ID = re.compile(r"[0-9a-f]{32}")

class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()

    def _load(self):
        if not self.path.exists():
            return {"version": 1, "items": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise RuntimeError("Estado local da Central está corrompido.") from None
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("items"), dict)
        ):
            raise RuntimeError("Estado local da Central é inválido.")
        return data

    def get_entry(self, share_id: str) -> dict[str, str]:
        data = self._load()
        raw = data["items"].get(share_id, {})
        if not isinstance(raw, dict):
            return {}
        status = raw.get("status")
        updated_at = raw.get("updatedAt")
        if status not in STATUSES or not isinstance(updated_at, str):
            return {}
        return {"status": status, "updatedAt": updated_at}

    def get_status(self, share_id: str) -> str | None:
        return self.get_entry(share_id).get("status")

    def set_status(self, share_id: str, status: str, *, now: str) -> None:
        share_id = str(share_id).strip().lower()
        if not _SHARE_ID.fullmatch(share_id):
            raise ValueError("ID Divulgação inválido.")
        status = str(status).strip().upper()
        if status not in STATUSES:
            raise ValueError("Status inválido.")
        if not isinstance(now, str) or not now:
            raise ValueError("Timestamp inválido.")
        data = self._load()
        data["items"][share_id] = {"status": status, "updatedAt": now}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + f".tmp-{os.getpid()}")
        payload = json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ) + "\n"
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
            os.chmod(self.path, 0o600)
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass
