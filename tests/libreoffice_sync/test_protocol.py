import hashlib
import hmac

from libreoffice_sync.protocol import canonical_json, signed_envelope


def test_canonical_json_matches_apps_script_vector():
    value = {"z": 1, "a": {"y": 2, "b": "ç"}, "list": [{"d": 4, "c": 3}]}
    assert canonical_json(value) == (
        '{"a":{"b":"ç","y":2},"list":[{"c":3,"d":4}],"z":1}'
    )


def test_signed_envelope_signature_is_stable():
    secret = "0123456789abcdef" * 4
    envelope = signed_envelope(
        "health",
        {},
        secret=secret,
        timestamp=1788420000,
        nonce="nonce_1234567890abcdef",
    )
    unsigned = {
        key: envelope[key]
        for key in ("version", "action", "timestamp", "nonce", "payload")
    }
    expected = hmac.new(
        secret.encode(),
        canonical_json(unsigned).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert envelope["signature"] == expected
