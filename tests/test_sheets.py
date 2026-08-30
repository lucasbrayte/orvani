from datetime import UTC, datetime
from decimal import Decimal

import pytest

from automation.config import IMPORT_HEADERS, Settings
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
    assert _request_for(requests, "setBasicFilter")["filter"]["range"]["endColumnIndex"] == 32
    assert _validation_values(requests, 1) == ["Sim", "Não"]
    assert _validation_values(requests, 5) == ["Automático", "Bloqueado"]
    assert _validation_values(requests, 25) == [
        "NOVO", "AGUARDANDO CONVERSÃO", "PROCESSANDO", "REVISAR",
        "PRONTO PARA PUBLICAR", "PUBLICADO", "ATENÇÃO", "ERRO", "DESATIVADO",
    ]
    assert _request_for(requests, "repeatCell")["cell"]["userEnteredFormat"]["numberFormat"]["type"] == "NUMBER"
    assert any("addConditionalFormatRule" in request for request in requests)
    filter_view = _request_for(requests, "addFilterView")
    assert filter_view["filter"]["title"] == "Shopee — aguardando conversão"
    assert filter_view["filter"]["range"] == {"sheetId": sheet_id, "startRowIndex": 0, "endColumnIndex": 32}
    assert filter_view["filter"]["criteria"]["25"]["condition"]["values"] == [
        {"userEnteredValue": "AGUARDANDO CONVERSÃO"}
    ]
    assert set(_sheet_ids(requests)) == {sheet_id}


def test_setup_chooses_the_smallest_unused_positive_id_and_reuses_it_everywhere(fake_sheets):
    from automation.sheets import setup_import_sheet

    fake_sheets._sheets = [
        {"properties": {"sheetId": 0, "title": "zero"}},
        {"properties": {"sheetId": 1, "title": "one"}},
        {"properties": {"sheetId": 3, "title": "three"}},
    ]
    setup_import_sheet(fake_sheets, "Importações")

    requests = fake_sheets.spreadsheet_writes[0]
    assert _request_for(requests, "addSheet")["properties"]["sheetId"] == 2
    assert set(_sheet_ids(requests)) == {2}


def test_setup_existing_sheet_validates_header_before_any_write(fake_sheets_with_imports):
    from automation.sheets import setup_import_sheet

    fake_sheets_with_imports._values["Importações!A1:AF1"] = [["wrong"]]
    with pytest.raises(SheetSchemaError):
        setup_import_sheet(fake_sheets_with_imports, "Importações")
    assert fake_sheets_with_imports.spreadsheet_writes == []
    assert fake_sheets_with_imports.value_writes == []


def test_setup_preserves_existing_rows_and_does_not_recreate_or_duplicate_filter_view(fake_sheets_with_imports):
    from automation.sheets import setup_import_sheet

    before = fake_sheets_with_imports.values("Importações!A1:AF")
    first = setup_import_sheet(fake_sheets_with_imports, "Importações")
    second = setup_import_sheet(fake_sheets_with_imports, "Importações")

    assert first.created is False
    assert second.created is False
    assert fake_sheets_with_imports.values("Importações!A1:AF") == before
    assert all("addSheet" not in request for write in fake_sheets_with_imports.spreadsheet_writes for request in write)
    assert sum("addFilterView" in request for write in fake_sheets_with_imports.spreadsheet_writes for request in write) == 1
    assert sum("addConditionalFormatRule" in request for write in fake_sheets_with_imports.spreadsheet_writes for request in write) == 2


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

    fake_sheets_with_imports._values["Importações!A1:AF"] = [
        list(IMPORT_HEADERS),
        ["id-1", "Sim", 12, Decimal("9.90")],
        [],
        ["id-3", False, datetime(2026, 8, 30, tzinfo=UTC)],
    ]
    rows = read_table(fake_sheets_with_imports, "Importações")

    assert rows == (
        ("id-1", "Sim", 12, Decimal("9.90")),
        (),
        ("id-3", False, datetime(2026, 8, 30, tzinfo=UTC)),
    )
    assert fake_sheets_with_imports.value_reads == ["Importações!A1:AF"]


def test_batch_write_transports_many_ranges_once_with_typed_numbers_and_dates(fake_sheets):
    from automation.sheets import batch_write

    batch_write(
        fake_sheets,
        (
            SheetUpdate("Importações!P2", ((Decimal("149.90"),),)),
            SheetUpdate("Importações!T2", ((datetime(2026, 8, 30, tzinfo=UTC),),)),
        ),
    )

    assert len(fake_sheets.value_writes) == 1
    payload = fake_sheets.value_writes[0]
    assert payload["valueInputOption"] == "USER_ENTERED"
    assert payload["data"] == [
        {"range": "Importações!P2", "values": [[149.9]]},
        {"range": "Importações!T2", "values": [["2026-08-30T00:00:00+00:00"]]},
    ]


def test_batch_write_rejects_invalid_updates_before_the_transport_call(fake_sheets):
    from automation.sheets import batch_write

    with pytest.raises(SheetSchemaError):
        batch_write(fake_sheets, (SheetUpdate("Importações!A2", ((object(),),)),))
    assert fake_sheets.value_writes == []


def test_new_import_row_defaults_are_one_range_and_automation_id_is_assigned_once(fake_sheets):
    from automation.models import ImportRecord
    from automation.sheets import batch_write, plan_new_import_row

    update = plan_new_import_row("Importações", 7)
    record, id_update = ImportRecord.from_sheet_row(7, (update.values[0][0],))
    existing, existing_update = ImportRecord.from_sheet_row(7, (record.automation_id,))
    batch_write(fake_sheets, (update,))

    assert update.range_name == "Importações!A7:AF7"
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


def test_google_gateway_retries_temporary_status_only_with_bounded_backoff():
    from automation.sheets import GoogleSheetsGateway

    class TransientError(Exception):
        status_code = 503

    sleeps = []
    service = _FakeService([TransientError(), {"sheets": []}])
    gateway = GoogleSheetsGateway(service, "spreadsheet-id", sleep=sleeps.append, retry_delays=(0.25,))

    assert gateway.get_spreadsheet() == {"sheets": []}
    assert len(service.spreadsheets_resource.calls) == 2
    assert sleeps == [0.25]


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
        def from_service_account_info(_info, _scopes):
            raise RuntimeError("never-print-me")

    monkeypatch.setattr(sheets.service_account, "Credentials", Credentials)
    with pytest.raises(ConfigurationError) as raised:
        sheets.GoogleSheetsGateway.from_settings(
            Settings(service_account_info={"private_key": "never-print-me"})
        )
    assert "never-print-me" not in str(raised.value)
