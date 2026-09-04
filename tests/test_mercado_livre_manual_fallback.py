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


NOW = datetime(2026, 9, 3, 3, 40, tzinfo=UTC)


def _record(**overrides):
    values = {
        "row_number": 2,
        "automation_id": "manual-mercado-row-2",
        "active": "Sim",
        "publish": "Sim",
        "featured": "Não",
        "order": "1",
        "update_mode": UpdateMode.AUTOMATICO,
        "product_url": (
            "https://www.mercadolivre.com.br/conjunto-de-panelas/p/MLB62276281"
            "?pdp_filters=item_id%3AMLB4431628133"
        ),
        "affiliate_url": "https://meli.la/abc123",
        "partner": "Mercado Livre",
        "external_id": "",
        "name": "Conjunto de panelas antiaderente 10 peças",
        "description": "Produto preenchido manualmente na aba Importações.",
        "category": "Casa",
        "subcategory": "Cozinha",
        "product_type": "Físico",
        "current_price": Decimal("189.99"),
        "previous_price": Decimal("331.42"),
        "calculated_discount": "",
        "coupon": "",
        "coupon_expires_at": "",
        "image_1": "https://http2.mlstatic.com/D_NQ_NP_123456-MLB.jpg",
        "image_2": "",
        "image_3": "",
        "image_4": "",
        "button_text": "Compre no Mercado Livre",
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


def test_mercado_livre_invalid_public_metadata_falls_back_to_manual_import_data():
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
    assert item.message == "Produto publicado via fallback manual do Mercado Livre."
    assert changes
    assert len(publication) == 1
    assert publication[0].range_name == "'Produtos'!A6:T6"
    values = publication[0].values[0]
    assert values[2] == "mercado_livre"
    assert values[5] == record.name
    assert values[7] == Decimal("331.42")
    assert values[8] == Decimal("189.99")
    assert values[11] == record.affiliate_url
    assert values[14] == record.image_1


def test_mercado_livre_fallback_fills_optional_catalog_text():
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
    assert values[5] == "Produto Mercado Livre"
    assert values[6] == "Oferta disponível no Mercado Livre."
    assert values[12] == "Ver oferta na Mercado Livre"


def test_mercado_livre_manual_fallback_requires_trusted_offer_identity():
    engine = SyncEngine(object(), object())
    record = _record(
        product_url="https://www.mercadolivre.com.br/conjunto-de-panelas/p/MLB62276281"
    )

    item, _changes, publication = engine._plan_record(
        record,
        InvalidProductDataError("metadados públicos insuficientes"),
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.ERRO
    assert item.product_changed is False
    assert publication == ()


def test_mercado_livre_manual_fallback_rejects_untrusted_affiliate_url():
    engine = SyncEngine(object(), object())
    record = _record(affiliate_url="https://evil.example/affiliate")

    item, _changes, publication = engine._plan_record(
        record,
        InvalidProductDataError("metadados públicos insuficientes"),
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.ERRO
    assert item.product_changed is False
    assert publication == ()


def test_pending_retries_persisted_mercado_livre_error_when_manual_fallback_is_ready():
    record = _persisted_invalid_data_error(_record())

    assert _is_selected(record, "pending", NOW) is True


def test_pending_does_not_loop_incomplete_persisted_mercado_livre_error():
    record = _persisted_invalid_data_error(_record(image_1=""))

    assert _is_selected(record, "pending", NOW) is False
