from dataclasses import replace
from decimal import Decimal

from libreoffice_sync.hashing import editable_payload, row_hash


def test_hash_changes_when_editable_price_changes(valid_row):
    first = row_hash(valid_row)
    second = row_hash(replace(valid_row, current_price=Decimal("190.00")))
    assert first != second


def test_hash_ignores_backend_status_fields(valid_row):
    payload = editable_payload(valid_row)
    assert "Status" not in payload
    assert "Mensagem" not in payload
    assert "ID Externo" not in payload


def test_editable_payload_uses_exact_apps_script_keys(valid_row):
    payload = editable_payload(valid_row)
    assert payload["ID Automação"] == "uuid-1"
    assert payload["Modo de Atualização"] == "Manual"
    assert payload["Preço Atual"] == "189.99"
    assert payload["Preço Anterior"] == "331.42"
    assert payload["Texto do Botão"] == "Ver oferta"
