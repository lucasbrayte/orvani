from decimal import Decimal
from pathlib import Path

import pytest

from automation.metadata import (
    clean_text,
    extract_product_metadata,
    parse_decimal,
    unique_https_images,
)
from automation.models import InvalidProductDataError


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")


def test_extracts_jsonld_without_inventing_coupon(load_fixture):
    # Removing the JSON-LD Offer parser would lose the public product facts below.
    data = extract_product_metadata(load_fixture("product-jsonld.html"), "https://example.com/item")

    assert data.name == "Produto de teste"
    assert data.description == "Descrição segura do produto."
    assert data.current_price == Decimal("149.90")
    assert data.previous_price == Decimal("199.90")
    assert data.currency == "BRL"
    assert data.images == ("https://images.example.com/item-1.jpg",)
    assert data.coupon is None
    assert data.source_category == "Eletrônicos > Áudio"
    assert data.available is True


def test_checks_every_jsonld_block_and_walks_a_graph(load_fixture):
    # Considering only the first script block would select no Product.
    data = extract_product_metadata(load_fixture("product-multiple-jsonld.html"), "https://example.com/item")

    assert data.name == "Produto no segundo bloco"
    assert data.current_price == Decimal("79.90")
    assert data.images == ("https://images.example.com/second.jpg",)


def test_recognizes_schema_type_urls_and_uses_a_higher_price_specification():
    # Exact literal type matching would skip normal JSON-LD schema URLs and its valid offer.
    html = '''<script type="application/ld+json">{
      "@type":"https://schema.org/Product", "name":"Produto com especificação",
      "offers":{"@type":"https://schema.org/Offer", "price":"100", "priceCurrency":"BRL",
      "priceSpecification":{"@type":"PriceSpecification", "price":"120"}}
    }</script>'''

    data = extract_product_metadata(html, "https://example.com/item")

    assert data.current_price == Decimal("100")
    assert data.previous_price == Decimal("120")


def test_uses_open_graph_when_no_valid_jsonld_product_exists(load_fixture):
    # Removing Open Graph fallback would reject this page despite its public price.
    data = extract_product_metadata(load_fixture("product-opengraph.html"), "https://example.com/item")

    assert data.name == "Produto Open Graph"
    assert data.description == "Oferta pública & segura"
    assert data.current_price == Decimal("1234.56")
    assert data.previous_price is None
    assert data.currency == "BRL"
    assert data.images == ("https://images.example.com/open-graph.jpg",)


@pytest.mark.parametrize(("raw", "expected"), [
    ("R$ 1.234,56", Decimal("1234.56")),
    ("1,234.56", Decimal("1234.56")),
    (149.9, Decimal("149.9")),
])
def test_parses_public_price_formats_without_float_arithmetic(raw, expected):
    # Replacing locale-aware normalization with Decimal(str(raw)) breaks Brazilian prices.
    assert parse_decimal(raw) == expected


def test_discards_a_previous_price_that_is_not_a_discount():
    html = '''<script type="application/ld+json">{
      "@type":"Product", "name":"Sem desconto", "offers":{
        "@type":"Offer", "price":"100", "highPrice":"100", "priceCurrency":"BRL"
      }}</script>'''

    data = extract_product_metadata(html, "https://example.com/item")

    assert data.current_price == Decimal("100")
    assert data.previous_price is None


def test_clean_text_removes_executable_content_normalizes_unicode_space_and_limits_length():
    # Keeping script/style text would expose non-product content in the catalog description.
    dirty = "<p>  Oferta\u00a0especial  </p><script>não copiar()</script><style>.x{}</style>"

    assert clean_text(dirty) == "Oferta especial"
    assert clean_text("x" * 4_010) == "x" * 4_000


def test_ignores_review_content_when_choosing_product_description():
    html = '''<script type="application/ld+json">{
      "@type":"Product", "name":"Produto", "description":"Descrição do fabricante",
      "aggregateRating":{"@type":"AggregateRating","description":"Avaliação não copiar"},
      "review":{"@type":"Review","description":"Comentário não copiar"},
      "offers":{"@type":"Offer","price":"10","priceCurrency":"BRL"}
    }</script>'''

    assert extract_product_metadata(html, "https://example.com/item").description == "Descrição do fabricante"


def test_keeps_only_safe_distinct_https_images_in_first_seen_order_and_caps_at_four():
    # Removing URL/dimension/context filtering would publish tracking, logo, or tiny image assets.
    images = [
        " http://images.example.com/insecure.jpg ",
        "https://images.example.com/logo.png",
        {"url": "https://images.example.com/tiny.jpg", "width": 119, "height": 120},
        "https://images.example.com/one.jpg#fragment",
        "https://images.example.com/one.jpg",
        "https://images.example.com/two.jpg",
        "https://images.example.com/three.jpg",
        "https://images.example.com/four.jpg",
        "https://images.example.com/five.jpg",
    ]

    assert unique_https_images(images) == (
        "https://images.example.com/one.jpg",
        "https://images.example.com/two.jpg",
        "https://images.example.com/three.jpg",
        "https://images.example.com/four.jpg",
    )


def test_rejects_metadata_without_a_positive_public_price():
    html = '<meta property="og:title" content="Sem preço">'

    with pytest.raises(InvalidProductDataError):
        extract_product_metadata(html, "https://example.com/item")
