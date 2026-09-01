from datetime import UTC, datetime
from decimal import Decimal

import pytest

from automation.config import IMPORT_HEADERS, PRODUCTS_HEADERS, Settings
from automation.models import ConfigurationError, SheetSchemaError, SheetUpdate


def _request_for(requests, name):
    return next(request[name] for request in requests if name in request)


def _validation_values(requests, column):
    validation = next(
        request["setDataValidation"]
        for request in requests
        if request.get("setDataValidation", {}).get("range", {}).get("startColumnIndex") == column
    )
    return [item["userEnteredValue"] for item in validation["rule"]["condition"]["values"]]


def _sheet_ids(value):
    if isinstance(value, dict):
        found = [value["sheetId"]] if "sheetId" in value else []
        return found + [identifier for child in value.values() for identifier in _sheet_ids(child)]
    if isinstance(value, list):
        return [identifier for child in value for identifier in _sheet_ids(child)]
    return []


def test_validate_headers_requires_the_exact_import_contract():
    from automation.sheets import validate_headers

    validate_headers(list(IMPORT_HEADERS))
    wrong = list(IMPORT_HEADERS)
    wrong[8] = "Parceiro"
    with pytest.raises(SheetSchemaError):
        validate_headers(wrong)


def test_setup_creates_missing_sheet_once_with_one_complete_structural_batch(fake_sheets):
    from automation.sheets import setup_import_sheet

    result = setup_import_sheet(fake_sheets, "Importações", dry_run=False)

    assert result.created is True
    assert len(fake_sheets.spreadsheet_writes) == 1
    requests = fake_sheets.spreadsheet_writes[0]
    properties = _request_for(requests, "addSheet")["properties"]
    sheet_id = properties["sheetId"]
    assert sheet_id == 1
    header_cells = _request_for(requests, "updateCells")["rows"][0]["values"]
    assert [cell["userEnteredValue"]["stringValue"] for cell in header_cells] == list(IMPORT_HEADERS)
    assert _request_for(requests, "updateSheetProperties")["properties"]["gridProperties"] == {
        "frozenRowCount": 1
    }
    header_format = next(
        request["repeatCell"]
        for request in requests
        if request.get("repeatCell", {}).get("range", {}).get("startRowIndex") == 0
    )
    assert header_format["range"] == {
        "sheetId": sheet_id,
        "startRowIndex": 0,
        "endRowIndex": 1,
        "startColumnIndex": 0,
        "endColumnIndex": 32,
    }
    assert header_format["cell"]["userEnteredFormat"]["textFormat"]["bold"] is True
    assert _request_for(requests, "setBasicFilter")["filter"]["range"]["endColumnIndex"] == 32
    assert _validation_values(requests, 1) == ["Sim", "Não"]
    assert _validation_values(requests, 5) == ["Automático", "Bloqueado"]
    assert _validation_values(requests, 25) == [
        "NOVO", "AGUARDANDO CONVERSÃO", "PROCESSANDO", "REVISAR",
        "PRONTO PARA PUBLICAR", "PUBLICADO", "ATENÇÃO", "ERRO", "DESATIVADO",
    ]
    assert next(
        request["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"]["type"]
        for request in requests
        if "numberFormat" in request.get("repeatCell", {}).get("cell", {}).get("userEnteredFormat", {})
    ) == "NUMBER"
    assert any("addConditionalFormatRule" in request for request in requests)
    filter_view = _request_for(requests, "addFilterView")
    assert filter_view["filter"]["title"] == "Shopee — aguardando conversão"
    assert filter_view["filter"]["range"] == {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1000, "startColumnIndex": 0, "endColumnIndex": 32}
    assert filter_view["filter"]["criteria"]["25"]["condition"]["values"] == [
        {"userEnteredValue": "AGUARDANDO CONVERSÃO"}
    ]
    assert set(_sheet_ids(requests)) == {sheet_id}


def test_setup_chooses_the_smallest_unused_positive_id_and_reuses_it_everywhere(fake_sheets):
    from automation.sheets import setup_import_sheet

    fake_sheets._sheets = [
        _grid_sheet(0, "zero"),
        _grid_sheet(1, "one"),
        _grid_sheet(3, "three"),
    ]
    setup_import_sheet(fake_sheets, "Importações")

    requests = fake_sheets.spreadsheet_writes[0]
    assert _request_for(requests, "addSheet")["properties"]["sheetId"] == 2
    assert set(_sheet_ids(requests)) == {2}


def test_setup_existing_sheet_validates_header_before_any_write(fake_sheets_with_imports):
    from automation.sheets import setup_import_sheet

    fake_sheets_with_imports._values["'Importações'!A1:AF1"] = [["wrong"]]
    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets_with_imports, "Importações")
    assert fake_sheets_with_imports.spreadsheet_writes == []
    assert fake_sheets_with_imports.value_writes == []


def test_setup_preserves_existing_rows_and_does_not_recreate_or_duplicate_filter_view(fake_sheets_with_imports):
    from automation.sheets import setup_import_sheet

    before = fake_sheets_with_imports.values("'Importações'!A1:AF")
    first = setup_import_sheet(fake_sheets_with_imports, "Importações")
    second = setup_import_sheet(fake_sheets_with_imports, "Importações")

    assert first.created is False
    assert second.created is False
    assert fake_sheets_with_imports.values("'Importações'!A1:AF") == before
    assert all("addSheet" not in request for write in fake_sheets_with_imports.spreadsheet_writes for request in write)
    assert sum("addFilterView" in request for write in fake_sheets_with_imports.spreadsheet_writes for request in write) == 1
    assert sum("addConditionalFormatRule" in request for write in fake_sheets_with_imports.spreadsheet_writes for request in write) == 2


def test_stateful_fake_models_repeated_validation_and_format_application_idempotently(fake_sheets_with_imports):
    """Catches the fake accumulating effects that Sheets replaces on the same range."""
    from automation.sheets import setup_import_sheet

    setup_import_sheet(fake_sheets_with_imports, "Importações")
    setup_import_sheet(fake_sheets_with_imports, "Importações")

    state = fake_sheets_with_imports._sheets[0]
    assert len(state["validations"]) == 5
    assert len(state["formats"]) == 4
    header_formats = [
        item
        for item in state["formats"]
        if item["range"]["startRowIndex"] == 0
    ]
    assert len(header_formats) == 1
    assert header_formats[0]["cell"]["userEnteredFormat"]["textFormat"] == {"bold": True}
    assert state["headerTextFormat"] == {"bold": True}
    assert state["basicFilter"]["range"] == {
        "sheetId": 17,
        "startRowIndex": 0,
        "endRowIndex": 1000,
        "startColumnIndex": 0,
        "endColumnIndex": 32,
    }


def test_setup_dry_run_returns_same_plan_without_writes(fake_sheets):
    from automation.sheets import setup_import_sheet

    dry = setup_import_sheet(fake_sheets, "Importações", dry_run=True)
    applied = setup_import_sheet(fake_sheets, "Importações", dry_run=False)

    assert dry.requests == applied.requests
    assert fake_sheets.spreadsheet_writes and fake_sheets.value_writes == []


@pytest.mark.parametrize(
    "sheets",
    (
        (
            {"properties": {"sheetId": 5, "title": "A"}},
            {"properties": {"sheetId": 5, "title": "B"}},
        ),
        (
            {"properties": {"sheetId": 5, "title": "Importações"}},
            {"properties": {"sheetId": 6, "title": "Importações"}},
        ),
    ),
)
def test_setup_rejects_inconsistent_metadata_without_a_write(fake_sheets, sheets):
    from automation.sheets import setup_import_sheet

    fake_sheets._sheets = list(sheets)
    with pytest.raises((ConfigurationError, SheetSchemaError)):
        setup_import_sheet(fake_sheets, "Importações")
    assert fake_sheets.spreadsheet_writes == []


def test_setup_rejects_an_unsafe_new_sheet_title_before_planning_a_write(fake_sheets):
    from automation.sheets import setup_import_sheet

    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets, "Importações!outra")
    assert fake_sheets.spreadsheet_writes == []


def test_read_table_preserves_types_and_empty_interior_rows(fake_sheets_with_imports):
    from automation.sheets import read_table

    fake_sheets_with_imports._values["'Importações'!A1:AF"] = [
        list(IMPORT_HEADERS),
        ["id-1", "Sim", 12, 9.9],
        [],
        ["id-3", False, 46264.0],
    ]
    rows = read_table(fake_sheets_with_imports, "Importações")

    assert rows == (
        ("id-1", "Sim", 12, 9.9),
        (),
        ("id-3", False, 46264.0),
    )
    assert fake_sheets_with_imports.value_reads == ["'Importações'!A1:AF"]


def test_batch_write_transports_many_ranges_once_with_typed_numbers_and_dates(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    batch_write(
        fake_sheets,
        (
            SheetUpdate("'Importações'!P2", ((Decimal("149.90"),),)),
            SheetUpdate("'Importações'!T2", ((datetime(2026, 8, 30, tzinfo=UTC),),)),
        ),
    )

    assert len(fake_sheets.value_writes) == 1
    payload = fake_sheets.value_writes[0]
    assert payload["valueInputOption"] == "RAW"
    assert payload["data"][0] == {"range": "'Importações'!P2:P2", "values": [[149.9]]}
    assert isinstance(payload["data"][1]["values"][0][0], float)


def test_batch_write_rejects_invalid_updates_before_the_transport_call(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    with pytest.raises(SheetSchemaError, match="tipo de célula inválido"):
        batch_write(fake_sheets, (SheetUpdate("Importações!A2", ((object(),),)),))
    assert fake_sheets.value_writes == []


def test_batch_write_refuses_user_entered_for_untrusted_sheet_content(fake_sheets):
    from automation.sheets import batch_write

    fake_sheets._sheets = [_grid_sheet()]
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Importações'!A2", (("=external-formula",),)),),
            value_input_option="USER_ENTERED",
        )
    assert fake_sheets.value_writes == []


def test_new_import_row_defaults_are_one_range_and_automation_id_is_assigned_once(fake_sheets):
    from automation.models import ImportRecord
    from automation.sheets import batch_write, plan_new_import_row

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    update = plan_new_import_row("Importações", 7)
    record, id_update = ImportRecord.from_sheet_row(7, (update.values[0][0],))
    existing, existing_update = ImportRecord.from_sheet_row(7, (record.automation_id,))
    batch_write(fake_sheets, (update,))

    assert update.range_name == "'Importações'!A7:AF7"
    assert len(update.values[0]) == 32
    assert update.values[0][2:6] == ("Não", "Não", "", "Automático")
    assert update.values[0][25] == "NOVO"
    assert update.values[0][27] == 0
    assert id_update is None
    assert existing.automation_id == record.automation_id
    assert existing_update is None
    assert len(fake_sheets.value_writes) == 1
    assert len(fake_sheets.value_writes[0]["data"]) == 1


class _Request:
    def __init__(self, action):
        self._action = action

    def execute(self):
        return self._action()


class _FakeSpreadsheetsResource:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        def execute():
            result = self.results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return _Request(execute)


class _FakeValuesResource:
    def __init__(self):
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return _Request(lambda: {"values": []})

    def batchUpdate(self, **kwargs):
        self.calls.append(("batchUpdate", kwargs))
        return _Request(lambda: {})


class _FakeService:
    def __init__(self, results):
        self.spreadsheets_resource = _FakeSpreadsheetsResource(results)
        self.values_resource = _FakeValuesResource()
        self.batch_calls = []

    def spreadsheets(self):
        return self

    def get(self, **kwargs):
        return self.spreadsheets_resource.get(**kwargs)

    def values(self):
        return self.values_resource

    def batchUpdate(self, **kwargs):
        self.batch_calls.append(kwargs)
        return _Request(lambda: {})


@pytest.mark.parametrize("status", (429, 500, 502, 503, 504))
def test_google_gateway_retries_only_an_allowed_temporary_status_with_bounded_backoff(status):
    from automation.sheets import GoogleSheetsGateway

    class TransientError(Exception):
        status_code = status

    sleeps = []
    service = _FakeService([TransientError(), {"sheets": []}])
    gateway = GoogleSheetsGateway(service, "spreadsheet-id", sleep=sleeps.append, retry_delays=(0.25,))

    assert gateway.get_spreadsheet() == {"sheets": []}
    assert len(service.spreadsheets_resource.calls) == 2
    assert sleeps == [0.25]


def test_google_gateway_stops_after_the_bounded_503_retry_budget():
    from automation.sheets import GoogleSheetsGateway

    class TransientError(Exception):
        status_code = 503

    sleeps = []
    service = _FakeService([TransientError(), TransientError(), TransientError()])
    with pytest.raises(ConfigurationError):
        GoogleSheetsGateway(service, "spreadsheet-id", sleep=sleeps.append, retry_delays=(0, 0)).get_spreadsheet()
    assert len(service.spreadsheets_resource.calls) == 3
    assert sleeps == [0.0, 0.0]


@pytest.mark.parametrize("status", (400, 401, 403, 404))
def test_google_gateway_does_not_retry_permanent_client_errors(status):
    from automation.sheets import GoogleSheetsGateway

    class ClientError(Exception):
        status_code = status

    service = _FakeService([ClientError()])
    gateway = GoogleSheetsGateway(service, "spreadsheet-id", sleep=lambda _delay: None)

    with pytest.raises((ConfigurationError, SheetSchemaError)):
        gateway.get_spreadsheet()
    assert len(service.spreadsheets_resource.calls) == 1


def test_google_gateway_builds_service_with_sheets_only_scope(monkeypatch):
    from automation import sheets

    calls = {}
    credential = object()

    class Credentials:
        @staticmethod
        def from_service_account_info(info, scopes):
            calls["credentials"] = (info, scopes)
            return credential

    def fake_build(*args, **kwargs):
        calls["build"] = (args, kwargs)
        return _FakeService([{"sheets": []}])

    monkeypatch.setattr(sheets.service_account, "Credentials", Credentials)
    monkeypatch.setattr(sheets, "build", fake_build)
    settings = Settings(service_account_info={"private_key": "never-print-me"})
    gateway = sheets.GoogleSheetsGateway.from_settings(settings)

    assert calls["credentials"] == (
        settings.service_account_info,
        ["https://www.googleapis.com/auth/spreadsheets"],
    )
    assert calls["build"] == (("sheets", "v4"), {"credentials": credential, "cache_discovery": False})
    assert gateway.spreadsheet_id == settings.spreadsheet_id


def test_google_gateway_hides_credential_factory_failures(monkeypatch):
    from automation import sheets

    class Credentials:
        @staticmethod
        def from_service_account_info(_info, *, scopes):
            assert scopes == ["https://www.googleapis.com/auth/spreadsheets"]
            raise RuntimeError("never-print-me")

    monkeypatch.setattr(sheets.service_account, "Credentials", Credentials)
    with pytest.raises(ConfigurationError) as raised:
        sheets.GoogleSheetsGateway.from_settings(
            Settings(service_account_info={"private_key": "never-print-me"})
        )
    assert "never-print-me" not in str(raised.value)


def _grid_sheet(sheet_id=17, title="Importações", *, rows=1000, columns=32):
    return {
        "properties": {
            "sheetId": sheet_id,
            "title": title,
            "sheetType": "GRID",
            "gridProperties": {"rowCount": rows, "columnCount": columns},
        }
    }


def _set_sheet_contract(fake_sheets, worksheet, headers, *, rows=1000, columns=None):
    columns = len(headers) if columns is None else columns
    fake_sheets._sheets = [_grid_sheet(17, worksheet, rows=rows, columns=columns)]
    last_column = "T" if len(headers) == 20 else "AF"
    header_row = 4 if tuple(headers) == PRODUCTS_HEADERS else 1
    fake_sheets._values[
        f"'{worksheet.replace("'", "''")}'!A{header_row}:{last_column}"
    ] = [list(headers)]


def test_google_values_read_requests_unformatted_values_and_serial_dates():
    from automation.sheets import GoogleSheetsGateway

    service = _FakeService([{"sheets": []}])
    gateway = GoogleSheetsGateway(service, "spreadsheet-id")
    gateway.get_values("'Importações'!A1:AF")

    assert service.values_resource.calls == [(
        "get",
        {
            "spreadsheetId": "spreadsheet-id",
            "range": "'Importações'!A1:AF",
            "valueRenderOption": "UNFORMATTED_VALUE",
            "dateTimeRenderOption": "SERIAL_NUMBER",
        },
    )]


def test_batch_write_uses_raw_and_google_serial_dates_without_formula_interpretation(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    batch_write(
        fake_sheets,
        (
            SheetUpdate("'Importações'!A2:C2", (("=not-a-formula", Decimal("149.90"), datetime(1899, 12, 31, 3, tzinfo=UTC)),)),
        ),
    )

    assert fake_sheets.value_writes == [{
        "valueInputOption": "RAW",
        "data": [{"range": "'Importações'!A2:C2", "values": [["=not-a-formula", 149.9, 1.125]]}],
    }]


@pytest.mark.parametrize(
    "value",
    (Decimal("NaN"), Decimal("Infinity"), Decimal("1e1000000")),
)
def test_batch_write_rejects_non_transportable_decimals_before_any_write(fake_sheets, value):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    with pytest.raises(SheetSchemaError, match="número inválido"):
        batch_write(fake_sheets, (SheetUpdate("'Importações'!A2", ((value,),)),))
    assert fake_sheets.value_writes == []


@pytest.mark.parametrize(
    "update, message",
    (
        (SheetUpdate("Produtos!A2", (("x",),)), "aba não autorizada"),
        (SheetUpdate("'Importações'!AG2", (("x",),)), "fora do contrato"),
        (SheetUpdate("'Importações'!A0", (("x",),)), "intervalo de atualização é inválido"),
        (SheetUpdate("'Importações'!A2:B2", (("x",),)), "dimensões"),
        (SheetUpdate("'Importações'!A2:A3", (("x", "y"),)), "dimensões"),
    ),
)
def test_batch_write_rejects_unauthorized_or_dimension_mismatched_ranges_before_any_write(fake_sheets, update, message):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    with pytest.raises(SheetSchemaError, match=message):
        batch_write(fake_sheets, (update,), worksheet="Importações")
    assert fake_sheets.value_writes == []


def test_read_table_supports_products_exact_contract_and_safe_quoted_range(fake_sheets):
    from automation.sheets import read_table

    fake_sheets._sheets = [_grid_sheet(19, "Produtos", columns=20)]
    fake_sheets._values["'Produtos'!A4:T"] = [list(PRODUCTS_HEADERS), ["Sim", "Físico", "Shopee"]]

    assert read_table(fake_sheets, "Produtos", headers=PRODUCTS_HEADERS) == (("Sim", "Físico", "Shopee"),)
    assert fake_sheets.value_reads == ["'Produtos'!A4:T"]


def test_batch_write_rejects_product_metadata_and_binds_the_header_at_row_four(fake_sheets):
    from automation.sheets import batch_write

    fake_sheets._sheets = [_grid_sheet(19, "Produtos", columns=20)]
    fake_sheets._values["'Produtos'!A4:T"] = [list(PRODUCTS_HEADERS)]

    with pytest.raises(SheetSchemaError, match="fora do contrato"):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Produtos'!A3", (("não tocar",),)),),
            worksheet="Produtos",
            headers=PRODUCTS_HEADERS,
        )

    assert fake_sheets.value_reads == ["'Produtos'!A4:T"]
    assert fake_sheets.value_writes == []


def test_batch_write_uses_the_selected_products_width_contract(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Produtos", PRODUCTS_HEADERS)
    batch_write(
        fake_sheets,
        (SheetUpdate("'Produtos'!T5", (("última coluna",),)),),
        worksheet="Produtos",
        headers=PRODUCTS_HEADERS,
    )
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Produtos'!U5", (("fora",),)),),
            worksheet="Produtos",
            headers=PRODUCTS_HEADERS,
        )


def test_batch_write_binds_a_custom_products_worksheet_to_its_real_header_before_writing(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Catálogo ' 2026", PRODUCTS_HEADERS)
    batch_write(
        fake_sheets,
        (SheetUpdate("'Catálogo '' 2026'!T5", (("última coluna",),)),),
        worksheet="Catálogo ' 2026",
        headers=PRODUCTS_HEADERS,
    )

    assert fake_sheets.spreadsheet_reads == 1
    assert fake_sheets.value_reads == ["'Catálogo '' 2026'!A4:T"]
    assert len(fake_sheets.value_writes) == 1


def test_batch_write_rejects_import_contract_on_real_products_header_before_write(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Produtos", PRODUCTS_HEADERS)
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Produtos'!U5", (("fora da aba real",),)),),
            worksheet="Produtos",
            headers=IMPORT_HEADERS,
        )
    assert fake_sheets.value_writes == []


def test_batch_write_rejects_wrong_contract_on_a_custom_products_worksheet_before_write(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Catálogo customizado", PRODUCTS_HEADERS)
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Catálogo customizado'!T5", (("não importa",),)),),
            worksheet="Catálogo customizado",
            headers=IMPORT_HEADERS,
        )
    assert fake_sheets.value_writes == []


def test_batch_write_rejects_a_real_header_mismatch_before_write(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Produtos", IMPORT_HEADERS, columns=32)
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Produtos'!T5", (("não importa",),)),),
            worksheet="Produtos",
            headers=PRODUCTS_HEADERS,
        )
    assert fake_sheets.value_writes == []


def test_batch_write_rejects_a_row_outside_the_real_grid_before_write(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS, rows=1000)
    with pytest.raises(SheetSchemaError):
        batch_write(fake_sheets, (SheetUpdate("'Importações'!A1001", (("late",),)),))
    assert fake_sheets.value_writes == []


def test_batch_write_rejects_a_real_grid_narrower_than_the_contract_before_write(fake_sheets):
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Produtos", PRODUCTS_HEADERS, columns=19)
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Produtos'!T5", (("outside",),)),),
            worksheet="Produtos",
            headers=PRODUCTS_HEADERS,
        )
    assert fake_sheets.value_writes == []


def test_batch_write_empty_batch_is_a_noop_without_reading_metadata(fake_sheets):
    from automation.sheets import batch_write

    batch_write(fake_sheets, ())

    assert fake_sheets.spreadsheet_reads == 0
    assert fake_sheets.value_reads == []
    assert fake_sheets.value_writes == []


def test_batch_write_rejects_an_invalid_selected_header_contract_before_write(fake_sheets):
    """Catches a non-schema value bypassing the approved width contract."""
    from automation.sheets import batch_write

    fake_sheets._sheets = [_grid_sheet()]
    with pytest.raises(SheetSchemaError):
        batch_write(
            fake_sheets,
            (SheetUpdate("'Importações'!A2", (("safe",),)),),
            headers=None,
        )
    assert fake_sheets.value_writes == []


def test_batch_write_rejects_a_ragged_later_update_before_the_single_transport_call(fake_sheets):
    """Catches partial writes when a later range has non-rectangular values."""
    from automation.sheets import batch_write

    _set_sheet_contract(fake_sheets, "Importações", IMPORT_HEADERS)
    with pytest.raises(SheetSchemaError, match="dimensões"):
        batch_write(
            fake_sheets,
            (
                SheetUpdate("'Importações'!A2", (("valid",),)),
                SheetUpdate("'Importações'!A3:B4", (("one", "two"), ("three",))),
            ),
        )
    assert fake_sheets.value_writes == []
    assert fake_sheets.values("'Importações'!A2:A2") == []


def test_setup_rejects_duplicate_or_semantically_conflicting_shopee_filter_before_write(fake_sheets_with_imports):
    from automation.sheets import setup_import_sheet

    sheet = fake_sheets_with_imports._sheets[0]
    sheet["filterViews"] = [{
        "filterViewId": 9,
        "title": "Shopee — aguardando conversão",
        "range": {"sheetId": 17, "startRowIndex": 0, "endColumnIndex": 31},
        "criteria": {},
    }]
    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets_with_imports, "Importações")
    assert fake_sheets_with_imports.spreadsheet_writes == []


def test_setup_rejects_duplicate_or_conflicting_conditional_status_rule_before_write(fake_sheets_with_imports):
    from automation.sheets import setup_import_sheet

    sheet = fake_sheets_with_imports._sheets[0]
    sheet["conditionalFormats"] = [{
        "ranges": [{"sheetId": 17, "startRowIndex": 1, "endRowIndex": 1000, "startColumnIndex": 25, "endColumnIndex": 26}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "ERRO"}]},
            "format": {"backgroundColor": {"red": 0.1}},
        },
    }]
    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets_with_imports, "Importações")
    assert fake_sheets_with_imports.spreadsheet_writes == []


@pytest.mark.parametrize("field", ("filterViews", "conditionalFormats"))
def test_setup_rejects_malformed_semantic_metadata_before_write(fake_sheets_with_imports, field):
    """Catches a gateway treating malformed state as an absent idempotent helper."""
    from automation.sheets import setup_import_sheet

    fake_sheets_with_imports._sheets[0][field] = {"unexpected": "mapping"}

    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets_with_imports, "Importações")
    assert fake_sheets_with_imports.spreadsheet_writes == []


@pytest.mark.parametrize(
    "properties",
    (
        {"sheetId": 2**31, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 2, "columnCount": 32}},
        {"sheetId": 1, "title": "Importações!injetada", "sheetType": "GRID", "gridProperties": {"rowCount": 2, "columnCount": 32}},
        {"sheetId": 1, "title": "Importações", "sheetType": "OBJECT", "gridProperties": {"rowCount": 2, "columnCount": 32}},
        {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 2, "columnCount": 31}},
    ),
)
def test_setup_rejects_invalid_grid_metadata_before_write(fake_sheets, properties):
    from automation.sheets import setup_import_sheet

    fake_sheets._sheets = [{"properties": properties}]
    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets, "Importações")
    assert fake_sheets.spreadsheet_writes == []


def test_setup_rejects_existing_grid_too_small_for_the_32_column_contract(fake_sheets):
    from automation.sheets import setup_import_sheet

    fake_sheets._sheets = [_grid_sheet(columns=31)]
    fake_sheets._values["'Importações'!A1:AF1"] = [list(IMPORT_HEADERS)]
    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets, "Importações")
    assert fake_sheets.spreadsheet_writes == []


@pytest.mark.parametrize("dimension", ("rowCount", "columnCount"))
def test_setup_rejects_out_of_range_grid_dimensions_before_write(fake_sheets, dimension):
    """Catches metadata that cannot be represented safely by the Sheets API."""
    from automation.sheets import setup_import_sheet

    sheet = _grid_sheet()
    sheet["properties"]["gridProperties"][dimension] = 2**31
    fake_sheets._sheets = [sheet]
    fake_sheets._values["'Importações'!A1:AF1"] = [list(IMPORT_HEADERS)]

    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets, "Importações")
    assert fake_sheets.spreadsheet_writes == []


@pytest.mark.parametrize("status", (501, 505))
def test_google_gateway_does_not_retry_unlisted_server_statuses(status):
    from automation.sheets import GoogleSheetsGateway

    class ServerError(Exception):
        status_code = status

    service = _FakeService([ServerError()])
    with pytest.raises(ConfigurationError):
        GoogleSheetsGateway(service, "spreadsheet-id").get_spreadsheet()
    assert len(service.spreadsheets_resource.calls) == 1


def test_google_gateway_rejects_hostile_retry_delays():
    from automation.sheets import GoogleSheetsGateway

    with pytest.raises(ConfigurationError):
        GoogleSheetsGateway(_FakeService([]), "spreadsheet-id", retry_delays=(-1, float("inf")))


def test_credential_failure_has_no_secret_in_traceback_or_exception_chain(monkeypatch):
    import traceback
    from automation import sheets

    secret = "credential-secret-must-not-leak"

    class Credentials:
        @staticmethod
        def from_service_account_info(_info, *, scopes):
            raise RuntimeError(secret)

    monkeypatch.setattr(sheets.service_account, "Credentials", Credentials)
    with pytest.raises(ConfigurationError) as raised:
        sheets.GoogleSheetsGateway.from_settings(Settings(service_account_info={"private_key": secret}))
    error = raised.value
    assert secret not in "".join(traceback.format_exception(error))
    assert secret not in repr(error)
    assert error.__cause__ is None and error.__context__ is None


def test_plan_new_import_row_preserves_existing_cells_and_is_noop_after_adoption():
    from automation.sheets import plan_new_import_row

    current = ("", "Sim", "", "", "", "", "https://store.test/product")
    first = plan_new_import_row("Fila '2026", 8, current_values=current, uuid_factory=lambda: "00000000-0000-4000-8000-000000000001")
    assert first is not None
    assert first.range_name == "'Fila ''2026'!A8:AF8"
    assert first.values[0][0] == "00000000-0000-4000-8000-000000000001"
    assert first.values[0][1] == "Sim"
    assert first.values[0][6] == "https://store.test/product"
    assert first.values[0][2] == "Não"
    assert plan_new_import_row("Fila '2026", 8, current_values=first.values[0]) is None
