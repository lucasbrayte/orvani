from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from automation.models import (
    ImportRecord,
    ImportStatus,
    InvalidProductDataError,
    UpdateMode,
)
from automation.sync import (
    SyncEngine,
    _is_selected,
    _permanent_error_hash,
    _record_link_hash,
)


NOW = datetime(2026, 9, 2, 20, 0, tzinfo=UTC)


def _record(**overrides):
    values = {
        "row_number": 2,
        "automation_id": "manual-shein-row-2",
        "active": "Sim",
        "publish": "Sim",
        "featured": "Não",
        "order": "1",
        "update_mode": UpdateMode.AUTOMATICO,
        "product_url": "https://br.shein.com/product-p-123456789.html",
        "affiliate_url": "https://br.shein.com/product-p-123456789.html",
        "partner": "SHEIN",
        "external_id": "",
        "name": "Camiseta de teste",
        "description": "Produto preenchido manualmente na aba Importações.",
        "category": "Moda",
        "subcategory": "Camisetas",
        "product_type": "Físico",
        "current_price": Decimal("39.70"),
        "previous_price": Decimal("49.90"),
        "calculated_discount": "",
        "coupon": "",
        "coupon_expires_at": "",
        "image_1": "https://img.ltwebstatic.com/images3_pi/2026/test.jpg",
        "image_2": "",
        "image_3": "",
        "image_4": "",
        "button_text": "Compre na SHEIN",
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


def _persisted_invalid_data_error(record):
    return replace(
        record,
        data_signature=(
            f"v1:{_record_link_hash(record)}:"
            f"{_permanent_error_hash('invalid_product_data')}"
        ),
    )


def test_shein_invalid_public_metadata_falls_back_to_manual_import_data():
    engine = SyncEngine(object(), object())
    record = _record()

    item, changes, publication = engine._plan_record(
        record,
        InvalidProductDataError("metadados públicos insuficientes"),
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.PUBLICADO
    assert item.product_changed is True
    assert changes
    assert len(publication) == 1
    assert publication[0].range_name == "'Produtos'!A6:T6"
    values = publication[0].values[0]
    assert values[2] == "shein"
    assert values[5] == "Camiseta de teste"
    assert values[7] == Decimal("49.90")
    assert values[8] == Decimal("39.70")
    assert values[11] == record.affiliate_url
    assert values[14] == record.image_1


def test_shein_fallback_fills_optional_catalog_text():
    engine = SyncEngine(object(), object())
    record = _record(
        name="",
        description="",
        category="",
        subcategory="",
        product_type="",
        button_text="",
    )

    item, _changes, publication = engine._plan_record(
        record,
        InvalidProductDataError("metadados públicos insuficientes"),
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.PUBLICADO
    assert len(publication) == 1
    values = publication[0].values[0]
    assert values[1] == "Físico"
    assert values[3] == "Outros"
    assert values[4] == "Geral"
    assert values[5] == "Produto SHEIN"
    assert values[6] == "Oferta disponível na SHEIN."
    assert values[12] == "Ver oferta na SHEIN"


def test_shein_manual_fallback_keeps_error_when_required_data_is_missing():
    engine = SyncEngine(object(), object())
    record = _record(current_price=None)

    item, _changes, publication = engine._plan_record(
        record,
        InvalidProductDataError("metadados públicos insuficientes"),
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.ERRO
    assert item.product_changed is False
    assert publication == ()


def test_pending_retries_persisted_shein_error_when_manual_fallback_is_ready():
    record = _persisted_invalid_data_error(_record())

    assert _is_selected(record, "pending", NOW) is True


def test_pending_does_not_loop_incomplete_persisted_shein_error():
    record = _persisted_invalid_data_error(_record(image_1=""))

    assert _is_selected(record, "pending", NOW) is False
