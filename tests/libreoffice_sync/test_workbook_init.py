
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


from libreoffice_sync.workbook_init import ALL_HEADERS, initialize_document


class UiFakeValidation:
    def __init__(self):
        self.Type = None
        self.Formula1 = ""
        self.ShowErrorMessage = False
        self.ErrorMessage = ""


class UiFakeRange:
    def __init__(self):
        self.Validation = UiFakeValidation()
        self.NumberFormat = None


class UiFakeCell:
    def __init__(self):
        self.String = ""


class UiFakeColumn:
    def __init__(self):
        self.IsVisible = True
        self.Width = 1000


class UiFakeColumns:
    def __init__(self):
        self.items = [UiFakeColumn() for _ in range(34)]

    def getByIndex(self, index):
        return self.items[index]


class UiFakeSheet:
    def __init__(self):
        self.cells = {}
        self.ranges = {}
        self.Columns = UiFakeColumns()
        self.Name = "Sheet1"

    def getCellByPosition(self, col, row):
        return self.cells.setdefault((col, row), UiFakeCell())

    def getCellRangeByPosition(self, c1, r1, c2, r2):
        return self.ranges.setdefault((c1, r1, c2, r2), UiFakeRange())


class UiFakeSheets:
    def __init__(self):
        self.sheet = UiFakeSheet()

    def hasByName(self, name):
        return self.sheet.Name == name

    def getByName(self, name):
        assert self.sheet.Name == name
        return self.sheet

    def getByIndex(self, index):
        assert index == 0
        return self.sheet


class UiFakeController:
    def __init__(self):
        self.frozen = None

    def freezeAtPosition(self, col, row):
        self.frozen = (col, row)


class UiFakeDocument:
    def __init__(self):
        self.Sheets = UiFakeSheets()
        self.controller = UiFakeController()

    def getCurrentController(self):
        return self.controller


def test_initialize_document_applies_full_catalog_ui_contract():
    doc = UiFakeDocument()
    initialize_document(doc)
    sheet = doc.Sheets.getByName("Catálogo")

    assert [sheet.getCellByPosition(i, 0).String for i in range(34)] == list(ALL_HEADERS)
    assert doc.controller.frozen == (0, 1)
    assert all(not sheet.Columns.getByIndex(i).IsVisible for i in range(27, 34))

    yes_no = sheet.getCellRangeByPosition(0, 1, 0, 1999).Validation
    assert "Sim" in yes_no.Formula1 and "Não" in yes_no.Formula1

    update_mode = sheet.getCellRangeByPosition(4, 1, 4, 1999).Validation
    assert "Automático" in update_mode.Formula1
    assert "Manual" in update_mode.Formula1
    assert "Bloqueado" in update_mode.Formula1

    partner = sheet.getCellRangeByPosition(7, 1, 7, 1999).Validation
    assert partner.Formula1 == '"Mercado Livre";"Shopee";"SHEIN"'

    assert sheet.Columns.getByIndex(8).Width > 1000
    assert sheet.Columns.getByIndex(9).Width > sheet.Columns.getByIndex(8).Width
