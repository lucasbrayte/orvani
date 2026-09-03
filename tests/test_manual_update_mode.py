from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from automation.models import (
    ImportRecord,
    ImportStatus,
    InvalidProductDataError,
    UpdateMode,
)
import automation.sync as sync


NOW = datetime(2026, 9, 3, 14, 30, tzinfo=UTC)


def _manual_record(**overrides):
    values = {
        "row_number": 2,
        "automation_id": "manual-row-2",
        "active": "Sim",
        "publish": "Sim",
        "featured": "Não",
        "order": "1",
        "update_mode": UpdateMode.MANUAL,
        "product_url": (
            "https://www.mercadolivre.com.br/produto/p/MLB62276281"
            "?pdp_filters=item_id%3AMLB4431628133"
        ),
        "affiliate_url": "https://meli.la/abc123",
        "partner": "Mercado Livre",
        "external_id": "",
        "name": "Panelas revisadas",
        "description": "Descrição revisada no Calc.",
        "category": "Casa",
        "subcategory": "Cozinha",
        "product_type": "Físico",
        "current_price": Decimal("189.99"),
        "previous_price": Decimal("331.42"),
        "calculated_discount": "",
        "coupon": "",
        "coupon_expires_at": "",
        "image_1": "https://http2.mlstatic.com/test.jpg",
        "image_2": "",
        "image_3": "",
        "image_4": "",
        "button_text": "Comprar",
        "status": ImportStatus.NOVO,
        "message": "",
        "consecutive_attempts": 0,
        "last_published_url": "",
        "data_signature": "",
        "last_checked_at": "",
        "last_updated_at": "",
    }
    values.update(overrides)
    return ImportRecord(**values)


def test_manual_snapshot_preserves_reviewed_catalog_fields():
    record = _manual_record()

    snapshot = sync._manual_import_snapshot(record, NOW)

    assert snapshot.partner == "mercado_livre"
    assert snapshot.external_id == "MLB4431628133"
    assert snapshot.name == record.name
    assert snapshot.description == record.description
    assert snapshot.current_price == Decimal("189.99")
    assert snapshot.previous_price == Decimal("331.42")
    assert snapshot.images == (record.image_1,)
    assert snapshot.affiliate_url == record.affiliate_url


def test_manual_snapshot_rejects_missing_required_text():
    with pytest.raises(InvalidProductDataError):
        sync._manual_import_snapshot(_manual_record(name=""), NOW)


def test_manual_snapshot_rejects_invalid_promotion():
    with pytest.raises(InvalidProductDataError):
        sync._manual_import_snapshot(
            _manual_record(
                current_price=Decimal("200.00"),
                previous_price=Decimal("199.00"),
            ),
            NOW,
        )


def test_manual_snapshot_rejects_product_without_safe_identity():
    with pytest.raises(InvalidProductDataError):
        sync._manual_import_snapshot(
            _manual_record(
                product_url=(
                    "https://www.mercadolivre.com.br/produto/p/MLB62276281"
                ),
            ),
            NOW,
        )

def test_manual_mode_does_not_select_public_connector():
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS, PRODUCTS_HEADERS

    record = _manual_record()
    calls = []

    class Connector:
        partner_key = "mercado_livre"

        def fetch(self, _url):
            return sync._manual_import_snapshot(record, NOW)

    class Registry:
        def select(self, _url):
            calls.append("select")
            return Connector()

    sheets = FakeSheetsGateway(
        sheets=(
            {
                "properties": {
                    "sheetId": 1,
                    "title": "Importações",
                    "sheetType": "GRID",
                    "gridProperties": {"rowCount": 20, "columnCount": 32},
                }
            },
            {
                "properties": {
                    "sheetId": 2,
                    "title": "Produtos",
                    "sheetType": "GRID",
                    "gridProperties": {"rowCount": 20, "columnCount": 20},
                }
            },
        ),
        values={
            _quoted("Importações", "A1:AF"): [
                list(IMPORT_HEADERS),
                list(sync._record_values(record)),
            ],
            _quoted("Produtos", "A4:T"): [list(PRODUCTS_HEADERS)],
        },
    )

    report = sync.SyncEngine(
        sheets,
        Registry(),
        clock=lambda: NOW,
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.PUBLICADO
    assert calls == []

def test_manual_publication_uses_calc_values_verbatim():
    engine = sync.SyncEngine(object(), object())
    record = _manual_record(
        name="Nome do Calc",
        description="Descrição do Calc",
        category="Casa",
        subcategory="Cozinha",
        current_price=Decimal("189.99"),
        previous_price=Decimal("331.42"),
        image_1="https://http2.mlstatic.com/manual.jpg",
    )
    snapshot = sync._manual_import_snapshot(record, NOW)

    item, _changes, publication = engine._plan_record(
        record,
        snapshot,
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.PUBLICADO
    assert len(publication) == 1

    values = publication[0].values[0]
    assert values[3] == "Casa"
    assert values[4] == "Cozinha"
    assert values[5] == "Nome do Calc"
    assert values[6] == "Descrição do Calc"
    assert values[7] == Decimal("331.42")
    assert values[8] == Decimal("189.99")
    assert values[14] == "https://http2.mlstatic.com/manual.jpg"

def test_manual_snapshot_parses_coupon_expiry_date():
    snapshot = sync._manual_import_snapshot(
        _manual_record(
            coupon="ORVANI10",
            coupon_expires_at="2026-09-30",
        ),
        NOW,
    )

    assert snapshot.coupon == "ORVANI10"
    assert snapshot.coupon_expires_at == datetime(2026, 9, 30, tzinfo=UTC)


def test_manual_snapshot_rejects_invalid_coupon_expiry():
    with pytest.raises(InvalidProductDataError):
        sync._manual_import_snapshot(
            _manual_record(
                coupon="ORVANI10",
                coupon_expires_at="30/09/2026",
            ),
            NOW,
        )
