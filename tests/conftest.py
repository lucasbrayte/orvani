from datetime import UTC, datetime
from decimal import Decimal
import socket
from collections import Counter
from copy import deepcopy

import httpx
import pytest

from automation.http_client import SafeHttpClient


class FakeSheetsGateway:
    """Fake observável do limite de transporte do Google Sheets."""

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
        self.spreadsheet_writes.append(copied)
        for request in copied:
            if "addSheet" in request:
                properties = request["addSheet"]["properties"]
                self._sheets.append({"properties": deepcopy(properties)})
            elif "updateCells" in request:
                update = request["updateCells"]
                sheet_id = update["range"]["sheetId"]
                title = self._title_for(sheet_id)
                header = [
                    cell["userEnteredValue"].get("stringValue", "")
                    for cell in update["rows"][0]["values"]
                ]
                self._values[f"{title}!A1:AF1"] = [header]
                self._values[f"{title}!A1:AF"] = [header]
            elif "addFilterView" in request:
                view = request["addFilterView"]["filter"]
                self._sheet_for(view["range"]["sheetId"]).setdefault("filterViews", []).append(view)
            elif "addConditionalFormatRule" in request:
                rule = request["addConditionalFormatRule"]["rule"]
                self._sheet_for(rule["ranges"][0]["sheetId"]).setdefault(
                    "conditionalFormats", []
                ).append(rule)

    def batch_values_update(self, data, value_input_option):
        copied = deepcopy(list(data))
        self.value_writes.append({"data": copied, "valueInputOption": value_input_option})
        for item in copied:
            self._values[item["range"]] = deepcopy(item["values"])

    def _sheet_for(self, sheet_id):
        for sheet in self._sheets:
            if sheet.get("properties", {}).get("sheetId") == sheet_id:
                return sheet
        raise AssertionError(f"unknown fake sheet id: {sheet_id}")

    def _title_for(self, sheet_id):
        return self._sheet_for(sheet_id)["properties"]["title"]


@pytest.fixture
def fake_sheets():
    return FakeSheetsGateway()


@pytest.fixture
def fake_sheets_with_imports():
    from automation.config import IMPORT_HEADERS

    return FakeSheetsGateway(
        sheets=({"properties": {"sheetId": 17, "title": "Importações"}},),
        values={
            "Importações!A1:AF1": [list(IMPORT_HEADERS)],
            "Importações!A1:AF": [list(IMPORT_HEADERS), ["saved-id", "Sim", "Não"]],
        },
    )


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
