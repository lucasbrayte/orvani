from __future__ import annotations

import json
import os
from decimal import Decimal

from share_center.source import (
    HEADERS, format_brl, parse_divulgation_csv, publication_text,
)
from share_center.state import StateStore
from share_center.server import HOST, PORT

def _csv():
    header = ",".join(f'"{x}"' for x in HEADERS)
    row = (
        '"0123456789abcdef0123456789abcdef",'
        '"auto-1","B0TEST1234","Amazon","Air Fryer",'
        '"Fritadeira prática para o dia a dia.","494.99",'
        '"https://images.example/a.jpg","https://link.amazon/abc",'
        '"PENDENTE","2026-09-04T23:00:00Z"'
    )
    return header + "\n" + row + "\n"

def test_parse_divulgation_csv_is_strict_and_preserves_safe_fields():
    item = parse_divulgation_csv(_csv())[0]
    assert item.share_id == "0123456789abcdef0123456789abcdef"
    assert item.partner == "Amazon"
    assert item.price == Decimal("494.99")
    assert item.image_url == "https://images.example/a.jpg"
    assert item.affiliate_url == "https://link.amazon/abc"

def test_publication_text_has_only_approved_content():
    item = parse_divulgation_csv(_csv())[0]
    assert publication_text(item) == (
        "🛍️ Air Fryer\n\n"
        "Fritadeira prática para o dia a dia.\n\n"
        "💰 R$ 494,99\n\n"
        "🔗 Confira na loja:\nhttps://link.amazon/abc"
    )
    assert "cupom" not in publication_text(item).casefold()
    assert "desconto" not in publication_text(item).casefold()

def test_brl_formatter_uses_two_decimals():
    assert format_brl(Decimal("68.9")) == "R$ 68,90"
    assert format_brl(Decimal("1234.56")) == "R$ 1.234,56"

def test_state_store_is_atomic_private_and_rejects_unknown_status(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.set_status(
        "0123456789abcdef0123456789abcdef", "PUBLICADO",
        now="2026-09-04T23:10:00Z",
    )
    assert store.get_status(
        "0123456789abcdef0123456789abcdef"
    ) == "PUBLICADO"
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1
    assert os.stat(path).st_mode & 0o777 == 0o600
    try:
        store.set_status(
            "0123456789abcdef0123456789abcdef", "INVALIDO",
            now="2026-09-04T23:10:00Z",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("status inválido foi aceito")

def test_share_server_is_loopback_only():
    assert HOST == "127.0.0.1"
    assert PORT == 8765
