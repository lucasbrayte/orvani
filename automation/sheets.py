"""Gateway em lote e configuração idempotente da aba Importações."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import isfinite
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import IMPORT_HEADERS, Settings
from .models import ConfigurationError, ImportStatus, SheetSchemaError, SheetUpdate, UpdateMode


_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_STATUS_COLUMN = 25
_SHEET_COLUMN_COUNT = len(IMPORT_HEADERS)
_SHOPEE_VIEW_TITLE = "Shopee — aguardando conversão"


@runtime_checkable
class SheetsGateway(Protocol):
    """Pequeno limite transportável, compartilhado por produção e fakes."""

    def get_spreadsheet(self) -> Mapping[str, Any]: ...

    def get_values(self, range_name: str) -> Mapping[str, Any]: ...

    def batch_update(self, requests: Sequence[Mapping[str, Any]]) -> None: ...

    def batch_values_update(
        self, data: Sequence[Mapping[str, Any]], value_input_option: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ImportSheetSetup:
    created: bool
    requests: tuple[Mapping[str, Any], ...]


class GoogleSheetsGateway:
    """Adaptador da API Google com retry apenas para indisponibilidade transitória."""

    def __init__(
        self,
        service: Any,
        spreadsheet_id: str,
        *,
        sleep: Callable[[float], None] | None = None,
        retry_delays: Sequence[float] = (0.5, 1.0),
    ) -> None:
        self._service = service
        self.spreadsheet_id = spreadsheet_id
        self._sleep = sleep or (lambda _seconds: None)
        self._retry_delays = tuple(retry_delays)

    @classmethod
    def from_settings(cls, settings: Settings) -> "GoogleSheetsGateway":
        try:
            credentials = service_account.Credentials.from_service_account_info(
                settings.service_account_info,
                scopes=[_SHEETS_SCOPE],
            )
            service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        except Exception as error:
            raise ConfigurationError("Não foi possível configurar o acesso ao Google Sheets.") from error
        return cls(service, settings.spreadsheet_id)

    def get_spreadsheet(self) -> Mapping[str, Any]:
        return self._execute(
            lambda: self._service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id)
            .execute()
        )

    def get_values(self, range_name: str) -> Mapping[str, Any]:
        return self._execute(
            lambda: self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )

    def batch_update(self, requests: Sequence[Mapping[str, Any]]) -> None:
        self._execute(
            lambda: self._service.spreadsheets()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": list(requests)})
            .execute()
        )

    def batch_values_update(
        self, data: Sequence[Mapping[str, Any]], value_input_option: str
    ) -> None:
        self._execute(
            lambda: self._service.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": value_input_option, "data": list(data)},
            )
            .execute()
        )

    def _execute(self, operation: Callable[[], Mapping[str, Any]]) -> Mapping[str, Any]:
        for attempt, delay in enumerate((*self._retry_delays, None)):
            try:
                response = operation()
                if not isinstance(response, Mapping):
                    raise ConfigurationError("Resposta inválida do Google Sheets.")
                return response
            except (ConfigurationError, SheetSchemaError):
                raise
            except Exception as error:
                status = _http_status(error)
                if status in (429,) or status is not None and 500 <= status <= 599:
                    if delay is not None:
                        self._sleep(delay)
                        continue
                    raise ConfigurationError("Google Sheets está temporariamente indisponível.") from error
                if status == 400:
                    raise SheetSchemaError("A requisição para Google Sheets é inválida.") from error
                if status in (401, 403):
                    raise ConfigurationError("A conta de serviço não tem acesso à planilha.") from error
                if status == 404:
                    raise SheetSchemaError("A planilha ou intervalo não foi encontrado.") from error
                raise ConfigurationError("Falha ao comunicar com Google Sheets.") from error
        raise AssertionError("retry loop exhausted")


def validate_headers(headers: Sequence[Any]) -> None:
    """Recusa qualquer esquema diferente dos 32 cabeçalhos aprovados."""
    if tuple(headers) != IMPORT_HEADERS:
        raise SheetSchemaError("Os cabeçalhos da aba Importações não correspondem ao contrato aprovado.")


def plan_import_sheet_setup(gateway: SheetsGateway, worksheet: str) -> ImportSheetSetup:
    """Lê metadados e constrói, sem gravar, uma única configuração estrutural."""
    _range(worksheet, "A1:AF1")
    metadata = gateway.get_spreadsheet()
    inventory = _sheet_inventory(metadata)
    if worksheet in inventory:
        sheet = inventory[worksheet]
        header_response = gateway.get_values(_range(worksheet, "A1:AF1"))
        values = header_response.get("values", [])
        if not isinstance(values, list) or not values:
            raise SheetSchemaError("A aba Importações não possui a linha de cabeçalho exigida.")
        header = values[0]
        if not isinstance(header, list):
            raise SheetSchemaError("A linha de cabeçalho da aba Importações é inválida.")
        validate_headers(header)
        return ImportSheetSetup(False, tuple(_formatting_requests(sheet)))

    sheet_id = _next_unused_positive_sheet_id(inventory.values())
    created_sheet = {"properties": {"sheetId": sheet_id, "title": worksheet}}
    requests: list[Mapping[str, Any]] = [{"addSheet": created_sheet}]
    requests.append(_headers_request(sheet_id))
    requests.extend(_formatting_requests({"properties": created_sheet["properties"]}))
    return ImportSheetSetup(True, tuple(requests))


def setup_import_sheet(
    gateway: SheetsGateway, worksheet: str, *, dry_run: bool = False
) -> ImportSheetSetup:
    """Aplica a configuração planejada, sem alterar linhas de dados existentes."""
    plan = plan_import_sheet_setup(gateway, worksheet)
    if plan.requests and not dry_run:
        gateway.batch_update(plan.requests)
    return plan


def read_table(gateway: SheetsGateway, worksheet: str) -> tuple[tuple[Any, ...], ...]:
    """Lê somente as 32 colunas aprovadas, preservando tipos e linhas internas."""
    response = gateway.get_values(_range(worksheet, "A1:AF"))
    values = response.get("values", [])
    if not isinstance(values, list) or not values or not isinstance(values[0], list):
        raise SheetSchemaError("A aba Importações não possui dados legíveis.")
    validate_headers(values[0])
    rows: list[tuple[Any, ...]] = []
    for row in values[1:]:
        if not isinstance(row, list) or len(row) > _SHEET_COLUMN_COUNT:
            raise SheetSchemaError("A aba Importações contém uma linha inválida.")
        rows.append(tuple(row))
    return tuple(rows)


def batch_write(
    gateway: SheetsGateway,
    updates: Sequence[SheetUpdate],
    *,
    value_input_option: str = "USER_ENTERED",
) -> None:
    """Valida e envia todos os intervalos em uma única values.batchUpdate."""
    if value_input_option not in {"USER_ENTERED", "RAW"}:
        raise SheetSchemaError("O modo de escrita da planilha é inválido.")
    data = [_transport_update(update) for update in updates]
    if data:
        gateway.batch_values_update(data, value_input_option)


def plan_new_import_row(
    worksheet: str,
    row_number: int,
    *,
    uuid_factory: Callable[[], Any] = uuid4,
) -> SheetUpdate:
    """Planeja uma linha nova inteira; não é usado para alterar linhas existentes."""
    if not isinstance(row_number, int) or isinstance(row_number, bool) or row_number < 2:
        raise SheetSchemaError("A nova linha de Importações é inválida.")
    automation_id = str(uuid_factory())
    values: list[Any] = [""] * _SHEET_COLUMN_COUNT
    values[0] = automation_id
    values[2] = "Não"
    values[3] = "Não"
    values[5] = UpdateMode.AUTOMATICO.value
    values[_STATUS_COLUMN] = ImportStatus.NOVO.value
    values[27] = 0
    return SheetUpdate(_range(worksheet, f"A{row_number}:AF{row_number}"), (tuple(values),))


def _sheet_inventory(metadata: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    sheets = metadata.get("sheets", [])
    if not isinstance(sheets, list):
        raise SheetSchemaError("Os metadados da planilha são inválidos.")
    by_title: dict[str, Mapping[str, Any]] = {}
    used_ids: set[int] = set()
    for sheet in sheets:
        if not isinstance(sheet, Mapping):
            raise SheetSchemaError("Os metadados da planilha são inválidos.")
        properties = sheet.get("properties")
        if not isinstance(properties, Mapping):
            raise SheetSchemaError("Os metadados da planilha são inválidos.")
        sheet_id, title = properties.get("sheetId"), properties.get("title")
        if (
            not isinstance(sheet_id, int)
            or isinstance(sheet_id, bool)
            or sheet_id < 0
            or not isinstance(title, str)
            or not title
            or sheet_id in used_ids
            or title in by_title
        ):
            raise SheetSchemaError("Os metadados da planilha são inconsistentes.")
        used_ids.add(sheet_id)
        by_title[title] = sheet
    return by_title


def _next_unused_positive_sheet_id(sheets: Sequence[Mapping[str, Any]]) -> int:
    used_ids = {sheet["properties"]["sheetId"] for sheet in sheets}
    candidate = 1
    while candidate in used_ids:
        candidate += 1
    return candidate


def _headers_request(sheet_id: int) -> Mapping[str, Any]:
    return {
        "updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": header}} for header in IMPORT_HEADERS]}],
            "fields": "userEnteredValue",
        }
    }


def _formatting_requests(sheet: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sheet_id = sheet["properties"]["sheetId"]
    full_range = {"sheetId": sheet_id, "startRowIndex": 0, "endColumnIndex": _SHEET_COLUMN_COUNT}
    requests: list[Mapping[str, Any]] = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {"setBasicFilter": {"filter": {"range": full_range}}},
    ]
    for column, allowed in (
        (1, ("Sim", "Não")),
        (2, ("Sim", "Não")),
        (3, ("Sim", "Não")),
        (5, tuple(item.value for item in UpdateMode)),
        (_STATUS_COLUMN, tuple(item.value for item in ImportStatus)),
    ):
        requests.append(_validation_request(sheet_id, column, allowed))
    requests.extend(
        (
            _format_request(sheet_id, 15, 17, "NUMBER", 'R$ #,##0.00'),
            _format_request(sheet_id, 19, 20, "DATE", "dd/MM/yyyy"),
            _format_request(sheet_id, 30, 32, "DATE", "dd/MM/yyyy"),
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "endColumnIndex": _SHEET_COLUMN_COUNT},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                }
            },
        )
    )
    for status, color in ((ImportStatus.ERRO.value, {"red": 1.0, "green": 0.8, "blue": 0.8}), (ImportStatus.ATENCAO.value, {"red": 1.0, "green": 0.95, "blue": 0.75})):
        if not _has_conditional_status_rule(sheet, status):
            requests.append(_conditional_status_request(sheet_id, status, color))
    if not _has_shopee_filter_view(sheet):
        requests.append(_shopee_filter_view_request(sheet_id))
    return requests


def _validation_request(sheet_id: int, column: int, allowed: Sequence[str]) -> Mapping[str, Any]:
    return {
        "setDataValidation": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": column, "endColumnIndex": column + 1},
            "rule": {
                "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": value} for value in allowed]},
                "strict": True,
                "showCustomUi": True,
            },
        }
    }


def _format_request(sheet_id: int, start_column: int, end_column: int, kind: str, pattern: str) -> Mapping[str, Any]:
    return {
        "repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": start_column, "endColumnIndex": end_column},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": kind, "pattern": pattern}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _conditional_status_request(sheet_id: int, status: str, color: Mapping[str, float]) -> Mapping[str, Any]:
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": _STATUS_COLUMN, "endColumnIndex": _STATUS_COLUMN + 1}],
                "booleanRule": {
                    "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": status}]},
                    "format": {"backgroundColor": dict(color)},
                },
            },
            "index": 0,
        }
    }


def _shopee_filter_view_request(sheet_id: int) -> Mapping[str, Any]:
    return {
        "addFilterView": {
            "filter": {
                "title": _SHOPEE_VIEW_TITLE,
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endColumnIndex": _SHEET_COLUMN_COUNT},
                "criteria": {
                    str(_STATUS_COLUMN): {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": ImportStatus.AGUARDANDO_CONVERSAO.value}],
                        }
                    }
                },
            }
        }
    }


def _has_shopee_filter_view(sheet: Mapping[str, Any]) -> bool:
    views = sheet.get("filterViews", [])
    return isinstance(views, list) and any(
        isinstance(view, Mapping) and view.get("title") == _SHOPEE_VIEW_TITLE for view in views
    )


def _has_conditional_status_rule(sheet: Mapping[str, Any], status: str) -> bool:
    rules = sheet.get("conditionalFormats", [])
    if not isinstance(rules, list):
        return False
    for rule in rules:
        try:
            values = rule["booleanRule"]["condition"]["values"]
        except (KeyError, TypeError):
            continue
        if values == [{"userEnteredValue": status}]:
            return True
    return False


def _transport_update(update: SheetUpdate) -> Mapping[str, Any]:
    if not isinstance(update, SheetUpdate) or not isinstance(update.range_name, str) or not update.range_name:
        raise SheetSchemaError("A atualização da planilha é inválida.")
    rows: list[list[Any]] = []
    if not isinstance(update.values, tuple) or not update.values:
        raise SheetSchemaError("A atualização da planilha não contém valores.")
    for row in update.values:
        if not isinstance(row, tuple) or not row:
            raise SheetSchemaError("A atualização da planilha não contém uma linha válida.")
        rows.append([_transport_value(value) for value in row])
    return {"range": update.range_name, "values": rows}


def _transport_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise SheetSchemaError("A atualização contém um número inválido.")
        return float(value)
    if isinstance(value, float):
        if not isfinite(value):
            raise SheetSchemaError("A atualização contém um número inválido.")
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise SheetSchemaError("A atualização contém um tipo de célula inválido.")


def _range(worksheet: str, cells: str) -> str:
    if not isinstance(worksheet, str) or not worksheet or "!" in worksheet:
        raise SheetSchemaError("O nome da aba é inválido.")
    return f"{worksheet}!{cells}"


def _http_status(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int):
        return value
    response = getattr(error, "resp", None)
    value = getattr(response, "status", None)
    return value if isinstance(value, int) else None
