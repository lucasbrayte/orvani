from __future__ import annotations

import hashlib
import hmac
import json
import re

SECRET_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def signed_envelope(
    action: str,
    payload: dict[str, object],
    *,
    secret: str,
    timestamp: int,
    nonce: str,
) -> dict[str, object]:
    if not SECRET_RE.fullmatch(secret):
        raise ValueError("ORVANI_SYNC_SECRET deve conter 64 caracteres hexadecimais.")
    if not isinstance(timestamp, int):
        raise ValueError("timestamp inválido.")
    if not isinstance(nonce, str) or len(nonce) < 12:
        raise ValueError("nonce inválido.")

    unsigned = {
        "version": "v1",
        "action": action,
        "timestamp": timestamp,
        "nonce": nonce,
        "payload": payload,
    }
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical_json(unsigned).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**unsigned, "signature": signature}
