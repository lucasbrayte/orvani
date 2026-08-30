import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from automation.config import PARTNERS
from automation.http_client import HttpResponse
from automation.models import (
    BlockedByStoreError,
    InvalidProductDataError,
    ProductNotFoundError,
    UnsupportedUrlError,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


class ScriptedHttpClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, allowed_hosts, expected_content_types):
        self.calls.append((url, tuple(allowed_hosts), tuple(expected_content_types)))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.fixture
def api_fixture():
    return json.loads((FIXTURES / "mercado-livre-item.json").read_text())


@pytest.fixture
def html_fixture():
    return (FIXTURES / "mercado-livre-product.html").read_bytes()


@pytest.fixture
def connector():
    from automation.connectors.mercado_livre import MercadoLivreConnector

    return MercadoLivreConnector(
        ScriptedHttpClient([]),
        PARTNERS["mercado_livre"],
        clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC),
    )


def _html(url, body):
    return HttpResponse(url=url, status_code=200, media_type="text/html", body=body)


def _api(item):
    return HttpResponse(
        url="https://api.mercadolibre.com/items/MLB1234567890",
        status_code=200,
        media_type="application/json",
        body=json.dumps(item).encode(),
    )


@pytest.mark.parametrize(
    "url",
    (
        "https://www.mercadolivre.com.br/MLB-1234567890-fone",
        "https://produto.mercadolivre.com.br/MLB-1234567890-fone",
        "https://meli.la/abc123",
    ),
)
def test_supports_only_approved_https_mercado_livre_urls(connector, url):
    # Relaxing host or HTTPS validation would let foreign URLs reach the connector.
    assert connector.supports(url) is True


@pytest.mark.parametrize(
    "url",
    (
        "http://www.mercadolivre.com.br/MLB-1234567890-fone",
        "https://mercadolivre.com.br.evil.example/MLB-1234567890-fone",
        "https://mercadolivre.com.br@evil.example/MLB-1234567890-fone",
        "https://www.mercadolivre.com.br:444/MLB-1234567890-fone",
        "https://meli.la.evil.example/abc",
    ),
)
def test_rejects_unsafe_or_lookalike_urls(connector, url):
    # Accepting any of these values turns an untrusted destination into a store fetch.
    assert connector.supports(url) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("https://www.mercadolivre.com.br/MLB-1234567890-fone", "MLB1234567890"),
        ("/MLB123456-item", "MLB123456"),
        ("MLB-999999", "MLB999999"),
        ("https://www.mercadolivre.com.br/MLB12345-fone", None),
        ("https://www.mercadolivre.com.br/xMLB123456-fone", None),
        ("https://www.mercadolivre.com.br/MLB123456x-fone", None),
        ("texto MLB123456 não é caminho confiável", None),
    ),
)
def test_extracts_only_bounded_item_ids_from_trusted_values(value, expected):
    # Broad matching would confuse catalog IDs or arbitrary page text with an item ID.
    from automation.connectors.mercado_livre import extract_mercado_item_id

    assert extract_mercado_item_id(value) == expected


def test_maps_separate_item_and_catalog_ids(connector, api_fixture):
    # Collapsing the two identifiers would overwrite the item identity with the catalog identity.
    value = connector.snapshot_from_api(
        api_fixture,
        "https://meli.la/abc",
        "https://www.mercadolivre.com.br/MLB-1234567890-fone",
    )

    assert value.external_id == "MLB1234567890"
    assert value.catalog_id == "MLB1234"
    assert value.current_price == Decimal("149.90")
    assert value.previous_price == Decimal("199.90")
    assert value.available is True
    assert value.coupon is None
    assert value.images == (
        "https://http2.mlstatic.com/D_NQ_NP_1.jpg",
        "https://http2.mlstatic.com/D_NQ_NP_2.jpg",
        "https://http2.mlstatic.com/D_NQ_NP_3.jpg",
        "https://http2.mlstatic.com/D_NQ_NP_4.jpg",
    )


def test_fetch_resolves_html_then_uses_only_documented_api_url(html_fixture, api_fixture):
    # A different endpoint, host, or content type would bypass the public API contract.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    client = ScriptedHttpClient((
        _html("https://www.mercadolivre.com.br/MLB-1234567890-fone", html_fixture),
        _api(api_fixture),
    ))
    connector = MercadoLivreConnector(client, PARTNERS["mercado_livre"])

    value = connector.fetch("https://meli.la/affiliate-kept")

    assert value.source_url == "https://www.mercadolivre.com.br/MLB-1234567890-fone"
    assert value.affiliate_url == "https://meli.la/affiliate-kept"
    assert client.calls == [
        (
            "https://meli.la/affiliate-kept",
            ("mercadolivre.com.br", "meli.la"),
            ("text/html", "application/xhtml+xml"),
        ),
        (
            "https://api.mercadolibre.com/items/MLB1234567890",
            ("api.mercadolibre.com",),
            ("application/json",),
        ),
    ]


def test_canonical_and_jsonld_supply_the_id_without_scanning_body_text(html_fixture, api_fixture):
    # Searching arbitrary body text would accept a product ID injected outside trusted metadata.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    client = ScriptedHttpClient((
        _html("https://www.mercadolivre.com.br/sem-id", html_fixture),
        _api(api_fixture),
    ))
    value = MercadoLivreConnector(client, PARTNERS["mercado_livre"]).fetch(
        "https://www.mercadolivre.com.br/sem-id"
    )

    assert value.external_id == "MLB1234567890"


def test_rejects_missing_or_malformed_api_price(connector, api_fixture):
    # Treating an absent public price as zero would fabricate a publishable offer.
    api_fixture["price"] = "preço indisponível"

    with pytest.raises(InvalidProductDataError):
        connector.snapshot_from_api(
            api_fixture,
            "https://meli.la/abc",
            "https://www.mercadolivre.com.br/MLB-1234567890-fone",
        )


def test_rejects_an_api_identity_that_is_not_an_exact_item_id(connector, api_fixture):
    # Substring parsing of an API identifier would attach a response to the wrong product.
    api_fixture["id"] = "old-MLB1234567890"

    with pytest.raises(InvalidProductDataError):
        connector.snapshot_from_api(
            api_fixture,
            "https://meli.la/abc",
            "https://www.mercadolivre.com.br/MLB-1234567890-fone",
        )


def test_unavailable_api_status_keeps_the_snapshot_explicitly_unavailable(connector, api_fixture):
    # Mapping every API status to active would silently republish paused products.
    api_fixture["status"] = "paused"

    assert connector.snapshot_from_api(
        api_fixture,
        "https://meli.la/abc",
        "https://www.mercadolivre.com.br/MLB-1234567890-fone",
    ).available is False


def test_preserves_affiliate_link_on_metadata_fallback(html_fixture):
    # Replacing this value with the resolved URL would discard the affiliate attribution.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    client = ScriptedHttpClient((
        _html("https://www.mercadolivre.com.br/MLB-1234567890-fone", html_fixture),
        BlockedByStoreError("API pública bloqueada"),
    ))
    value = MercadoLivreConnector(client, PARTNERS["mercado_livre"]).fetch(
        "https://www.mercadolivre.com.br/MLB-1234567890-item?affiliate=keep"
    )

    assert value.affiliate_url == "https://www.mercadolivre.com.br/MLB-1234567890-item?affiliate=keep"
    assert value.source_url == "https://www.mercadolivre.com.br/MLB-1234567890-fone"
    assert value.coupon is None
    assert value.images == ("https://http2.mlstatic.com/D_NQ_NP_html.jpg",)
    assert value.category == "Eletrônicos"


def test_does_not_turn_an_api_not_found_into_html_success(html_fixture):
    # Falling back on a real 404 would revive a product the public API says no longer exists.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    client = ScriptedHttpClient((
        _html("https://www.mercadolivre.com.br/MLB-1234567890-fone", html_fixture),
        ProductNotFoundError("Produto não encontrado."),
    ))

    with pytest.raises(ProductNotFoundError):
        MercadoLivreConnector(client, PARTNERS["mercado_livre"]).fetch(
            "https://www.mercadolivre.com.br/MLB-1234567890-fone"
        )


def test_rejects_html_without_a_trusted_item_id():
    # Fallback without an identity would publish an item with an invented external ID.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    client = ScriptedHttpClient((
        _html(
            "https://www.mercadolivre.com.br/sem-id",
            b"<html><body>MLB1234567890 em texto arbitrario</body></html>",
        ),
    ))

    with pytest.raises(InvalidProductDataError):
        MercadoLivreConnector(client, PARTNERS["mercado_livre"]).fetch(
            "https://www.mercadolivre.com.br/sem-id"
        )


def test_rejects_structured_url_ids_from_foreign_hosts():
    # Trusting an arbitrary JSON-LD URL would let a page claim an unrelated item identity.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    html = b'''<script type="application/ld+json">{
      "@type": "Product", "url": "https://evil.example/MLB1234567890-item"
    }</script>'''
    client = ScriptedHttpClient((
        _html("https://www.mercadolivre.com.br/sem-id", html),
    ))

    with pytest.raises(InvalidProductDataError):
        MercadoLivreConnector(client, PARTNERS["mercado_livre"]).fetch(
            "https://www.mercadolivre.com.br/sem-id"
        )

    assert len(client.calls) == 1


def test_fetch_rejects_unsupported_url_without_http_call():
    # Network I/O before validation would permit an attacker-controlled request.
    from automation.connectors.mercado_livre import MercadoLivreConnector

    client = ScriptedHttpClient(())

    with pytest.raises(UnsupportedUrlError):
        MercadoLivreConnector(client, PARTNERS["mercado_livre"]).fetch(
            "https://mercadolivre.com.br.evil.example/MLB-1234567890"
        )

    assert client.calls == []


def test_registry_discovers_mercado_livre_from_the_valid_default_config():
    # Omitting the implemented module from the registry would make valid Mercado Livre links unselectable.
    from automation.connectors.base import build_connector_registry

    registry = build_connector_registry(ScriptedHttpClient(()))

    assert registry.select("https://meli.la/affiliate-kept").partner_key == "mercado_livre"
