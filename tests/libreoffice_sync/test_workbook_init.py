
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
        self.IsTextWrapped = False


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


class UiFakeRow:
    def __init__(self):
        self.Height = 0
        self.OptimalHeight = True


class UiFakeRows:
    def __init__(self):
        self.items = {}

    def getByIndex(self, index):
        return self.items.setdefault(index, UiFakeRow())


class UiFakeSheet:
    def __init__(self):
        self.cells = {}
        self.ranges = {}
        self.Columns = UiFakeColumns()
        self.Rows = UiFakeRows()
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
    assert partner.Formula1 == '"Mercado Livre";"Shopee";"SHEIN";"Amazon"'

    assert sheet.Columns.getByIndex(8).Width > 1000
    assert sheet.Columns.getByIndex(9).Width > sheet.Columns.getByIndex(8).Width

    wrapped_columns = (5, 6, 8, 9, 17, 18, 19, 20, 21, 23)
    for col in wrapped_columns:
        assert (
            sheet.getCellRangeByPosition(col, 1, col, 1999).IsTextWrapped
            is True
        )

    assert (
        sheet.getCellRangeByPosition(13, 1, 13, 1999).IsTextWrapped
        is False
    )

    for row_index in (1, 2, 1999):
        row = sheet.Rows.getByIndex(row_index)
        assert row.Height == 700
        assert row.OptimalHeight is False


def test_price_format_uses_builtin_brl_currency_with_two_decimals(monkeypatch):
    import sys
    from types import SimpleNamespace

    import libreoffice_sync.workbook_init as workbook_init

    class FakeLocale:
        Language = ""
        Country = ""

    fake_uno = SimpleNamespace(
        createUnoStruct=lambda name: FakeLocale()
        if name == "com.sun.star.lang.Locale"
        else None
    )
    monkeypatch.setitem(sys.modules, "uno", fake_uno)

    class FakeRange:
        def __init__(self):
            self.NumberFormat = 0
            self.values = (133.76, 199.90)

    class FakeSheet:
        def __init__(self):
            self.price_range = FakeRange()
            self.range_calls = []

        def getCellRangeByPosition(self, *args):
            self.range_calls.append(args)
            return self.price_range

    class FakeFormats:
        def __init__(self):
            self.index_calls = []
            self.query_calls = []

        def getFormatIndex(self, index, locale):
            self.index_calls.append((index, locale.Language, locale.Country))
            return 913

        # A implementação antiga chama este método e recebe outra chave,
        # garantindo um RED comportamental em vez de um teste só de texto.
        def queryKey(self, pattern, locale, scan):
            self.query_calls.append(
                (pattern, locale.Language, locale.Country, scan)
            )
            return 777

        def addNew(self, _pattern, _locale):
            return 778

    formats = FakeFormats()
    document = SimpleNamespace(NumberFormats=formats)
    sheet = FakeSheet()
    before = sheet.price_range.values

    workbook_init._apply_price_format(document, sheet)

    assert formats.index_calls == [(13, "pt", "BR")]
    assert formats.query_calls == []
    assert sheet.range_calls == [(13, 1, 14, 1999)]
    assert sheet.price_range.NumberFormat == 913
    assert sheet.price_range.values == before
