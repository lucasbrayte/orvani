from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from automation.config import PARTNERS, PartnerConfig
from automation.http_client import HttpResponse
from automation.models import InvalidProductDataError, ProductNotFoundError, UnsupportedUrlError


FIXTURES = Path(__file__).parents[1] / "fixtures"
FIXTURE_PARTNER = PartnerConfig("tiktok_shop", "TikTok Shop fixture", ("shop.tiktok.test",), False)


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
    return (FIXTURES / "tiktok-shop-product.html").read_bytes()


def test_production_has_no_hosts_and_never_supports_a_tiktok_url():
    # Adding a real host before an official sample would activate unsupported production fetching.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    connector = TikTokShopConnector(ScriptedHttpClient(()), PARTNERS["tiktok_shop"])

    assert connector.allowed_hosts == ()
    assert connector.live_verified is False
    assert connector.supports("https://www.tiktok.com/shop/item/1") is False
    assert connector.supports("https://shop.tiktok.test/product/123") is False


def test_fixture_host_builds_an_offline_metadata_snapshot(html_fixture):
    # The fixture host proves only parser behavior and must not leak into production settings.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    url = "https://shop.tiktok.test/product/123"
    client = ScriptedHttpClient((_html(url, html_fixture),))
    value = TikTokShopConnector(
        client, FIXTURE_PARTNER, clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC)
    ).fetch(url)

    assert value.partner == "tiktok_shop"
    assert value.external_id == "123"
    assert value.source_url == url
    assert value.affiliate_url == url
    assert value.current_price == Decimal("49.90")
    assert value.previous_price == Decimal("69.90")
    assert value.images == ("https://images.example.test/tiktok-fone.jpg",)
    assert value.coupon is None
    assert client.calls == [(url, ("shop.tiktok.test",), ("text/html", "application/xhtml+xml"))]


def test_fixture_host_rejects_incomplete_metadata_without_inventing_fields(html_fixture):
    # Filling a missing price with a default would make an incomplete fixture publishable.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    url = "https://shop.tiktok.test/product/123"
    no_price = html_fixture.replace(b'          "price": "49.90",\n', b"")
    with pytest.raises(InvalidProductDataError):
        TikTokShopConnector(ScriptedHttpClient((_html(url, no_price),)), FIXTURE_PARTNER).fetch(url)


def test_fixture_host_rejects_foreign_terminal_response(html_fixture):
    # Trusting a fake client's foreign terminal URL would bypass the host boundary before API use.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    client = ScriptedHttpClient((_html("https://evil.example/product/123", html_fixture),))
    with pytest.raises(InvalidProductDataError):
        TikTokShopConnector(client, FIXTURE_PARTNER).fetch("https://shop.tiktok.test/product/123")


def test_optional_api_fake_can_supply_normalized_public_fields_after_safe_identity(html_fixture):
    # Passing API fields through before validating the page identity could mix an unrelated product.
    from automation.connectors.tiktok_shop import TikTokShopApiProduct, TikTokShopConnector

    class FakeApi:
        def __init__(self):
            self.external_ids = []

        def fetch_product(self, external_id):
            self.external_ids.append(external_id)
            return TikTokShopApiProduct(
                name="Fone da API fake",
                description="Dados públicos normalizados para contrato offline.",
                current_price=Decimal("39.90"),
                previous_price=Decimal("59.90"),
                currency="BRL",
                images=("https://images.example.test/tiktok-api-fone.jpg",),
                source_category="Eletrônicos > Áudio",
                available=True,
            )

    url = "https://shop.tiktok.test/product/123"
    api = FakeApi()
    value = TikTokShopConnector(
        ScriptedHttpClient((_html(url, html_fixture),)), FIXTURE_PARTNER, api=api
    ).fetch(url)

    assert api.external_ids == ["123"]
    assert value.external_id == "123"
    assert value.current_price == Decimal("39.90")
    assert value.previous_price == Decimal("59.90")
    assert value.category == "Eletrônicos"
    assert value.subcategory == "Áudio"
    assert value.affiliate_url == url


def test_optional_api_rejects_invalid_normalized_data(html_fixture):
    # A malformed future API response must become a typed product-data error, not a partial snapshot.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    class InvalidApi:
        def fetch_product(self, external_id):
            assert external_id == "123"
            return object()

    url = "https://shop.tiktok.test/product/123"
    with pytest.raises(InvalidProductDataError):
        TikTokShopConnector(
            ScriptedHttpClient((_html(url, html_fixture),)), FIXTURE_PARTNER, api=InvalidApi()
        ).fetch(url)


def test_propagates_typed_fetch_errors_without_using_optional_api():
    # Calling an API after a failed page fetch could turn a missing product into a different snapshot.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    class UnexpectedApi:
        def fetch_product(self, external_id):
            raise AssertionError(external_id)

    client = ScriptedHttpClient((ProductNotFoundError("missing"),))
    with pytest.raises(ProductNotFoundError, match="missing"):
        TikTokShopConnector(client, FIXTURE_PARTNER, api=UnexpectedApi()).fetch(
            "https://shop.tiktok.test/product/123"
        )


def test_rejects_unsupported_url_before_any_optional_api_call():
    # A production connector must not become usable merely because an API object was injected.
    from automation.connectors.tiktok_shop import TikTokShopConnector

    class UnexpectedApi:
        def fetch_product(self, external_id):
            raise AssertionError(external_id)

    client = ScriptedHttpClient(())
    with pytest.raises(UnsupportedUrlError):
        TikTokShopConnector(client, PARTNERS["tiktok_shop"], api=UnexpectedApi()).fetch(
            "https://www.tiktok.com/shop/item/1"
        )
    assert client.calls == []


def test_registry_builds_tiktok_last_but_leaves_production_inert():
    # Registry construction must retain the stable four-partner order without activating TikTok hosts.
    from automation.connectors.base import build_connector_registry

    registry = build_connector_registry(ScriptedHttpClient(()))

    assert [connector.partner_key for connector in registry._connectors] == [
        "mercado_livre", "shopee", "shein", "tiktok_shop"
    ]
    with pytest.raises(UnsupportedUrlError):
        registry.select("https://www.tiktok.com/shop/item/1")
