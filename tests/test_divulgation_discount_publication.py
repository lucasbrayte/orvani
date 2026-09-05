from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from automation.config import DIVULGATION_HEADERS
from automation.models import ImportRecord, ImportStatus, ProductRow, UpdateMode
from automation.sheets import ensure_divulgation_sheet, read_table
from automation.sync import plan_divulgation_update
from share_center.source import HEADERS, parse_divulgation_csv, publication_text

NOW = datetime(2026, 9, 5, 20, 0, tzinfo=UTC)


def record():
    return ImportRecord(
        row_number=2,
        automation_id="550e8400-e29b-41d4-a716-446655440000",
        active="Sim", publish="Sim", featured="Não", order="",
        update_mode=UpdateMode.AUTOMATICO,
        product_url="https://www.mercadolivre.com.br/item/MLB123",
        affiliate_url="https://meli.la/item",
        partner="mercado_livre", external_id="MLB123",
        name="Produto", description="Descrição",
        category="Casa", subcategory="Cozinha", product_type="Físico",
        current_price=Decimal("89.90"),
        previous_price=Decimal("100.00"),
        calculated_discount="10", coupon="", coupon_expires_at="",
        image_1="https://images.example/item.jpg",
        image_2="", image_3="", image_4="",
        button_text="Ver oferta", status=ImportStatus.NOVO, message="",
        consecutive_attempts=0, last_published_url="",
        data_signature="", last_checked_at="", last_updated_at="",
    )


def product(*, price="100.00", promotional="89.90"):
    return ProductRow(
        row_number=6, active="Sim", product_type="Físico",
        partner="mercado_livre", category="Casa", subcategory="Cozinha",
        name="Air Fryer", description="Produto em promoção.",
        price=Decimal(price),
        promotional_price=None if promotional is None else Decimal(promotional),
        coupon="", offer_expires_at="",
        affiliate_url="https://meli.la/item",
        button_text="Ver oferta", video_url="",
        image_1="https://images.example/item.jpg",
        image_2="", image_3="", image_4="",
        order="", featured="Não", reconstructed_external_id="MLB123",
    )


def csv_text(*, previous="", discount="", legacy=False):
    headers = HEADERS[:-2] if legacy else HEADERS
    row = [
        "0123456789abcdef0123456789abcdef",
        "auto-1", "MLB123", "Mercado Livre", "Air Fryer",
        "Produto em promoção.", "89.90",
        "https://images.example/item.jpg", "https://meli.la/item",
        "PENDENTE", "2026-09-05T20:00:00Z",
    ]
    if not legacy:
        row.extend([previous, discount])
    q = lambda values: ",".join(f'"{value}"' for value in values)
    return q(headers) + "\n" + q(row) + "\n"


def test_new_rows_store_previous_price_and_discount():
    assert DIVULGATION_HEADERS[-2:] == ("Preço Anterior", "Desconto")
    assert HEADERS[-2:] == ("Preço Anterior", "Desconto")
    update = plan_divulgation_update(
        record(), product(), existing_ids=set(), row_number=2,
        created_at=NOW, worksheet="Divulgação",
    )
    assert update is not None
    assert update.range_name == "'Divulgação'!A2:M2"
    row = update.values[0]
    assert row[6] == Decimal("89.90")
    assert row[11] == Decimal("100.00")
    assert row[12] == 10


def test_non_promotional_and_inconsistent_prices_do_not_claim_discount():
    normal = plan_divulgation_update(
        record(), product(promotional=None),
        existing_ids=set(), row_number=2,
        created_at=NOW, worksheet="Divulgação",
    )
    assert normal is not None
    assert normal.values[0][6] == Decimal("100.00")
    assert normal.values[0][11:] == ("", "")

    inconsistent = plan_divulgation_update(
        record(), product(promotional="120.00"),
        existing_ids=set(), row_number=3,
        created_at=NOW, worksheet="Divulgação",
    )
    assert inconsistent is not None
    assert inconsistent.values[0][6] == Decimal("100.00")
    assert inconsistent.values[0][11:] == ("", "")


def test_publication_uses_whatsapp_discount_format():
    item = parse_divulgation_csv(
        csv_text(previous="100.00", discount="10")
    )[0]
    text = publication_text(item)
    assert "🔥 *10% OFF*" in text
    assert "De: ~R$ 100,00~" in text
    assert "Por: *R$ 89,90*" in text
    assert "💰 R$ 89,90" not in text


def test_legacy_rows_never_gain_discount_retroactively():
    item = parse_divulgation_csv(csv_text(legacy=True))[0]
    text = publication_text(item)
    assert "OFF" not in text
    assert "De:" not in text
    assert "💰 R$ 89,90" in text


def test_wrong_stored_discount_falls_back_to_normal_publication():
    item = parse_divulgation_csv(
        csv_text(previous="100.00", discount="35")
    )[0]
    text = publication_text(item)
    assert "OFF" not in text
    assert "De:" not in text
    assert "💰 R$ 89,90" in text


class LegacyGateway:
    def __init__(self):
        self.value_writes = []

    def get_spreadsheet(self):
        return {"sheets": [{
            "properties": {
                "sheetId": 3, "title": "Divulgação", "sheetType": "GRID",
                "gridProperties": {"rowCount": 100, "columnCount": 32},
            }
        }]}

    def get_values(self, range_name):
        if range_name == "'Divulgação'!A1:M1":
            return {"values": [list(DIVULGATION_HEADERS[:-2])]}
        if range_name == "'Divulgação'!A1:M":
            return {"values": [
                list(DIVULGATION_HEADERS[:-2]),
                [
                    "0123456789abcdef0123456789abcdef",
                    "auto-1", "MLB123", "Mercado Livre", "Produto",
                    "Descrição", 89.90,
                    "https://images.example/item.jpg",
                    "https://meli.la/item", "PUBLICADO",
                    "2026-09-04T20:00:00Z",
                ],
            ]}
        raise AssertionError(f"range inesperado: {range_name}")

    def batch_values_update(self, data, value_input_option):
        self.value_writes.append((data, value_input_option))

    def batch_update(self, _requests):
        raise AssertionError("não deve recriar a aba existente")


def test_existing_sheet_appends_only_new_headers():
    gateway = LegacyGateway()
    assert ensure_divulgation_sheet(
        gateway, "Divulgação", dry_run=False
    ) is False
    assert gateway.value_writes == [(
        [{
            "range": "'Divulgação'!L1:M1",
            "values": [["Preço Anterior", "Desconto"]],
        }],
        "RAW",
    )]


def test_dry_run_reads_legacy_sheet_without_writing():
    gateway = LegacyGateway()
    assert ensure_divulgation_sheet(
        gateway, "Divulgação", dry_run=True
    ) is False
    rows = read_table(gateway, "Divulgação", headers=DIVULGATION_HEADERS)
    assert len(rows) == 1
    assert rows[0][0] == "0123456789abcdef0123456789abcdef"
    assert gateway.value_writes == []
