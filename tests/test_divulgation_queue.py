from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from automation.config import DIVULGATION_HEADERS
from automation.models import ImportRecord, ImportStatus, ProductRow, UpdateMode
from automation.sheets import ensure_divulgation_sheet
from automation.sync import (
    SyncEngine,
    plan_divulgation_update,
    should_queue_divulgation,
)

NOW = datetime(2026, 9, 4, 23, 0, tzinfo=UTC)

def _record(status=ImportStatus.NOVO):
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
        button_text="Ver oferta", status=status, message="",
        consecutive_attempts=0, last_published_url="",
        data_signature="", last_checked_at="", last_updated_at="",
    )

def _product(row_number=6):
    return ProductRow(
        row_number=row_number, active="Sim", product_type="Físico",
        partner="mercado_livre", category="Casa", subcategory="Cozinha",
        name="Air Fryer de teste",
        description=(
            "Uma descrição longa de produto para a fila de divulgação. "
            "Ela deve ser reduzida com segurança sem perder o sentido."
        ),
        price=Decimal("100.00"), promotional_price=Decimal("89.90"),
        coupon="", offer_expires_at="", affiliate_url="https://meli.la/item",
        button_text="Ver oferta", video_url="",
        image_1="https://images.example/item.jpg",
        image_2="", image_3="", image_4="",
        order="", featured="Não", reconstructed_external_id="MLB123",
    )

def test_divulgation_contract_is_small_and_stable():
    assert DIVULGATION_HEADERS == (
        "ID Divulgação", "ID Automação", "ID Externo", "Plataforma", "Nome",
        "Descrição Curta", "Preço", "Imagem", "Link Afiliado",
        "Status WhatsApp", "Criado em",
    )

def test_first_publication_plans_one_pending_divulgation():
    update = plan_divulgation_update(
        _record(), _product(), existing_ids=set(), row_number=2,
        created_at=NOW, worksheet="Divulgação",
    )
    assert update is not None
    assert update.range_name == "'Divulgação'!A2:K2"
    row = update.values[0]
    assert len(row) == len(DIVULGATION_HEADERS)
    assert row[1] == "550e8400-e29b-41d4-a716-446655440000"
    assert row[3] == "Mercado Livre"
    assert row[4] == "Air Fryer de teste"
    assert row[6] == Decimal("89.90")
    assert row[7] == "https://images.example/item.jpg"
    assert row[8] == "https://meli.la/item"
    assert row[9] == "PENDENTE"
    assert row[10] == "2026-09-04T23:00:00Z"
    assert len(row[0]) == 32

def test_same_automation_id_never_plans_a_duplicate():
    first = plan_divulgation_update(
        _record(), _product(), existing_ids=set(), row_number=2,
        created_at=NOW, worksheet="Divulgação",
    )
    assert first is not None
    assert plan_divulgation_update(
        _record(), _product(), existing_ids={first.values[0][0]},
        row_number=3, created_at=NOW, worksheet="Divulgação",
    ) is None

def test_only_first_transition_to_published_enters_queue():
    assert should_queue_divulgation(
        ImportStatus.NOVO, ImportStatus.PUBLICADO
    ) is True
    assert should_queue_divulgation(
        ImportStatus.REVISAR, ImportStatus.PUBLICADO
    ) is True
    assert should_queue_divulgation(
        ImportStatus.PUBLICADO, ImportStatus.PUBLICADO
    ) is False
    assert should_queue_divulgation(
        ImportStatus.NOVO, ImportStatus.REVISAR
    ) is False

class SetupGateway:
    def __init__(self):
        self.requests = []
        self.value_writes = []
    def get_spreadsheet(self):
        return {"sheets": []}
    def get_values(self, _range_name):
        return {"values": []}
    def batch_update(self, requests):
        self.requests.extend(requests)
    def batch_values_update(self, data, value_input_option):
        self.value_writes.append((data, value_input_option))

def test_divulgation_sheet_setup_is_idempotent_and_dry_run_safe():
    gateway = SetupGateway()
    assert ensure_divulgation_sheet(gateway, "Divulgação", dry_run=True) is True
    assert gateway.requests == []
    assert gateway.value_writes == []
    assert ensure_divulgation_sheet(gateway, "Divulgação", dry_run=False) is True
    update = next(
        req["updateCells"] for req in gateway.requests if "updateCells" in req
    )
    headers = [
        cell["userEnteredValue"]["stringValue"]
        for cell in update["rows"][0]["values"]
    ]
    assert tuple(headers) == DIVULGATION_HEADERS

def test_sync_engine_dry_run_queues_first_successful_publication():
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS, PRODUCTS_HEADERS
    from automation.models import ProductSnapshot

    record = [
        "550e8400-e29b-41d4-a716-446655440000",
        "Sim", "Sim", "Não", "", "Automático",
        "https://www.mercadolivre.com.br/item/MLB123",
        "https://meli.la/item", "mercado_livre", "MLB123",
        "Produto", "Descrição", "Casa", "Cozinha", "Físico",
        89.90, 100.00, "10", "", "",
        "https://images.example/item.jpg", "", "", "", "Ver oferta",
        "NOVO", "", 0, "", "", "", "",
    ]
    sheets = (
        {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID",
         "gridProperties": {"rowCount": 100, "columnCount": 32}}},
        {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID",
         "gridProperties": {"rowCount": 100, "columnCount": 20}}},
        {"properties": {"sheetId": 3, "title": "Divulgação", "sheetType": "GRID",
         "gridProperties": {"rowCount": 100, "columnCount": 32}}},
    )
    values = {
        _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), record],
        _quoted("Produtos", "A4:T"): [list(PRODUCTS_HEADERS)],
        _quoted("Divulgação", "A1:K1"): [list(DIVULGATION_HEADERS)],
        _quoted("Divulgação", "A1:K"): [list(DIVULGATION_HEADERS)],
    }
    gateway = FakeSheetsGateway(sheets=sheets, values=values)

    class Registry:
        def select(self, _url):
            class Connector:
                partner_key = "mercado_livre"
                def fetch(self, url):
                    return ProductSnapshot(
                        partner="mercado_livre", external_id="MLB123",
                        catalog_id=None, source_url=url, affiliate_url=url,
                        name="Produto", description="Descrição",
                        current_price=Decimal("89.90"),
                        previous_price=Decimal("100.00"), currency="BRL",
                        category="Casa", subcategory="Cozinha",
                        product_type="Físico", coupon=None,
                        coupon_expires_at=None,
                        images=("https://images.example/item.jpg",),
                        available=True, fetched_at=NOW,
                    )
            return Connector()

    report = SyncEngine(
        gateway, Registry(), clock=lambda: NOW,
        divulgation_worksheet="Divulgação",
    ).run("pending", dry_run=True)
    assert report.final_status(2) is ImportStatus.PUBLICADO
    assert len(report.planned_product_updates) == 1
    assert len(report.planned_divulgation_updates) == 1
