
from libreoffice_sync.workbook_init import ALL_HEADERS, configure_catalog_sheet


class FakeCell:
    def __init__(self):
        self.String = ""


class FakeColumn:
    def __init__(self):
        self.IsVisible = True


class FakeColumns:
    def __init__(self, count=34):
        self.columns = [FakeColumn() for _ in range(count)]

    def getByIndex(self, index):
        return self.columns[index]


class FakeSheet:
    def __init__(self):
        self.cells = {}
        self.Columns = FakeColumns()

    def getCellByPosition(self, col, row):
        return self.cells.setdefault((col, row), FakeCell())


def test_header_contract_covers_a_through_ah():
    assert len(ALL_HEADERS) == 34
    assert ALL_HEADERS[0] == "Ativo"
    assert ALL_HEADERS[21] == "Texto Botão"
    assert ALL_HEADERS[22] == "Status"
    assert ALL_HEADERS[27] == "ID Automação"
    assert ALL_HEADERS[33] == "Hash Confirmado"


def test_configure_catalog_sheet_writes_headers_and_hides_technical_columns():
    sheet = FakeSheet()

    configure_catalog_sheet(sheet)

    assert [sheet.getCellByPosition(i, 0).String for i in range(34)] == list(ALL_HEADERS)
    assert all(sheet.Columns.getByIndex(i).IsVisible for i in range(27))
    assert all(not sheet.Columns.getByIndex(i).IsVisible for i in range(27, 34))
