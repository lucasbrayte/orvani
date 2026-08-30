from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from automation.config import PARTNERS
from automation.http_client import HttpResponse
from automation.models import InvalidProductDataError, ProductNotFoundError


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


def _html(url, body):
    return HttpResponse(url=url, status_code=200, media_type="text/html", body=body)


@pytest.fixture
def html_fixture():
    return (FIXTURES / "shein-product.html").read_bytes()


@pytest.fixture
def shein_connector():
    from automation.connectors.shein import SheinConnector

    return SheinConnector(
        ScriptedHttpClient(()),
        PARTNERS["shein"],
        clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC),
    )


def test_fixture_contract_uses_only_sanitized_metadata(shein_connector, html_fixture):
    # A fixture is a repeatable contract, never evidence that this production page is live.
    url = "https://br.shein.com/product-p-123.html"
    client = ScriptedHttpClient((_html(url, html_fixture),))
    value = type(shein_connector)(
        client, PARTNERS["shein"], clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC)
    ).fetch(url)

    assert value.partner == "shein"
    assert value.external_id == "123"
    assert value.source_url == url
    assert value.affiliate_url == url
    assert value.current_price == Decimal("79.90")
    assert value.previous_price == Decimal("99.90")
    assert value.images == ("https://images.example.test/shein-jaqueta.jpg",)
    assert value.coupon is None
    assert value.category == "Moda"
    assert client.calls == [(url, ("shein.com", "br.shein.com", "onelink.shein.com"), ("text/html", "application/xhtml+xml"))]


def test_supports_only_existing_approved_https_hosts(shein_connector):
    # A broader allowlist would authorize a store domain without approved project evidence.
    assert shein_connector.allowed_hosts == ("shein.com", "br.shein.com", "onelink.shein.com")
    assert shein_connector.live_verified is False
    assert shein_connector.supports("https://br.shein.com/product-p-123.html") is True
    assert shein_connector.supports("https://www.shein.com/product-p-123.html") is True
    for unsafe in (
        "http://br.shein.com/product-p-123.html",
        "https://br.shein.com.evil.example/product-p-123.html",
        "https://br.shein.com@evil.example/product-p-123.html",
        "https://br.shein.com:444/product-p-123.html",
    ):
        assert shein_connector.supports(unsafe) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("https://br.shein.com/product-p-123.html", "123"),
        ("/product-p-123.html", "123"),
        ("https://br.shein.com/product-p-000123.html", "000123"),
        ("https://br.shein.com/product-p-0.html", None),
        ("https://br.shein.com/product-p-1234567890123456.html", None),
        ("https://br.shein.com/?product-p-123.html", None),
        ("texto product-p-123.html não é caminho", None),
    ),
)
def test_extracts_bounded_identity_only_from_product_paths(value, expected):
    # Searching arbitrary text or query strings could associate an unrelated product identity.
    from automation.connectors.shein import extract_shein_product_id

    assert extract_shein_product_id(value) == expected


def test_uses_a_trusted_canonical_path_when_terminal_path_has_no_identity(html_fixture):
    # A canonical from another host must not be able to supply the product identity.
    from automation.connectors.shein import SheinConnector

    terminal_url = "https://br.shein.com/brisa-leve.html"
    value = SheinConnector(
        ScriptedHttpClient((_html(terminal_url, html_fixture),)), PARTNERS["shein"]
    ).fetch(terminal_url)

    assert value.external_id == "123"
    assert value.source_url == terminal_url


def test_rejects_foreign_canonical_and_unrelated_jsonld_identity(html_fixture):
    # Taking IDs from foreign or unrelated Product blocks would mix different products.
    from automation.connectors.shein import SheinConnector

    terminal_url = "https://br.shein.com/brisa-leve.html"
    unsafe = html_fixture.replace(
        b'https://br.shein.com/product-p-123.html', b'https://evil.example/product-p-999.html'
    ).replace(b'"sku": "123"', b'"sku": "999"')
    with pytest.raises(InvalidProductDataError):
        SheinConnector(ScriptedHttpClient((_html(terminal_url, unsafe),)), PARTNERS["shein"]).fetch(
            terminal_url
        )


def test_propagates_typed_fetch_errors(shein_connector):
    # Converting a not-found page into a snapshot would invent store data.
    from automation.connectors.shein import SheinConnector

    client = ScriptedHttpClient((ProductNotFoundError("missing"),))
    connector = SheinConnector(client, PARTNERS["shein"])

    with pytest.raises(ProductNotFoundError, match="missing"):
        connector.fetch("https://br.shein.com/product-p-123.html")

    assert client.calls


def test_registry_adds_shein_after_existing_connectors():
    # Omitting SHEIN or reordering it changes deterministic registry construction.
    from automation.connectors.base import build_connector_registry

    registry = build_connector_registry(ScriptedHttpClient(()))

    assert [connector.partner_key for connector in registry._connectors] == [
        "mercado_livre", "shopee", "shein"
    ]
