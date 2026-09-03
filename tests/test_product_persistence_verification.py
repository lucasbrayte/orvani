from datetime import UTC, datetime
from decimal import Decimal

import pytest

from automation.config import IMPORT_HEADERS, PRODUCTS_HEADERS
from automation.models import ConfigurationError, ImportRecord, ImportStatus, ProductSnapshot
from automation.sync import SyncEngine, _record_values
from conftest import FakeSheetsGateway, _quoted


class _Registry:
    def select(self, _url):
        class Connector:
            partner_key = "mercado_livre"

            def fetch(self, url):
                return ProductSnapshot(
                    partner="mercado_livre",
                    external_id="MLB123",
                    catalog_id=None,
                    source_url="https://www.mercadolivre.com.br/item/MLB123",
                    affiliate_url=url,
                    name="Produto persistência",
                    description="Descrição persistência",
                    current_price=Decimal("149.90"),
                    previous_price=Decimal("199.90"),
                    currency="BRL",
                    category="Eletrônicos",
                    subcategory="Áudio",
                    product_type="Físico",
                    coupon=None,
                    coupon_expires_at=None,
                    images=("https://images.example/persist.jpg",),
                    available=True,
                    fetched_at=datetime(2026, 9, 2, 22, 0, tzinfo=UTC),
                )

        return Connector()


class _Settings:
    service_account_info = {
        "type": "service_account",
        "client_email": "bot@example.invalid",
        "private_key": "key",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    spreadsheet_id = "sheet-id"
    import_worksheet = "Importações"
    products_worksheet = "Produtos"


class _DropProductWrites(FakeSheetsGateway):
    """Simula a API aceitando a escrita, mas a linha não ficando disponível na releitura."""

    def batch_values_update(self, data, value_input_option):
        super().batch_values_update(data, value_input_option)
        for item in data:
            if item["range"].startswith("'Produtos'!"):
                self._values.pop(item["range"], None)


def _record():
    values = [
        "auto-persist-1",
        "Sim",
        "Sim",
        "Não",
        "9",
        "Automático",
        "https://www.mercadolivre.com.br/item/MLB123",
        "https://meli.la/current?b=2&a=1",
        "mercado_livre",
        "MLB123",
        "Produto persistência",
        "Descrição persistência",
        "Eletrônicos",
        "Áudio",
        "Físico",
        Decimal("149.90"),
        Decimal("199.90"),
        "25",
        "",
        "",
        "https://images.example/persist.jpg",
        "",
        "",
        "",
        "",
        "NOVO",
        "",
        0,
        "",
        "",
        "",
        "",
    ]
    record, planned = ImportRecord.from_sheet_row(2, values)
    assert planned is None
    return record


def _gateway(gateway_type=FakeSheetsGateway):
    imported = _record()
    return gateway_type(
        sheets=(
            {
                "properties": {
                    "sheetId": 1,
                    "title": "Importações",
                    "sheetType": "GRID",
                    "gridProperties": {"rowCount": 100, "columnCount": 32},
                }
            },
            {
                "properties": {
                    "sheetId": 2,
                    "title": "Produtos",
                    "sheetType": "GRID",
                    "gridProperties": {"rowCount": 100, "columnCount": 20},
                }
            },
        ),
        values={
            _quoted("Importações", "A1:AF"): [
                list(IMPORT_HEADERS),
                list(_record_values(imported)),
            ],
            _quoted("Produtos", "A4:T"): [list(PRODUCTS_HEADERS)],
        },
    )


def _written_ranges(gateway):
    return [
        item["range"]
        for batch in gateway.value_writes
        for item in batch["data"]
    ]


def test_live_sync_requires_product_readback_before_publicado():
    sheets = _gateway(_DropProductWrites)

    with pytest.raises(ConfigurationError, match="confirmar"):
        SyncEngine(sheets, _Registry()).run("pending", dry_run=False)

    assert "'Produtos'!A6:T6" in _written_ranges(sheets)
    assert "'Produtos'!A6:T6" in sheets.value_reads
    assert "'Importações'!A2:AF2" not in _written_ranges(sheets)


def test_live_sync_confirms_persisted_product_before_terminal_publication():
    sheets = _gateway()

    report = SyncEngine(sheets, _Registry()).run("pending", dry_run=False)

    assert report.final_status(2) is ImportStatus.PUBLICADO
    assert "'Produtos'!A6:T6" in sheets.value_reads

    ranges = _written_ranges(sheets)
    assert ranges.index("'Produtos'!A6:T6") < ranges.index("'Importações'!A2:AF2")


def test_cli_reports_exact_planned_product_range(capsys):
    from automation.cli import CliDependencies, main

    sheets = _gateway()
    dependencies = CliDependencies(
        settings=_Settings(),
        gateway=sheets,
        registry=_Registry(),
    )

    assert main(["sync", "--mode", "pending", "--dry-run"], dependencies) == 0
    output = capsys.readouterr().out
    assert "produtos_ranges='Produtos'!A6:T6" in output
