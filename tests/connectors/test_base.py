from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest

from automation.config import PartnerConfig
from automation.connectors.base import (
    ConnectorRegistry,
    MetadataConnectorBase,
    ProductConnector,
)
from automation.http_client import HttpResponse
from automation.metadata import ExtractedProductData
from automation.models import ProductNotFoundError, UnsupportedUrlError


class StubConnector:
    def __init__(self, partner_key: str, allowed_hosts: tuple[str, ...]) -> None:
        self.partner_key = partner_key
        self._allowed_hosts = allowed_hosts

    def supports(self, url: str) -> bool:
        from automation.security import validate_https_url

        try:
            validate_https_url(url, self._allowed_hosts)
        except Exception:
            return False
        return True

    def fetch(self, affiliate_url: str):
        raise AssertionError(f"fetch inesperado para {affiliate_url}")


class FakeHttpClient:
    def __init__(self, response: HttpResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []

    def get(
        self,
        url: str,
        allowed_hosts: tuple[str, ...],
        expected_content_types: tuple[str, ...],
    ) -> HttpResponse:
        self.calls.append((url, allowed_hosts, expected_content_types))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FixtureConnector(MetadataConnectorBase):
    def extract_identifiers(
        self, metadata: ExtractedProductData, source_url: str
    ) -> tuple[str, str | None]:
        assert metadata.name == "Fone público"
        assert source_url == "https://shop.example.com/products/terminal"
        return "SKU-123", "CAT-9"


def partner() -> PartnerConfig:
    return PartnerConfig("fixture", "Fixture", ("shop.example.com",), False)


def metadata() -> ExtractedProductData:
    return ExtractedProductData(
        name="Fone público",
        description="Áudio para teste",
        current_price=Decimal("149.90"),
        previous_price=Decimal("199.90"),
        currency="BRL",
        images=("https://images.example.com/fone.jpg",),
        coupon=None,
        source_category="Eletrônicos > Áudio",
        available=True,
    )


def test_product_connector_protocol_accepts_the_behavior_required_by_registry():
    # Removing any public connector operation makes this value unsafe for registry callers.
    connector = StubConnector("mercado_livre", ("mercadolivre.com.br",))

    assert isinstance(connector, ProductConnector)


def test_registry_selects_only_supporting_connector_without_fetching():
    # Selecting by configured order must not call a connector's network-facing fetch method.
    mercado = StubConnector("mercado_livre", ("mercadolivre.com.br",))
    shopee = StubConnector("shopee", ("shopee.com.br",))

    assert ConnectorRegistry((mercado, shopee)).select(
        "https://www.mercadolivre.com.br/MLB-1"
    ) is mercado


def test_registry_rejects_unknown_url():
    # Returning an arbitrary connector for no support would issue an unsafe store fetch.
    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry(()).select("https://unknown.example/item")


def test_registry_rejects_ambiguous_support_without_using_order_as_a_tiebreaker():
    # Picking the first connector here would make an accidental overlap fetch from the wrong store.
    first = StubConnector("first", ("shop.example.com",))
    second = StubConnector("second", ("shop.example.com",))

    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry((first, second)).select("https://shop.example.com/item")


def test_registry_does_not_match_a_deceptive_host_by_substring():
    # A substring match would route an attacker-controlled mercadolivre.com.br.evil host.
    mercado = StubConnector("mercado_livre", ("mercadolivre.com.br",))

    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry((mercado,)).select("https://mercadolivre.com.br.evil.example/item")


def test_metadata_connector_builds_snapshot_from_terminal_html_response():
    # Losing either URL would publish a resolved link or fail to identify the fetched page.
    client = FakeHttpClient(
        HttpResponse(
            url="https://shop.example.com/products/terminal",
            status_code=200,
            media_type="text/html",
            body=b"<html>fixture</html>",
        )
    )
    connector = FixtureConnector(
        cast(object, client),
        partner(),
        metadata_extractor=lambda _html, _source: metadata(),
        clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC),
    )

    snapshot = connector.fetch("https://shop.example.com/products/affiliate?tag=keep")

    assert snapshot.partner == "fixture"
    assert snapshot.external_id == "SKU-123"
    assert snapshot.catalog_id == "CAT-9"
    assert snapshot.source_url == "https://shop.example.com/products/terminal"
    assert snapshot.affiliate_url == "https://shop.example.com/products/affiliate?tag=keep"
    assert snapshot.category == "Eletrônicos"
    assert snapshot.subcategory == "Áudio"
    assert snapshot.current_price == Decimal("149.90")
    assert snapshot.previous_price == Decimal("199.90")
    assert snapshot.images == ("https://images.example.com/fone.jpg",)
    assert snapshot.available is True
    assert snapshot.fetched_at == datetime(2026, 8, 30, 12, tzinfo=UTC)
    assert client.calls == [(
        "https://shop.example.com/products/affiliate?tag=keep",
        ("shop.example.com",),
        ("text/html", "application/xhtml+xml"),
    )]


def test_metadata_connector_rejects_unsupported_url_before_calling_http():
    # If validation moves after HTTP, a foreign URL can reach the network client.
    client = FakeHttpClient(AssertionError("HTTP não deveria ser chamado"))
    connector = FixtureConnector(cast(object, client), partner())

    with pytest.raises(UnsupportedUrlError):
        connector.fetch("https://evil.example/item")

    assert client.calls == []


def test_metadata_connector_propagates_typed_http_errors():
    # Swallowing a not-found error would turn a failed fetch into invented product data.
    client = FakeHttpClient(ProductNotFoundError("missing"))
    connector = FixtureConnector(cast(object, client), partner())

    with pytest.raises(ProductNotFoundError, match="missing"):
        connector.fetch("https://shop.example.com/item")
