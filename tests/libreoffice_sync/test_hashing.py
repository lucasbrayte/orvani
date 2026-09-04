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

def test_payload_normalizes_choices_and_infers_partner(valid_row):
    row = replace(
        valid_row,
        active="sim",
        publish="SIM",
        featured="não",
        update_mode="",
        partner="",
        product_type="fisico",
        product_url="https://shopee.com.br/produto-i.123.456",
        affiliate_url="https://s.shopee.com.br/abc123",
    )

    payload = editable_payload(row)

    assert payload["Ativo"] == "Sim"
    assert payload["Publicar"] == "Sim"
    assert payload["Destaque"] == "Não"
    assert payload["Modo de Atualização"] == "Automático"
    assert payload["Plataforma"] == "Shopee"
    assert payload["Tipo"] == "Físico"


def test_payload_omits_blank_prices(valid_row):
    payload = editable_payload(
        replace(valid_row, current_price=None, previous_price=None)
    )

    assert "Preço Atual" not in payload
    assert "Preço Anterior" not in payload
