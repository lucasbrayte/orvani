
from __future__ import annotations

from pathlib import Path

from libreoffice_sync.models import BackendStatus
from libreoffice_sync.uno_client import LibreOfficeWorkbook


EXPECTED = Path("/tmp/Orvani.ods")


class FakeCell:
    def __init__(self, string="", value=0.0):
        self.String = string
        self.Value = value


class FakeCursor:
    def __init__(self, sheet):
        self.sheet = sheet
        self.RangeAddress = type("RangeAddress", (), {"EndRow": sheet.end_row})()

    def gotoEndOfUsedArea(self, _):
        self.RangeAddress.EndRow = self.sheet.end_row


class FakeColumn:
    def __init__(self):
        self.IsVisible = True


class FakeColumns:
    def __init__(self, count=34):
        self._columns = [FakeColumn() for _ in range(count)]

    def getByIndex(self, index):
        return self._columns[index]


class FakeSheet:
    def __init__(self):
        self.cells = {}
        self.end_row = 1
        self.Columns = FakeColumns()

    def getCellByPosition(self, col, row):
        self.end_row = max(self.end_row, row)
        return self.cells.setdefault((col, row), FakeCell())

    def createCursor(self):
        return FakeCursor(self)


class FakeSheets:
    def __init__(self, sheet):
        self.sheet = sheet

    def hasByName(self, name):
        return name == "Catálogo"

    def getByName(self, name):
        assert name == "Catálogo"
        return self.sheet


class FakeDocument:
    def __init__(self, sheet):
        self.Sheets = FakeSheets(sheet)
        self.URL = EXPECTED.as_uri()
        self.listener = None

    def addDocumentEventListener(self, listener):
        self.listener = listener


def seed_row(sheet):
    values = {
        0: "Sim",
        1: "Sim",
        2: "Não",
        3: "1",
        4: "Manual",
        5: "https://www.mercadolivre.com.br/produto/p/MLB12345678",
        6: "https://meli.la/teste",
        7: "Mercado Livre",
        8: "Produto",
        9: "Descrição",
        10: "Casa",
        11: "Cozinha",
        12: "Físico",
        15: "ORVANI10",
        16: "2026-09-30",
        17: "https://example.com/1.jpg",
        21: "Ver oferta",
        27: "uuid-1",
        32: "hash-local",
        33: "hash-ok",
    }
    for col, value in values.items():
        sheet.getCellByPosition(col, 1).String = value
    sheet.getCellByPosition(13, 1).Value = 189.99
    sheet.getCellByPosition(14, 1).Value = 331.42


def test_read_catalog_row_maps_documented_columns_only():
    sheet = FakeSheet()
    seed_row(sheet)
    workbook = LibreOfficeWorkbook.from_document(FakeDocument(sheet), EXPECTED)

    rows = workbook.read_catalog_rows()

    assert len(rows) == 1
    row = rows[0]
    assert row.row_number == 2
    assert row.automation_id == "uuid-1"
    assert row.name == "Produto"
    assert str(row.current_price) == "189.99"
    assert row.images[0] == "https://example.com/1.jpg"
    assert row.acknowledged_hash == "hash-ok"


def test_ensure_automation_id_is_stable():
    sheet = FakeSheet()
    workbook = LibreOfficeWorkbook.from_document(FakeDocument(sheet), EXPECTED)

    first = workbook.ensure_automation_id(2)
    second = workbook.ensure_automation_id(2)

    assert first == second
    assert len(first) == 36
    assert sheet.getCellByPosition(27, 1).String == first


def test_local_error_writes_only_status_and_message():
    sheet = FakeSheet()
    seed_row(sheet)
    before_name = sheet.getCellByPosition(8, 1).String
    workbook = LibreOfficeWorkbook.from_document(FakeDocument(sheet), EXPECTED)

    workbook.write_local_error(2, "Preço Atual é obrigatório.")

    assert sheet.getCellByPosition(22, 1).String == "ERRO LOCAL"
    assert sheet.getCellByPosition(23, 1).String == "Preço Atual é obrigatório."
    assert sheet.getCellByPosition(8, 1).String == before_name


def test_apply_status_updates_backend_and_technical_columns_without_editable_fields():
    sheet = FakeSheet()
    seed_row(sheet)
    workbook = LibreOfficeWorkbook.from_document(FakeDocument(sheet), EXPECTED)

    status = BackendStatus(
        automation_id="uuid-1",
        external_id="MLB12345678",
        status="PUBLICADO",
        message="Produto publicado.",
        discount="43",
        last_published_url="https://meli.la/teste",
        data_signature="signature",
        last_checked_at="2026-09-03T16:00:00Z",
        last_updated_at="2026-09-03T16:00:02Z",
    )

    assert workbook.apply_status(status) is True
    assert sheet.getCellByPosition(22, 1).String == "PUBLICADO"
    assert sheet.getCellByPosition(23, 1).String == "Produto publicado."
    assert sheet.getCellByPosition(24, 1).String == "43"
    assert sheet.getCellByPosition(25, 1).String == "2026-09-03T16:00:00Z"
    assert sheet.getCellByPosition(26, 1).String == "2026-09-03T16:00:02Z"
    assert sheet.getCellByPosition(28, 1).String == "MLB12345678"
    assert sheet.getCellByPosition(29, 1).String == "https://meli.la/teste"
    assert sheet.getCellByPosition(30, 1).String == "signature"
    assert sheet.getCellByPosition(8, 1).String == "Produto"


def test_save_event_can_be_consumed_once():
    sheet = FakeSheet()
    doc = FakeDocument(sheet)
    workbook = LibreOfficeWorkbook.from_document(doc, EXPECTED)

    assert workbook.consume_save_event() is False
    workbook.mark_saved()
    assert workbook.consume_save_event() is True
    assert workbook.consume_save_event() is False
