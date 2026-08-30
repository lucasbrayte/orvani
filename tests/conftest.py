from datetime import UTC, datetime
from decimal import Decimal
import socket
from collections import Counter
from copy import deepcopy
import re

import httpx
import pytest

from automation.http_client import SafeHttpClient


class FakeSheetsGateway:
    """Fake de Sheets que aplica requests e rejeita grades/ranges inválidos."""

    def __init__(self, sheets=(), values=None):
        self._sheets = deepcopy(list(sheets))
        self._values = deepcopy(values or {})
        self.spreadsheet_reads = 0
        self.value_reads = []
        self.spreadsheet_writes = []
        self.value_writes = []

    def get_spreadsheet(self):
        self.spreadsheet_reads += 1
        return {"sheets": deepcopy(self._sheets)}

    def get_values(self, range_name):
        self.value_reads.append(range_name)
        return {"values": deepcopy(self._values.get(range_name, []))}

    def values(self, range_name):
        return deepcopy(self._values.get(range_name, []))

    def batch_update(self, requests):
        copied = deepcopy(list(requests))
        for request in copied:
            if "addSheet" in request:
                properties = request["addSheet"]["properties"]
                grid = properties.get("gridProperties", {})
                assert properties.get("sheetType") == "GRID"
                assert grid.get("rowCount", 0) >= 2
                assert grid.get("columnCount", 0) >= 32
                assert self._sheet_by_id(properties["sheetId"], required=False) is None
                self._sheets.append({"properties": deepcopy(properties)})
            elif "updateCells" in request:
                update = request["updateCells"]
                sheet_id = update["range"]["sheetId"]
                self._assert_grid_range(update["range"], rows=len(update["rows"]), columns=len(update["rows"][0]["values"]))
                title = self._title_for(sheet_id)
                header = [
                    cell["userEnteredValue"].get("stringValue", "")
                    for cell in update["rows"][0]["values"]
                ]
                self._values[_quoted(title, "A1:AF1")] = [header]
                self._values[_quoted(title, "A1:AF")] = [header]
            elif "addFilterView" in request:
                view = request["addFilterView"]["filter"]
                self._assert_grid_range(view["range"])
                view.setdefault("filterViewId", self._next_filter_view_id())
                self._sheet_for(view["range"]["sheetId"]).setdefault("filterViews", []).append(view)
            elif "updateFilterView" in request:
                view = request["updateFilterView"]["filter"]
                self._assert_grid_range(view["range"])
                target = self._sheet_for(view["range"]["sheetId"])
                index = next(i for i, item in enumerate(target.get("filterViews", [])) if item.get("filterViewId") == view["filterViewId"])
                target["filterViews"][index] = view
            elif "addConditionalFormatRule" in request:
                rule = request["addConditionalFormatRule"]["rule"]
                self._assert_grid_range(rule["ranges"][0])
                self._sheet_for(rule["ranges"][0]["sheetId"]).setdefault(
                    "conditionalFormats", []
                ).append(rule)
            elif "setBasicFilter" in request:
                filter_value = request["setBasicFilter"]["filter"]
                self._assert_grid_range(filter_value["range"])
                self._sheet_for(filter_value["range"]["sheetId"])["basicFilter"] = filter_value
            elif "setDataValidation" in request:
                validation = request["setDataValidation"]
                self._assert_grid_range(validation["range"])
                self._replace_range_state(
                    self._sheet_for(validation["range"]["sheetId"]), "validations", validation
                )
            elif "repeatCell" in request:
                format_value = request["repeatCell"]
                self._assert_grid_range(format_value["range"])
                self._replace_range_state(
                    self._sheet_for(format_value["range"]["sheetId"]), "formats", format_value
                )
            elif "updateSheetProperties" in request:
                properties = request["updateSheetProperties"]["properties"]
                sheet = self._sheet_by_id(properties["sheetId"], required=False)
                assert sheet is not None
                sheet["properties"].setdefault("gridProperties", {}).update(properties.get("gridProperties", {}))
            else:
                raise AssertionError(f"unsupported fake Sheets request: {request}")
        self.spreadsheet_writes.append(copied)

    def batch_values_update(self, data, value_input_option):
        copied = deepcopy(list(data))
        assert value_input_option in {"RAW", "USER_ENTERED"}
        for item in copied:
            title, start_column, start_row, end_column, end_row = _parse_a1(item["range"])
            sheet = self._sheet_by_title(title)
            grid = sheet["properties"]["gridProperties"]
            assert end_column < grid["columnCount"] and end_row <= grid["rowCount"]
            assert len(item["values"]) == end_row - start_row + 1
            assert all(len(row) == end_column - start_column + 1 for row in item["values"])
        self.value_writes.append({"data": copied, "valueInputOption": value_input_option})
        for item in copied:
            self._values[item["range"]] = deepcopy(item["values"])

    def _sheet_for(self, sheet_id):
        sheet = self._sheet_by_id(sheet_id, required=False)
        if sheet is None:
            raise AssertionError(f"unknown fake sheet id: {sheet_id}")
        return sheet

    def _title_for(self, sheet_id):
        return self._sheet_for(sheet_id)["properties"]["title"]

    def _sheet_by_id(self, sheet_id, *, required=True):
        for sheet in self._sheets:
            if sheet.get("properties", {}).get("sheetId") == sheet_id:
                return sheet
        if required:
            raise AssertionError(f"unknown fake sheet id: {sheet_id}")
        return None

    def _sheet_by_title(self, title):
        return next(sheet for sheet in self._sheets if sheet["properties"]["title"] == title)

    def _assert_grid_range(self, value, *, rows=None, columns=None):
        sheet = self._sheet_for(value["sheetId"])
        grid = sheet["properties"]["gridProperties"]
        start_row = value.get("startRowIndex", 0)
        end_row = value.get("endRowIndex", grid["rowCount"])
        start_column = value.get("startColumnIndex", 0)
        end_column = value.get("endColumnIndex", grid["columnCount"])
        assert 0 <= start_row < end_row <= grid["rowCount"]
        assert 0 <= start_column < end_column <= grid["columnCount"]
        if rows is not None:
            assert start_row + rows <= end_row
        if columns is not None:
            assert start_column + columns <= end_column

    def _next_filter_view_id(self):
        return 1 + max((view.get("filterViewId", 0) for sheet in self._sheets for view in sheet.get("filterViews", [])), default=0)

    @staticmethod
    def _replace_range_state(sheet, key, entry):
        entries = sheet.setdefault(key, [])
        entries[:] = [current for current in entries if current.get("range") != entry["range"]]
        entries.append(entry)


@pytest.fixture
def fake_sheets():
    return FakeSheetsGateway()


@pytest.fixture
def fake_sheets_with_imports():
    from automation.config import IMPORT_HEADERS

    return FakeSheetsGateway(
        sheets=({"properties": {"sheetId": 17, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 1000, "columnCount": 32}}},),
        values={
            _quoted("Importações", "A1:AF1"): [list(IMPORT_HEADERS)],
            _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), ["saved-id", "Sim", "Não"]],
        },
    )


def _quoted(title, cells):
    return f"'{title.replace("'", "''")}'!{cells}"


def _parse_a1(range_name):
    match = re.fullmatch(r"'((?:''|[^'])+)'!([A-Z]+)([1-9][0-9]*):([A-Z]+)([1-9][0-9]*)", range_name)
    assert match, f"unsafe A1 range: {range_name}"
    title, start_column, start_row, end_column, end_row = match.groups()
    return title.replace("''", "'"), _column(start_column), int(start_row), _column(end_column), int(end_row)


def _column(label):
    value = 0
    for character in label:
        value = value * 26 + ord(character) - ord("A") + 1
    return value - 1


def _public_dns_resolver(*_args):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


@pytest.fixture
def snapshot_kwargs():
    return {
        "partner": "mercado_livre",
        "external_id": "MLB123",
        "catalog_id": None,
        "source_url": "https://www.mercadolivre.com.br/item/MLB123",
        "affiliate_url": "https://www.mercadolivre.com.br/item/MLB123",
        "name": "Produto de teste",
        "description": "Descrição de teste",
        "current_price": Decimal("10.00"),
        "previous_price": None,
        "currency": "BRL",
        "category": "Eletrônicos",
        "subcategory": "Acessórios",
        "product_type": "Físico",
        "coupon": None,
        "coupon_expires_at": None,
        "images": ("https://images.example/item.jpg",),
        "available": True,
        "fetched_at": datetime(2026, 8, 30, tzinfo=UTC),
    }


@pytest.fixture
def http_client_factory():
    safe_clients = []
    raw_clients = []

    def factory(
        routes,
        *,
        dns_resolver=_public_dns_resolver,
        sleeps=None,
        requests=None,
        client_builder=None,
    ):
        calls = Counter()
        queued_routes = {
            url: list(response) if isinstance(response, list) else [response]
            for url, response in routes.items()
        }

        def handler(request):
            url = str(request.url)
            calls[url] += 1
            if requests is not None:
                requests.append(request)
            response = queued_routes[url].pop(0)
            if isinstance(response, Exception):
                raise response
            status_code, headers, body = response
            if isinstance(body, httpx.SyncByteStream):
                return httpx.Response(status_code, headers=headers, stream=body, request=request)
            return httpx.Response(status_code, headers=headers, content=body, request=request)

        transport = httpx.MockTransport(handler)
        raw_client = (
            client_builder(transport)
            if client_builder is not None
            else httpx.Client(transport=transport)
        )
        client = SafeHttpClient(
            client=raw_client,
            dns_resolver=dns_resolver,
            sleep=(sleeps.append if sleeps is not None else lambda _seconds: None),
        )
        safe_clients.append(client)
        raw_clients.append(raw_client)
        return client, calls

    yield factory

    for client in safe_clients:
        client.close()
    for client in raw_clients:
        client.close()
