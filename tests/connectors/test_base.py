from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from automation.config import PartnerConfig
from automation.connectors import base
from automation.connectors.base import (
    ConnectorRegistry,
    MetadataConnectorBase,
    ProductConnector,
    build_connector_registry,
)
from automation.http_client import HttpResponse
from automation.metadata import ExtractedProductData
from automation.models import (
    ConfigurationError,
    InvalidProductDataError,
    ProductNotFoundError,
    UnsupportedUrlError,
)


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


class ThrowingConnector(StubConnector):
    def supports(self, url: str) -> bool:
        raise RuntimeError(f"falha de suporte: {url}")


class TruthyConnector(StubConnector):
    def supports(self, url: str) -> bool:
        return cast(bool, "yes")


class EmptyIdentifierConnector(FixtureConnector):
    def extract_identifiers(
        self, metadata: ExtractedProductData, source_url: str
    ) -> tuple[str, str | None]:
        return "  ", None


class InvalidIdentifierConnector(FixtureConnector):
    def extract_identifiers(self, metadata: ExtractedProductData, source_url: str):
        return "SKU-123", 42


class InvalidMetadataConnector(FixtureConnector):
    def extract_metadata(self, html: str, source_url: str):
        return "not metadata"


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


def test_product_connector_protocol_accepts_property_and_plain_attribute_partner_keys():
    # A property-only protocol declaration must retain structural compatibility for both styles.
    client = FakeHttpClient(AssertionError("não usado"))

    assert isinstance(StubConnector("mercado_livre", ("mercadolivre.com.br",)), ProductConnector)
    assert isinstance(FixtureConnector(cast(object, client), partner()), ProductConnector)


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


def test_registry_ignores_a_support_exception_before_a_single_match():
    # Letting a broken connector abort selection hides a usable configured connector.
    match = StubConnector("shop", ("shop.example.com",))

    assert ConnectorRegistry((ThrowingConnector("broken", ()), match)).select(
        "https://shop.example.com/item"
    ) is match


def test_registry_turns_only_support_exceptions_into_unsupported_url():
    # A RuntimeError from plugin support probing must never escape the registry boundary.
    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry((ThrowingConnector("broken", ()),)).select(
            "https://shop.example.com/item"
        )


def test_registry_accepts_only_a_boolean_true_support_result():
    # A malformed truthy value must not select a connector that broke the boolean contract.
    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry((TruthyConnector("broken", ()),)).select(
            "https://shop.example.com/item"
        )


def test_registry_still_rejects_ambiguity_after_ignoring_a_support_exception():
    # Skipping a broken connector must not turn two actual matches into a deterministic choice.
    first = StubConnector("first", ("shop.example.com",))
    second = StubConnector("second", ("shop.example.com",))

    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry((ThrowingConnector("broken", ()), first, second)).select(
            "https://shop.example.com/item"
        )


def test_registry_does_not_match_a_deceptive_host_by_substring():
    # A substring match would route an attacker-controlled mercadolivre.com.br.evil host.
    mercado = StubConnector("mercado_livre", ("mercadolivre.com.br",))

    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry((mercado,)).select("https://mercadolivre.com.br.evil.example/item")


def test_metadata_connector_supports_does_not_match_a_deceptive_host_by_substring():
    # A base connector must reject the deceptive host before the safe client sees it.
    client = FakeHttpClient(AssertionError("HTTP não deveria ser chamado"))

    assert FixtureConnector(cast(object, client), partner()).supports(
        "https://shop.example.com.evil.test/item"
    ) is False


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


@pytest.mark.parametrize(
    "connector_type",
    [EmptyIdentifierConnector, InvalidIdentifierConnector, InvalidMetadataConnector],
)
def test_metadata_connector_rejects_invalid_identifier_hook_results(connector_type):
    # Blank IDs or malformed identifier tuples would create snapshots with an invented identity.
    client = FakeHttpClient(
        HttpResponse(
            url="https://shop.example.com/products/terminal",
            status_code=200,
            media_type="text/html",
            body=b"<html>fixture</html>",
        )
    )
    connector = connector_type(
        cast(object, client),
        partner(),
        metadata_extractor=lambda _html, _source: metadata(),
    )

    with pytest.raises(InvalidProductDataError):
        connector.fetch("https://shop.example.com/item")


def _partners_for_builder() -> dict[str, PartnerConfig]:
    return {
        key: PartnerConfig(key, key, (f"{key}.test",), False)
        for key, _class_name in base._FUTURE_CONNECTORS
    }


def _missing_module(name: str) -> ModuleNotFoundError:
    error = ModuleNotFoundError(name)
    error.name = name
    return error


def test_builder_ignores_only_concrete_modules_that_are_absent(monkeypatch):
    # Treating all import failures as optional would hide a broken concrete connector.
    imported: list[str] = []

    def import_missing(module_name: str):
        imported.append(module_name)
        raise _missing_module(module_name)

    monkeypatch.setattr(base, "import_module", import_missing)

    registry = build_connector_registry(cast(object, FakeHttpClient(AssertionError("não usado"))))

    assert imported == [f"automation.connectors.{key}" for key, _ in base._FUTURE_CONNECTORS]
    with pytest.raises(UnsupportedUrlError):
        registry.select("https://unknown.example/item")


def test_builder_uses_approved_order_when_concrete_modules_are_present(monkeypatch):
    # Reordering module construction would change predictable first-match configuration order.
    constructed: list[str] = []

    def connector_class_for(key: str):
        class FakeConnector:
            def __init__(self, _http_client, partner_config: PartnerConfig) -> None:
                constructed.append(partner_config.key)
                self.partner_key = partner_config.key

            def supports(self, url: str) -> bool:
                return url == f"https://{self.partner_key}.test/item"

            def fetch(self, affiliate_url: str):
                raise AssertionError(affiliate_url)

        return FakeConnector

    modules = {
        f"automation.connectors.{key}": SimpleNamespace(**{class_name: connector_class_for(key)})
        for key, class_name in base._FUTURE_CONNECTORS
    }
    monkeypatch.setattr(base, "import_module", modules.__getitem__)

    registry = build_connector_registry(
        cast(object, FakeHttpClient(AssertionError("não usado"))), _partners_for_builder()
    )

    assert constructed == [key for key, _ in base._FUTURE_CONNECTORS]
    assert registry.select("https://shopee.test/item").partner_key == "shopee"


def test_builder_rejects_missing_config_for_an_existing_module(monkeypatch):
    # Silently omitting an implemented connector makes deployment configuration appear valid.
    module_name, class_name = base._FUTURE_CONNECTORS[0]
    monkeypatch.setattr(
        base,
        "import_module",
        lambda _module_name: SimpleNamespace(**{class_name: StubConnector}),
    )

    with pytest.raises(ConfigurationError):
        build_connector_registry(cast(object, FakeHttpClient(AssertionError("não usado"))), {})


@pytest.mark.parametrize("error", [ImportError("interno"), _missing_module("dependency.internal")])
def test_builder_does_not_silence_internal_import_errors(monkeypatch, error):
    # An optional connector is absent only when Python names that connector module itself.
    monkeypatch.setattr(base, "import_module", lambda _module_name: (_ for _ in ()).throw(error))

    with pytest.raises(type(error)) as raised:
        build_connector_registry(cast(object, FakeHttpClient(AssertionError("não usado"))))

    assert raised.value is error


def test_builder_turns_a_missing_connector_class_into_configuration_error(monkeypatch):
    # A present module without its promised connector class is a broken application configuration.
    monkeypatch.setattr(base, "import_module", lambda _module_name: SimpleNamespace())

    with pytest.raises(ConfigurationError):
        build_connector_registry(cast(object, FakeHttpClient(AssertionError("não usado"))))


def test_builder_does_not_silence_connector_construction_errors(monkeypatch):
    # Constructor failures must remain visible instead of producing a partial registry.
    module_name, class_name = base._FUTURE_CONNECTORS[0]

    class BrokenConnector:
        def __init__(self, _http_client, _partner_config) -> None:
            raise RuntimeError("construction failed")

    monkeypatch.setattr(
        base,
        "import_module",
        lambda _module_name: SimpleNamespace(**{class_name: BrokenConnector}),
    )

    with pytest.raises(RuntimeError, match="construction failed"):
        build_connector_registry(
            cast(object, FakeHttpClient(AssertionError("não usado"))),
            {module_name: PartnerConfig(module_name, module_name, (), False)},
        )
