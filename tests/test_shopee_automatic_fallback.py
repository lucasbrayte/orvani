from datetime import UTC, datetime
from decimal import Decimal

from automation.models import ImportRecord, ImportStatus, InvalidProductDataError, UpdateMode
from automation.sync import SyncEngine

NOW = datetime(2026, 9, 3, 22, 30, tzinfo=UTC)


def _record(**overrides):
    values = {
        "row_number": 2,
        "automation_id": "shopee-fallback-row-2",
        "active": "Sim",
        "publish": "Sim",
        "featured": "Não",
        "order": "1",
        "update_mode": UpdateMode.AUTOMATICO,
        "product_url": "https://shopee.com.br/produto-teste-i.123456789.987654321",
        "affiliate_url": "https://s.shopee.com.br/abc123",
        "partner": "Shopee",
        "external_id": "",
        "name": "Produto Shopee revisado",
        "description": "Dados preenchidos no LibreOffice Calc.",
        "category": "Casa",
        "subcategory": "Utilidades",
        "product_type": "Físico",
        "current_price": Decimal("133.76"),
        "previous_price": Decimal("199.90"),
        "calculated_discount": "",
        "coupon": "",
        "coupon_expires_at": "",
        "image_1": "https://down-br.img.susercontent.com/file/test-image",
        "image_2": "",
        "image_3": "",
        "image_4": "",
        "button_text": "Ver Oferta",
        "status": ImportStatus.ERRO,
        "message": "Dados públicos do produto são inválidos.",
        "consecutive_attempts": 0,
        "last_published_url": "",
        "data_signature": "",
        "last_checked_at": "",
        "last_updated_at": "",
    }
    values.update(overrides)
    return ImportRecord(**values)


def test_shopee_invalid_public_metadata_falls_back_to_calc_data():
    engine = SyncEngine(object(), object())
    record = _record()
    item, changes, publication = engine._plan_record(
        record, InvalidProductDataError("metadados públicos insuficientes"), (), NOW
    )
    assert item.final_status is ImportStatus.PUBLICADO
    assert item.product_changed is True
    assert item.message == "Produto publicado via fallback manual do Shopee."
    assert changes
    assert len(publication) == 1
    values = publication[0].values[0]
    assert values[2] == "shopee"
    assert values[5] == record.name
    assert values[7] == Decimal("199.90")
    assert values[8] == Decimal("133.76")
    assert values[11] == record.affiliate_url
    assert values[14] == record.image_1


def test_shopee_fallback_stays_error_when_required_calc_data_is_missing():
    engine = SyncEngine(object(), object())
    record = _record(name="")
    item, _changes, publication = engine._plan_record(
        record, InvalidProductDataError("metadados públicos insuficientes"), (), NOW
    )
    assert item.final_status is ImportStatus.ERRO
    assert item.product_changed is False
    assert publication == ()


def test_shopee_fallback_requires_safe_identity():
    engine = SyncEngine(object(), object())
    record = _record(product_url="https://shopee.com.br/produto-sem-id")
    item, _changes, publication = engine._plan_record(
        record, InvalidProductDataError("metadados públicos insuficientes"), (), NOW
    )
    assert item.final_status is ImportStatus.ERRO
    assert publication == ()
