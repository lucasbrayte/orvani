from datetime import UTC, datetime
from decimal import Decimal
import socket
from collections import Counter

import httpx
import pytest

from automation.http_client import SafeHttpClient


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
