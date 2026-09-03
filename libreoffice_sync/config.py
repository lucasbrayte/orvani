
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LocalSettings:
    webapp_url: str
    sync_secret: str
    workbook_path: Path
    poll_seconds: int = 20
    uno_host: str = "127.0.0.1"
    uno_port: int = 2002

    @classmethod
    def from_env(cls):
        url = os.environ.get("ORVANI_WEBAPP_URL", "").strip()
        secret = os.environ.get("ORVANI_SYNC_SECRET", "").strip()
        raw_path = os.environ.get("ORVANI_WORKBOOK_PATH", "").strip()
        raw_poll = os.environ.get("ORVANI_STATUS_POLL_SECONDS", "20").strip()
        host = os.environ.get("ORVANI_UNO_HOST", "127.0.0.1").strip()
        raw_port = os.environ.get("ORVANI_UNO_PORT", "2002").strip()

        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "script.google.com"
            or not parsed.path.endswith("/exec")
        ):
            raise ConfigurationError(
                "ORVANI_WEBAPP_URL deve ser uma URL HTTPS /exec de script.google.com."
            )

        if not re.fullmatch(r"[0-9a-fA-F]{64}", secret):
            raise ConfigurationError(
                "ORVANI_SYNC_SECRET deve ter exatamente 64 caracteres hexadecimais."
            )

        path = Path(raw_path).expanduser()
        if not raw_path or not path.is_absolute():
            raise ConfigurationError(
                "ORVANI_WORKBOOK_PATH deve ser um caminho absoluto."
            )

        try:
            poll = int(raw_poll)
        except ValueError as exc:
            raise ConfigurationError("Intervalo de polling inválido.") from exc
        if not 10 <= poll <= 300:
            raise ConfigurationError(
                "ORVANI_STATUS_POLL_SECONDS deve ficar entre 10 e 300."
            )

        if host != "127.0.0.1":
            raise ConfigurationError(
                "ORVANI_UNO_HOST deve ser 127.0.0.1 nesta versão."
            )

        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ConfigurationError("ORVANI_UNO_PORT inválida.") from exc
        if not 1 <= port <= 65535:
            raise ConfigurationError("ORVANI_UNO_PORT fora da faixa válida.")

        return cls(
            webapp_url=url,
            sync_secret=secret,
            workbook_path=path.resolve(),
            poll_seconds=poll,
            uno_host=host,
            uno_port=port,
        )
