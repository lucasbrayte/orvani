"""Gateway seguro e idempotente para o contrato Google Sheets da Orvani."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from math import isfinite
import re
import time
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import IMPORT_HEADERS, PRODUCTS_HEADERS, PRODUCTS_HEADER_ROW, Settings
from .models import ConfigurationError, ImportStatus, SheetSchemaError, SheetUpdate, UpdateMode

_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_STATUS_COLUMN = 25
_MAX_SHEET_ID = 2_147_483_647
_MAX_RETRIES = 2
_MAX_DELAY_SECONDS = 60.0
_GRID_ROWS = 1_000
_GRID_COLUMNS = len(IMPORT_HEADERS)
_SHOPEE_VIEW_TITLE = "Shopee — aguardando conversão"
_A1 = re.compile(r"(?:(?:'((?:''|[^'])+)')|([^'!]+))!([A-Z]+)([1-9][0-9]*)(?::([A-Z]+)([1-9][0-9]*))?$")


@runtime_checkable
class SheetsGateway(Protocol):
    def get_spreadsheet(self) -> Mapping[str, Any]: ...
    def get_values(self, range_name: str) -> Mapping[str, Any]: ...
    def batch_update(self, requests: Sequence[Mapping[str, Any]]) -> None: ...
    def batch_values_update(self, data: Sequence[Mapping[str, Any]], value_input_option: str) -> None: ...


@dataclass(frozen=True, slots=True)
class ImportSheetSetup:
    created: bool
    requests: tuple[Mapping[str, Any], ...]


class GoogleSheetsGateway:
    def __init__(self, service: Any, spreadsheet_id: str, *, sleep: Callable[[float], None] = time.sleep, retry_delays: Sequence[float] = (0.5, 1.0)) -> None:
        self._service = service
        self.spreadsheet_id = spreadsheet_id
        self._sleep = sleep
        self._retry_delays = _validated_delays(retry_delays)

    @classmethod
    def from_settings(cls, settings: Settings) -> "GoogleSheetsGateway":
        try:
            credentials = service_account.Credentials.from_service_account_info(settings.service_account_info, scopes=[_SHEETS_SCOPE])
            service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        except Exception:
            service = None
        if service is None:
            raise ConfigurationError("Não foi possível configurar o acesso ao Google Sheets.")
        return cls(service, settings.spreadsheet_id)

    def get_spreadsheet(self) -> Mapping[str, Any]:
        return self._execute(lambda: self._service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute())

    def get_values(self, range_name: str) -> Mapping[str, Any]:
        return self._execute(lambda: self._service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=range_name,
            valueRenderOption="UNFORMATTED_VALUE", dateTimeRenderOption="SERIAL_NUMBER",
        ).execute())

    def batch_update(self, requests: Sequence[Mapping[str, Any]]) -> None:
        self._execute(lambda: self._service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body={"requests": list(requests)}).execute())

    def batch_values_update(self, data: Sequence[Mapping[str, Any]], value_input_option: str) -> None:
        self._execute(lambda: self._service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"valueInputOption": value_input_option, "data": list(data)},
        ).execute())

    def _execute(self, operation: Callable[[], Mapping[str, Any]]) -> Mapping[str, Any]:
        for attempt in range(len(self._retry_delays) + 1):
            retry = False
            status: int | None = None
            try:
                response = operation()
                if not isinstance(response, Mapping):
                    raise ConfigurationError("Resposta inválida do Google Sheets.")
                return response
            except (ConfigurationError, SheetSchemaError):
                raise
            except Exception as error:
                status = _http_status(error)
                retry = status in {429, 500, 502, 503, 504}
            if retry and attempt < len(self._retry_delays):
                self._sleep(self._retry_delays[attempt])
                continue
            raise _api_error(status)
        raise AssertionError("unreachable retry loop")


def validate_headers(headers: Sequence[Any], *, expected: Sequence[str] = IMPORT_HEADERS) -> None:
    if tuple(headers) != tuple(expected):
        raise SheetSchemaError("Os cabeçalhos da aba não correspondem ao contrato aprovado.")


def plan_import_sheet_setup(gateway: SheetsGateway, worksheet: str) -> ImportSheetSetup:
    _validate_title(worksheet)
    inventory = _sheet_inventory(gateway.get_spreadsheet())
    existing = inventory.get(worksheet)
    if existing is not None:
        grid = existing["properties"]["gridProperties"]
        if grid["rowCount"] < 2 or grid["columnCount"] < len(IMPORT_HEADERS):
            raise SheetSchemaError("A grade existente não comporta o contrato Importações.")
        values = gateway.get_values(_a1_range(worksheet, "A1:AF1")).get("values", [])
        if not isinstance(values, list) or not values or not isinstance(values[0], list):
            raise SheetSchemaError("A aba Importações não possui a linha de cabeçalho exigida.")
        validate_headers(values[0])
        return ImportSheetSetup(False, tuple(_formatting_requests(existing)))
    sheet_id = _next_unused_positive_sheet_id(inventory.values())
    properties = {"sheetId": sheet_id, "title": worksheet, "sheetType": "GRID", "gridProperties": {"rowCount": _GRID_ROWS, "columnCount": _GRID_COLUMNS}}
    requests: list[Mapping[str, Any]] = [{"addSheet": {"properties": properties}}, _headers_request(sheet_id)]
    requests.extend(_formatting_requests({"properties": properties}))
    return ImportSheetSetup(True, tuple(requests))


def setup_import_sheet(gateway: SheetsGateway, worksheet: str, *, dry_run: bool = False) -> ImportSheetSetup:
    plan = plan_import_sheet_setup(gateway, worksheet)
    if plan.requests and not dry_run:
        gateway.batch_update(plan.requests)
    return plan


def read_table(gateway: SheetsGateway, worksheet: str, *, headers: Sequence[str] = IMPORT_HEADERS) -> tuple[tuple[Any, ...], ...]:
    _validate_title(worksheet)
    expected = _approved_header_contract(headers)
    header_row = _header_row_for_contract(expected)
    values = gateway.get_values(
        _a1_range(worksheet, f"A{header_row}:{_column_label(len(expected) - 1)}")
    ).get("values", [])
    if not isinstance(values, list) or not values or not isinstance(values[0], list):
        raise SheetSchemaError("A aba não possui dados legíveis.")
    validate_headers(values[0], expected=expected)
    output: list[tuple[Any, ...]] = []
    for row in values[1:]:
        if not isinstance(row, list) or len(row) > len(expected):
            raise SheetSchemaError("A aba contém uma linha inválida.")
        output.append(tuple(row))
    return tuple(output)


def batch_write(
    gateway: SheetsGateway,
    updates: Sequence[SheetUpdate],
    *,
    worksheet: str = "Importações",
    headers: Sequence[str] = IMPORT_HEADERS,
    value_input_option: str = "RAW",
) -> None:
    _validate_title(worksheet)
    if value_input_option != "RAW":
        raise SheetSchemaError("O modo de escrita da planilha é inválido.")
    expected = _approved_header_contract(headers)
    header_row = _header_row_for_contract(expected)
    pending = tuple(updates)
    if not pending:
        return
    grid = _worksheet_grid_for_write(gateway, worksheet, expected, header_row)
    width_limit = min(len(expected), grid["columnCount"])
    data = [
        _transport_update(
            update,
            worksheet,
            width_limit,
            grid["rowCount"],
            first_writable_row=header_row + 1,
        )
        for update in pending
    ]
    if data:
        gateway.batch_values_update(data, value_input_option)


def plan_new_import_row(worksheet: str, row_number: int, *, current_values: Sequence[Any] = (), uuid_factory: Callable[[], Any] = uuid4) -> SheetUpdate | None:
    _validate_title(worksheet)
    if not isinstance(row_number, int) or isinstance(row_number, bool) or row_number < 2:
        raise SheetSchemaError("A nova linha de Importações é inválida.")
    if not isinstance(current_values, Sequence) or isinstance(current_values, (str, bytes)) or len(current_values) > len(IMPORT_HEADERS):
        raise SheetSchemaError("A linha de Importações é inválida.")
    values = list(current_values) + [""] * (len(IMPORT_HEADERS) - len(current_values))
    changed = False
    if values[0] in (None, ""):
        generated = str(uuid_factory())
        if not _is_uuid4(generated):
            raise SheetSchemaError("O ID Automação gerado é inválido.")
        values[0], changed = generated, True
    for index, default in ((2, "Não"), (3, "Não"), (5, UpdateMode.AUTOMATICO.value), (_STATUS_COLUMN, ImportStatus.NOVO.value), (27, 0)):
        if values[index] in (None, ""):
            values[index], changed = default, True
    if not changed:
        return None
    return SheetUpdate(_a1_range(worksheet, f"A{row_number}:AF{row_number}"), (tuple(values),))


def _validated_delays(delays: Sequence[float]) -> tuple[float, ...]:
    if not isinstance(delays, Sequence) or isinstance(delays, (str, bytes)) or len(delays) > _MAX_RETRIES:
        raise ConfigurationError("A configuração de retry é inválida.")
    output: list[float] = []
    for delay in delays:
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not isfinite(delay) or not 0 <= delay <= _MAX_DELAY_SECONDS:
            raise ConfigurationError("A configuração de retry é inválida.")
        output.append(float(delay))
    return tuple(output)


def _sheet_inventory(metadata: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    sheets = metadata.get("sheets", [])
    if not isinstance(sheets, list):
        raise SheetSchemaError("Os metadados da planilha são inválidos.")
    output: dict[str, Mapping[str, Any]] = {}
    ids: set[int] = set()
    for sheet in sheets:
        if not isinstance(sheet, Mapping) or not isinstance(sheet.get("properties"), Mapping):
            raise SheetSchemaError("Os metadados da planilha são inválidos.")
        properties = sheet["properties"]
        sheet_id, title, grid = properties.get("sheetId"), properties.get("title"), properties.get("gridProperties")
        if (isinstance(sheet_id, bool) or not isinstance(sheet_id, int) or not 0 <= sheet_id <= _MAX_SHEET_ID or not _title_is_valid(title) or properties.get("sheetType") != "GRID" or not _grid_is_valid(grid) or sheet_id in ids or title in output):
            raise SheetSchemaError("Os metadados da planilha são inconsistentes.")
        ids.add(sheet_id)
        output[title] = sheet
    return output


def _grid_is_valid(grid: Any) -> bool:
    return isinstance(grid, Mapping) and all(
        isinstance(grid.get(key), int)
        and not isinstance(grid.get(key), bool)
        and 0 < grid[key] <= _MAX_SHEET_ID
        for key in ("rowCount", "columnCount")
    )


def _worksheet_grid_for_write(
    gateway: SheetsGateway,
    worksheet: str,
    expected: Sequence[str],
    header_row: int,
) -> Mapping[str, int]:
    sheet = _sheet_inventory(gateway.get_spreadsheet()).get(worksheet)
    if sheet is None:
        raise SheetSchemaError("A aba de escrita não foi encontrada.")
    grid = sheet["properties"]["gridProperties"]
    if grid["columnCount"] < len(expected) or grid["rowCount"] <= header_row:
        raise SheetSchemaError("A grade da aba não comporta o contrato de escrita.")
    last_column = _column_label(len(expected) - 1)
    values = gateway.get_values(
        _a1_range(worksheet, f"A{header_row}:{last_column}")
    ).get("values", [])
    if not isinstance(values, list) or not values or not isinstance(values[0], list):
        raise SheetSchemaError("A aba de escrita não possui cabeçalho legível.")
    validate_headers(values[0], expected=expected)
    return grid


def _next_unused_positive_sheet_id(sheets: Sequence[Mapping[str, Any]]) -> int:
    used = {sheet["properties"]["sheetId"] for sheet in sheets}
    candidate = 1
    while candidate in used:
        candidate += 1
    if candidate > _MAX_SHEET_ID:
        raise SheetSchemaError("Não há um sheetId seguro disponível.")
    return candidate


def _headers_request(sheet_id: int) -> Mapping[str, Any]:
    return {"updateCells": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(IMPORT_HEADERS)}, "rows": [{"values": [{"userEnteredValue": {"stringValue": item}} for item in IMPORT_HEADERS]}], "fields": "userEnteredValue"}}


def _formatting_requests(sheet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    properties = sheet["properties"]
    sheet_id, rows = properties["sheetId"], properties["gridProperties"]["rowCount"]
    full = {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": rows, "startColumnIndex": 0, "endColumnIndex": len(IMPORT_HEADERS)}
    requests: list[Mapping[str, Any]] = [
        {"updateSheetProperties": {"properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
        _header_format_request(sheet_id),
        {"setBasicFilter": {"filter": {"range": full}}},
    ]
    for column, allowed in ((1, ("Sim", "Não")), (2, ("Sim", "Não")), (3, ("Sim", "Não")), (5, tuple(item.value for item in UpdateMode)), (_STATUS_COLUMN, tuple(item.value for item in ImportStatus))):
        requests.append(_validation_request(sheet_id, rows, column, allowed))
    requests.extend((_format_request(sheet_id, rows, 15, 17, "NUMBER", 'R$ #,##0.00'), _format_request(sheet_id, rows, 19, 20, "DATE", "dd/MM/yyyy"), _format_request(sheet_id, rows, 30, 32, "DATE", "dd/MM/yyyy")))
    for status, color in ((ImportStatus.ERRO.value, {"red": 1.0, "green": 0.8, "blue": 0.8}), (ImportStatus.ATENCAO.value, {"red": 1.0, "green": 0.95, "blue": 0.75})):
        state = _conditional_rule_state(sheet, sheet_id, rows, status, color)
        if state == "conflict":
            raise SheetSchemaError("A formatação condicional de status é conflitante.")
        if state == "missing":
            requests.append(_conditional_status_request(sheet_id, rows, status, color))
    state = _filter_view_state(sheet, sheet_id, rows)
    if state == "conflict":
        raise SheetSchemaError("A view Shopee existente é conflitante.")
    if state == "missing":
        requests.append(_shopee_filter_view_request(sheet_id, rows))
    return requests


def _validation_request(sheet_id: int, rows: int, column: int, allowed: Sequence[str]) -> Mapping[str, Any]:
    return {"setDataValidation": {"range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": rows, "startColumnIndex": column, "endColumnIndex": column + 1}, "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": value} for value in allowed]}, "strict": True, "showCustomUi": True}}}


def _format_request(sheet_id: int, rows: int, start: int, end: int, kind: str, pattern: str) -> Mapping[str, Any]:
    return {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": rows, "startColumnIndex": start, "endColumnIndex": end}, "cell": {"userEnteredFormat": {"numberFormat": {"type": kind, "pattern": pattern}}}, "fields": "userEnteredFormat.numberFormat"}}


def _header_format_request(sheet_id: int) -> Mapping[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": len(IMPORT_HEADERS),
            },
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    }


def _conditional_status_request(sheet_id: int, rows: int, status: str, color: Mapping[str, float]) -> Mapping[str, Any]:
    return {"addConditionalFormatRule": {"rule": {"ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": rows, "startColumnIndex": _STATUS_COLUMN, "endColumnIndex": _STATUS_COLUMN + 1}], "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": status}]}, "format": {"backgroundColor": dict(color)}}}, "index": 0}}


def _conditional_rule_state(sheet: Mapping[str, Any], sheet_id: int, rows: int, status: str, color: Mapping[str, float]) -> str:
    expected = _conditional_status_request(sheet_id, rows, status, color)["addConditionalFormatRule"]["rule"]
    matches = [
        rule
        for rule in _semantic_entries(sheet, "conditionalFormats")
        if isinstance(rule.get("booleanRule"), Mapping)
        and rule["booleanRule"].get("condition") == expected["booleanRule"]["condition"]
    ]
    if not matches:
        return "missing"
    return "exact" if len(matches) == 1 and matches[0] == expected else "conflict"


def _shopee_filter_view_request(sheet_id: int, rows: int) -> Mapping[str, Any]:
    return {"addFilterView": {"filter": {"title": _SHOPEE_VIEW_TITLE, "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": rows, "startColumnIndex": 0, "endColumnIndex": len(IMPORT_HEADERS)}, "criteria": {str(_STATUS_COLUMN): {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": ImportStatus.AGUARDANDO_CONVERSAO.value}]}}}}}}


def _filter_view_state(sheet: Mapping[str, Any], sheet_id: int, rows: int) -> str:
    expected = _shopee_filter_view_request(sheet_id, rows)["addFilterView"]["filter"]
    views = [view for view in _semantic_entries(sheet, "filterViews") if view.get("title") == _SHOPEE_VIEW_TITLE]
    if not views:
        return "missing"
    exact = all({key: value for key, value in view.items() if key != "filterViewId"} == expected for view in views)
    return "exact" if len(views) == 1 and exact else "conflict"


def _semantic_entries(sheet: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    entries = sheet.get(key, [])
    if not isinstance(entries, list) or not all(isinstance(entry, Mapping) for entry in entries):
        raise SheetSchemaError("Os metadados auxiliares da aba são inválidos.")
    return entries


def _approved_header_contract(headers: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(headers, Sequence) or isinstance(headers, (str, bytes)):
        raise SheetSchemaError("O contrato da aba é inválido.")
    expected = tuple(headers)
    if expected not in (IMPORT_HEADERS, PRODUCTS_HEADERS):
        raise SheetSchemaError("O contrato da aba é inválido.")
    return expected


def _header_row_for_contract(headers: Sequence[str]) -> int:
    return PRODUCTS_HEADER_ROW if tuple(headers) == PRODUCTS_HEADERS else 1


def _transport_update(
    update: SheetUpdate,
    worksheet: str,
    width_limit: int,
    row_limit: int,
    *,
    first_writable_row: int,
) -> Mapping[str, Any]:
    if not isinstance(update, SheetUpdate):
        raise SheetSchemaError("A atualização da planilha é inválida.")
    range_name, width, height = _authorized_rectangle(
        update.range_name,
        worksheet,
        width_limit,
        row_limit,
        first_writable_row=first_writable_row,
    )
    if not isinstance(update.values, tuple) or len(update.values) != height:
        raise SheetSchemaError("As dimensões da atualização não correspondem ao intervalo.")
    rows: list[list[Any]] = []
    for row in update.values:
        if not isinstance(row, tuple) or len(row) != width:
            raise SheetSchemaError("As dimensões da atualização não correspondem ao intervalo.")
        rows.append([_transport_value(value) for value in row])
    return {"range": range_name, "values": rows}


def _authorized_rectangle(
    range_name: Any,
    worksheet: str,
    width_limit: int,
    row_limit: int,
    *,
    first_writable_row: int,
) -> tuple[str, int, int]:
    if not isinstance(range_name, str) or not (match := _A1.fullmatch(range_name)):
        raise SheetSchemaError("O intervalo de atualização é inválido.")
    quoted, plain, first_column, first_row, last_column, last_row = match.groups()
    title = quoted.replace("''", "'") if quoted is not None else plain
    if title != worksheet:
        raise SheetSchemaError("O intervalo aponta para uma aba não autorizada.")
    _validate_title(title)
    last_column, last_row = last_column or first_column, last_row or first_row
    start_col, end_col, start_row, end_row = _column_number(first_column), _column_number(last_column), int(first_row), int(last_row)
    if (
        start_col > end_col
        or start_row > end_row
        or start_row < first_writable_row
        or start_col < 0
        or end_col >= width_limit
        or end_row > row_limit
    ):
        raise SheetSchemaError("O intervalo de atualização está fora do contrato.")
    return _a1_range(title, f"{first_column}{start_row}:{last_column}{end_row}"), end_col - start_col + 1, end_row - start_row + 1


def _transport_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise SheetSchemaError("A atualização contém um número inválido.")
        try:
            result = float(value)
        except (OverflowError, ValueError):
            raise SheetSchemaError("A atualização contém um número inválido.") from None
        if not isfinite(result):
            raise SheetSchemaError("A atualização contém um número inválido.")
        return result
    if isinstance(value, float):
        if not isfinite(value):
            raise SheetSchemaError("A atualização contém um número inválido.")
        return value
    if isinstance(value, datetime):
        point = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return (point - datetime(1899, 12, 30, tzinfo=UTC)).total_seconds() / 86_400
    if isinstance(value, date):
        return (datetime(value.year, value.month, value.day, tzinfo=UTC) - datetime(1899, 12, 30, tzinfo=UTC)).days
    raise SheetSchemaError("A atualização contém um tipo de célula inválido.")


def _a1_range(title: str, cells: str) -> str:
    _validate_title(title)
    return "'" + title.replace("'", "''") + "'!" + cells


def _validate_title(title: Any) -> None:
    if not _title_is_valid(title):
        raise SheetSchemaError("O nome da aba é inválido.")


def _title_is_valid(title: Any) -> bool:
    return isinstance(title, str) and 0 < len(title) <= 100 and not title.isspace() and not any(character in title for character in "[]:*?/\\!\x00\n\r")


def _column_number(label: str) -> int:
    value = 0
    for character in label:
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _column_label(number: int) -> str:
    result = ""
    while True:
        number, remainder = divmod(number, 26)
        result = chr(ord("A") + remainder) + result
        if number == 0:
            return result
        number -= 1


def _is_uuid4(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value))


def _http_status(error: Exception) -> int | None:
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    status = getattr(getattr(error, "resp", None), "status", None)
    return status if isinstance(status, int) else None


def _api_error(status: int | None) -> Exception:
    if status == 400:
        return SheetSchemaError("A requisição para Google Sheets é inválida.")
    if status in {401, 403}:
        return ConfigurationError("A conta de serviço não tem acesso à planilha.")
    if status == 404:
        return SheetSchemaError("A planilha ou intervalo não foi encontrado.")
    if status in {429, 500, 502, 503, 504}:
        return ConfigurationError("Google Sheets está temporariamente indisponível.")
    return ConfigurationError("Falha ao comunicar com Google Sheets.")
