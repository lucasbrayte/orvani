from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from automation.config import PARTNERS
from automation.http_client import HttpResponse
from automation.models import BlockedByStoreError, ImportRecord, ImportStatus, InvalidProductDataError, UnsafeRedirectError


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
    return (FIXTURES / "shopee-product.html").read_bytes()


@pytest.fixture
def shopee_connector():
    from automation.connectors.shopee import ShopeeConnector

    return ShopeeConnector(
        ScriptedHttpClient(()),
        PARTNERS["shopee"],
        clock=lambda: datetime(2026, 8, 30, 12, tzinfo=UTC),
    )


def test_supports_only_approved_https_shopee_hosts(shopee_connector):
    # Relaxing exact host or URL-shape validation would make a private fetch reachable.
    assert shopee_connector.supports("https://shopee.com.br/fone-i.123.456") is True
    assert shopee_connector.supports("https://www.shopee.com.br/fone-i.123.456") is True
    assert shopee_connector.supports("https://s.shopee.com.br/AbCd") is True
    for unsafe in (
        "http://shopee.com.br/fone-i.123.456",
        "https://shopee.com.br.evil.example/fone-i.123.456",
        "https://shopee.com.br@evil.example/fone-i.123.456",
        "https://shopee.com.br:444/fone-i.123.456",
    ):
        assert shopee_connector.supports(unsafe) is False


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("https://shopee.com.br/fone-i.123456.987654321", "123456.987654321"),
        ("/product/123456/987654321", "123456.987654321"),
        ("https://shopee.com.br/i.123.456", "123.456"),
        ("https://shopee.com.br/fone-i.0.456", None),
        ("https://shopee.com.br/fone-i.123.0", None),
        ("https://shopee.com.br/fone-i.1234567890123456.456", None),
        ("texto 123456.987654321 não é identidade de página", None),
        ("https://shopee.com.br/?id=123456.987654321", None),
    ),
)
def test_extracts_only_positive_bounded_item_ids_from_page_paths(value, expected):
    # Matching arbitrary text or query data would attach an unrelated Shopee identity.
    from automation.connectors.shopee import extract_shopee_item_id

    assert extract_shopee_item_id(value) == expected


def test_fetches_public_direct_page_without_private_or_affiliate_endpoint(html_fixture):
    # Adding any extra request would violate the metadata-only collection boundary.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/fone-publico-i.123456.987654321"
    client = ScriptedHttpClient((_html(url, html_fixture),))
    value = ShopeeConnector(client, PARTNERS["shopee"]).fetch(url)

    assert value.external_id == "123456.987654321"
    assert value.source_url == url
    assert value.affiliate_url == url
    assert value.current_price == Decimal("149.90")
    assert value.previous_price is None
    assert value.coupon is None
    assert client.calls == [(url, ("shopee.com.br", "s.shopee.com.br"), ("text/html", "application/xhtml+xml"))]


def test_short_link_preserves_original_affiliate_url(html_fixture):
    # Replacing the supplied short URL loses the attribution used for later publication.
    from automation.connectors.shopee import ShopeeConnector

    affiliate_url = "https://s.shopee.com.br/AbCd"
    terminal_url = "https://shopee.com.br/fone-publico-i.123456.987654321"
    value = ShopeeConnector(
        ScriptedHttpClient((_html(terminal_url, html_fixture),)), PARTNERS["shopee"]
    ).fetch(affiliate_url)

    assert value.source_url == terminal_url
    assert value.affiliate_url == affiliate_url


def test_safe_client_follows_only_an_allowed_short_link_redirect(http_client_factory, html_fixture):
    # Bypassing SafeHttpClient would stop per-hop validation of short-link destinations.
    from automation.connectors.shopee import ShopeeConnector

    short_url = "https://s.shopee.com.br/AbCd"
    terminal_url = "https://shopee.com.br/fone-publico-i.123456.987654321"
    client, _calls = http_client_factory({
        short_url: (302, {"location": terminal_url}, b""),
        terminal_url: (200, {"content-type": "text/html"}, html_fixture),
    })

    value = ShopeeConnector(client, PARTNERS["shopee"]).fetch(short_url)

    assert value.source_url == terminal_url
    assert value.affiliate_url == short_url


def test_disallowed_short_link_redirect_is_terminal(http_client_factory):
    # Falling through to a foreign redirect would turn a tracking link into an SSRF fetch.
    from automation.connectors.shopee import ShopeeConnector

    short_url = "https://s.shopee.com.br/AbCd"
    client, _calls = http_client_factory({
        short_url: (302, {"location": "https://evil.example/item"}, b""),
    })

    with pytest.raises(UnsafeRedirectError):
        ShopeeConnector(client, PARTNERS["shopee"]).fetch(short_url)


def test_rejects_missing_current_price_without_inventing_a_value(html_fixture):
    # Accepting a product with no current price would create a publishable price from absent metadata.
    from automation.connectors.shopee import ShopeeConnector

    no_price = html_fixture.replace(b'"price": "149.90", ', b"")
    url = "https://shopee.com.br/fone-publico-i.123456.987654321"
    with pytest.raises(InvalidProductDataError):
        ShopeeConnector(ScriptedHttpClient((_html(url, no_price),)), PARTNERS["shopee"]).fetch(url)


def test_propagates_persistent_store_blocking_without_metadata_fallback():
    # Converting a block to an empty snapshot would overwrite prior reviewed data.
    from automation.connectors.shopee import ShopeeConnector

    client = ScriptedHttpClient((BlockedByStoreError("bloqueado"),))
    with pytest.raises(BlockedByStoreError):
        ShopeeConnector(client, PARTNERS["shopee"]).fetch(
            "https://shopee.com.br/fone-publico-i.123456.987654321"
        )


def test_rejects_an_id_present_only_in_unrelated_text_or_related_product():
    # Scraping body text or related entities would select a product other than the terminal page.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<html><body>123456.987654321
      <script type="application/ld+json">{
        "@type": "Product", "name": "Principal", "isRelatedTo": {
          "@type": "Product", "sku": "123456.987654321"
        }, "offers": {"@type":"Offer", "price":"9.90", "priceCurrency":"BRL"}
      }</script></body></html>'''

    with pytest.raises(InvalidProductDataError):
        ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)


def test_rejects_foreign_canonical_and_structured_identity():
    # A trusted ID must belong to an approved terminal page, not a foreign JSON-LD claim.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<link rel="canonical" href="https://evil.example/i.123.456">
      <script type="application/ld+json">{
        "@type":"Product", "url":"https://evil.example/i.123.456", "sku":"123.456",
        "offers":{"@type":"Offer", "price":"9.90", "priceCurrency":"BRL"}
      }</script>'''

    with pytest.raises(InvalidProductDataError):
        ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)


def test_uses_only_the_terminal_webpage_main_product_jsonld_identity(html_fixture):
    # Taking a related JSON-LD SKU would mismatch the page's explicitly designated product.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<script type="application/ld+json">{
      "@context": "https://schema.org", "@type": "WebPage",
      "@id": "https://shopee.com.br/produto-principal",
      "mainEntity": {"@type": "Product", "sku": "123456.987654321",
        "mainEntityOfPage": "https://shopee.com.br/produto-principal",
        "isRelatedTo": {"@type": "Product", "sku": "111.222"},
        "name": "Fone publico Shopee", "description": "Audio",
        "image": "https://images.example.test/fone.jpg",
        "offers": {"@type": "Offer", "price": "149.90", "priceCurrency": "BRL"}
      }
    }</script>'''

    value = ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)

    assert value.external_id == "123456.987654321"


def test_rejects_main_product_designated_by_a_foreign_webpage():
    # Trusting a foreign WebPage wrapper would make its product claim an identity for this terminal page.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<script type="application/ld+json">{
      "@type": "WebPage", "@id": "https://evil.example/produto-principal",
      "mainEntity": {"@type": "Product", "sku": "123456.987654321",
        "mainEntityOfPage": "https://shopee.com.br/produto-principal",
        "name": "Produto publico", "offers": {"@type": "Offer", "price": "9.90", "priceCurrency": "BRL"}
      }
    }</script>'''

    with pytest.raises(InvalidProductDataError):
        ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)


def test_rejects_a_top_level_product_fragment_id_without_page_association():
    # A fragment identifies a graph node, not the terminal page's main product.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<script type="application/ld+json">{
      "@type": "Product", "@id": "#produto-relacionado", "sku": "123.456",
      "name": "Produto relacionado", "offers": {
        "@type": "Offer", "price": "9.90", "priceCurrency": "BRL"
      }
    }</script>'''

    with pytest.raises(InvalidProductDataError):
        ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)


def test_does_not_combine_a_webpage_main_entity_and_product_across_jsonld_blocks():
    # Cross-block graph resolution would allow an unrelated Product to borrow another block's mainEntity.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<script type="application/ld+json">{
      "@type": "WebPage", "@id": "https://shopee.com.br/produto-principal",
      "mainEntity": {"@id": "#produto-principal"}
    }</script>
    <script type="application/ld+json">{
      "@type": "Product", "@id": "#produto-principal", "sku": "123.456",
      "name": "Produto separado", "offers": {
        "@type": "Offer", "price": "9.90", "priceCurrency": "BRL"
      }
    }</script>'''

    with pytest.raises(InvalidProductDataError):
        ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)


def test_accepts_a_webpage_main_entity_resolved_from_its_own_jsonld_graph():
    # Rejecting a graph-local mainEntity would discard a normal structured product identity.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<script type="application/ld+json">{
      "@graph": [
        {"@type": "WebPage", "@id": "https://shopee.com.br/produto-principal",
          "mainEntity": {"@id": "#produto-principal"}},
        {"@type": ["https://schema.org/Product"], "@id": "#produto-principal",
          "sku": "123.456", "name": "Produto principal", "offers": {
            "@type": "Offer", "price": "9.90", "priceCurrency": "BRL"
          }}
      ]
    }</script>'''

    value = ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)

    assert value.external_id == "123.456"


def test_accepts_top_level_product_with_absolute_main_entity_page_reference():
    # Requiring a WebPage wrapper would reject public Product JSON-LD that names its terminal page.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    html = b'''<script type="application/ld+json">{
      "@type": ["Product"], "mainEntityOfPage": "https://shopee.com.br/produto-principal",
      "sku": "123.456", "name": "Produto principal", "offers": {
        "@type": "Offer", "price": "9.90", "priceCurrency": "BRL"
      }
    }</script>'''

    value = ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)

    assert value.external_id == "123.456"


def test_accepts_top_level_product_referencing_a_trusted_canonical_page():
    # A trusted canonical is an explicit page identity when the terminal URL was redirected.
    from automation.connectors.shopee import ShopeeConnector

    url = "https://shopee.com.br/produto-principal"
    canonical = "https://shopee.com.br/produto-canonico"
    html = b'''<link rel="canonical" href="https://shopee.com.br/produto-canonico">
    <script type="application/ld+json">{
      "@type": "Product", "url": "https://shopee.com.br/produto-canonico",
      "sku": "123.456", "name": "Produto canonico", "offers": {
        "@type": "Offer", "price": "9.90", "priceCurrency": "BRL"
      }
    }</script>'''

    value = ShopeeConnector(ScriptedHttpClient((_html(url, html),)), PARTNERS["shopee"]).fetch(url)

    assert value.external_id == "123.456"
    assert value.source_url == url
    assert canonical != value.source_url


def test_registry_contains_mercado_shopee_shein_then_inert_tiktok():
    # Omitting an implemented connector or reordering it changes deterministic registration.
    from automation.connectors.base import build_connector_registry

    registry = build_connector_registry(ScriptedHttpClient(()))

    assert [connector.partner_key for connector in registry._connectors] == [
        "mercado_livre", "shopee", "shein", "tiktok_shop"
    ]
    assert registry.select("https://s.shopee.com.br/AbCd").partner_key == "shopee"


def _record(row_number, **changes):
    base = ImportRecord(
        row_number=row_number,
        automation_id=f"id-{row_number}", active="Sim", publish="Não", featured="Não", order="",
        update_mode="Automático", product_url=f"https://shopee.com.br/item-i.123.{row_number + 1}",
        affiliate_url="", partner="shopee", external_id="", name="", description="", category="",
        subcategory="", product_type="", current_price=None, previous_price=None,
        calculated_discount="", coupon="", coupon_expires_at="", image_1="", image_2="", image_3="",
        image_4="", button_text="", status=ImportStatus.NOVO, message="", consecutive_attempts=0,
        last_published_url="", data_signature="", last_checked_at="", last_updated_at="",
    )
    return replace(base, **changes)


@pytest.mark.parametrize(("count", "expected_sizes"), ((0, []), (1, [1]), (5, [5]), (6, [5, 1]), (11, [5, 5, 1])))
def test_batches_cap_at_five_and_keep_sheet_order(count, expected_sizes):
    # Changing the grouping or sorting would give manual conversion a different queue than the sheet.
    from automation.connectors.shopee import build_conversion_batches

    rows = tuple(_record(index + 2) for index in range(count))
    batches = build_conversion_batches(rows)

    assert [len(batch) for batch in batches] == expected_sizes
    assert [record.row_number for batch in batches for record in batch] == list(range(2, count + 2))
    assert [record.message for batch in batches for record in batch] == [
        f"Lote Shopee {(index // 5) + 1:02d} — máximo 5 links" for index in range(count)
    ]
    assert all(record.status is ImportStatus.AGUARDANDO_CONVERSAO for batch in batches for record in batch)


def test_batches_filter_exact_active_link_and_status_values_without_mutating_records():
    # Broad coercion would queue disabled, converted, malformed, or unrelated rows for manual work.
    from automation.connectors.shopee import build_conversion_batches

    eligible = _record(2)
    rows = (
        eligible,
        _record(3, active="sim"),
        _record(4, active=" Sim "),
        _record(5, product_url="   "),
        _record(6, affiliate_url="   "),
        _record(7, affiliate_url="https://s.shopee.com.br/ready"),
        _record(8, status=ImportStatus.REVISAR),
        _record(9, status=ImportStatus.AGUARDANDO_CONVERSAO),
        _record(10, product_url=" https://shopee.com.br/item-i.123.11 "),
    )
    original = tuple((row.status, row.message) for row in rows)

    batches = build_conversion_batches(rows)

    assert [[record.row_number for record in batch] for batch in batches] == [[2, 6, 9, 10]]
    assert tuple((row.status, row.message) for row in rows) == original
    assert batches[0][0] is not eligible


def test_batches_use_the_custom_positive_size_in_messages_without_mutating_records():
    # A fixed five-link message would mislead manual conversion when a smaller requested limit is used.
    from automation.connectors.shopee import build_conversion_batches

    rows = tuple(_record(row_number) for row_number in range(2, 7))
    original = tuple((row.status, row.message) for row in rows)

    batches = build_conversion_batches(rows, batch_size=2)

    assert [len(batch) for batch in batches] == [2, 2, 1]
    assert [[record.row_number for record in batch] for batch in batches] == [[2, 3], [4, 5], [6]]
    assert [[record.message for record in batch] for batch in batches] == [
        ["Lote Shopee 01 — máximo 2 links", "Lote Shopee 01 — máximo 2 links"],
        ["Lote Shopee 02 — máximo 2 links", "Lote Shopee 02 — máximo 2 links"],
        ["Lote Shopee 03 — máximo 2 links"],
    ]
    assert all(
        record.status is ImportStatus.AGUARDANDO_CONVERSAO
        for batch in batches
        for record in batch
    )
    assert tuple((row.status, row.message) for row in rows) == original


@pytest.mark.parametrize("invalid_batch_size", (0, -1, 1.5, True, "5", None))
def test_batches_reject_invalid_batch_sizes(invalid_batch_size):
    # Treating invalid limits as defaults can make a supposedly capped manual batch unbounded.
    from automation.connectors.shopee import build_conversion_batches

    with pytest.raises((TypeError, ValueError)):
        build_conversion_batches((_record(2),), batch_size=invalid_batch_size)


def test_batches_reject_non_import_records():
    # Accepting lookalike records would bypass the 32-column import model contract.
    from automation.connectors.shopee import build_conversion_batches

    with pytest.raises(TypeError):
        build_conversion_batches((object(),))
