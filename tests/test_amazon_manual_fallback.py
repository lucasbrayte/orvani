from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from automation.config import PARTNERS
from automation.models import (
    ImportRecord,
    ImportStatus,
    InvalidProductDataError,
    UnsupportedUrlError,
    UpdateMode,
)
import automation.sync as sync

NOW = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)
ASIN = "B0D123ABCD"


def _record(**overrides):
    values = {
        "row_number": 2,
        "automation_id": "amazon-fallback-row-2",
        "active": "Sim",
        "publish": "Sim",
        "featured": "Não",
        "order": "1",
        "update_mode": UpdateMode.AUTOMATICO,
        "product_url": f"https://www.amazon.com.br/dp/{ASIN}?ref_=orvani",
        "affiliate_url": "https://amzn.to/4abcXYZ",
        "partner": "Amazon",
        "external_id": "",
        "name": "Produto Amazon revisado",
        "description": "Dados preenchidos no LibreOffice Calc.",
        "category": "Eletrônicos",
        "subcategory": "Acessórios",
        "product_type": "Físico",
        "current_price": Decimal("149.90"),
        "previous_price": Decimal("199.90"),
        "calculated_discount": "",
        "coupon": "",
        "coupon_expires_at": "",
        "image_1": "https://m.media-amazon.com/images/I/orvani-test.jpg",
        "image_2": "",
        "image_3": "",
        "image_4": "",
        "button_text": "Ver oferta",
        "status": ImportStatus.ERRO,
        "message": "Dados públicos do produto são inválidos.",
        "consecutive_attempts": 0,
        "last_published_url": "",
        "data_signature": "",
        "last_checked_at": "",
        "last_updated_at": "",
    }
    values.update(overrides)
    return ImportRecord(**values)


def test_amazon_backend_partner_configuration_is_exact():
    partner = PARTNERS["amazon"]
    assert partner.key == "amazon"
    assert partner.display_name == "Amazon"
    assert partner.allowed_hosts == ("amazon.com.br", "amzn.to", "link.amazon")
    assert partner.live_verified is False


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (f"https://www.amazon.com.br/dp/{ASIN}", ASIN),
        (f"https://amazon.com.br/gp/product/{ASIN}?tag=orvani-20", ASIN),
        (f"https://www.amazon.com.br/gp/aw/d/{ASIN}#details", ASIN),
        (f"https://www.amazon.com.br/Produto-Teste/dp/{ASIN}/ref=something", ASIN),
    ],
)
def test_amazon_asin_is_extracted_only_from_supported_direct_paths(url, expected):
    assert sync._extract_amazon_asin(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://amzn.to/4abcXYZ",
        "https://www.amazon.com.br/s?k=fone",
        "https://www.amazon.com.br/dp/ABC123",
        "https://amazon.com.br.evil.example/dp/B0D123ABCD",
        "http://www.amazon.com.br/dp/B0D123ABCD",
    ],
)
def test_amazon_asin_rejects_short_links_invalid_paths_and_unsafe_hosts(url):
    assert sync._extract_amazon_asin(url) is None


def test_amazon_partner_urls_accept_only_approved_hosts():
    assert sync._normalized_partner_link_or_none(
        f"https://www.amazon.com.br/dp/{ASIN}", "amazon"
    )
    assert sync._normalized_partner_link_or_none("https://amzn.to/4abcXYZ", "amazon")
    assert sync._normalized_partner_link_or_none(
        "https://link.amazon/B0iTSeEgH", "amazon"
    )
    assert (
        sync._normalized_partner_link_or_none(
            f"https://amazon.com.br.evil.example/dp/{ASIN}", "amazon"
        )
        is None
    )
    assert (
        sync._normalized_partner_link_or_none(
            "https://link.amazon.evil.example/B0iTSeEgH", "amazon"
        )
        is None
    )
    assert (
        sync._normalized_partner_link_or_none(
            "https://evil-link.amazon.example/B0iTSeEgH", "amazon"
        )
        is None
    )
    assert (
        sync._normalized_partner_link_or_none(
            "http://link.amazon/B0iTSeEgH", "amazon"
        )
        is None
    )


@pytest.mark.parametrize(
    "error",
    [
        InvalidProductDataError("metadados públicos insuficientes"),
        UnsupportedUrlError("sem conector Amazon"),
    ],
)
def test_amazon_automatic_failures_fall_back_to_reviewed_calc_data(error):
    engine = sync.SyncEngine(object(), object())
    record = _record()

    item, changes, publication = engine._plan_record(record, error, (), NOW)

    assert item.final_status is ImportStatus.PUBLICADO
    assert item.product_changed is True
    assert item.message == "Produto publicado via fallback manual da Amazon."
    assert changes
    assert len(publication) == 1
    values = publication[0].values[0]
    assert values[2] == "amazon"
    assert values[5] == record.name
    assert values[7] == Decimal("199.90")
    assert values[8] == Decimal("149.90")
    assert values[11] == record.affiliate_url
    assert values[14] == record.image_1


def test_amazon_snapshot_uses_direct_url_asin_and_preserves_reviewed_values():
    record = _record()
    snapshot = sync._manual_amazon_snapshot(record, NOW)

    assert snapshot.partner == "amazon"
    assert snapshot.external_id == ASIN
    assert snapshot.catalog_id is None
    assert snapshot.source_url == record.product_url
    assert snapshot.affiliate_url == record.affiliate_url
    assert snapshot.name == record.name
    assert snapshot.current_price == record.current_price
    assert snapshot.previous_price == record.previous_price
    assert snapshot.images == (record.image_1,)


@pytest.mark.parametrize(
    "record",
    [
        _record(name=""),
        _record(current_price=None),
        _record(image_1=""),
        _record(product_url="https://www.amazon.com.br/s?k=produto"),
        _record(product_url="https://amzn.to/4abcXYZ"),
        _record(previous_price=Decimal("149.90")),
    ],
)
def test_amazon_fallback_rejects_missing_or_unsafe_required_data(record):
    engine = sync.SyncEngine(object(), object())
    item, _changes, publication = engine._plan_record(
        record,
        InvalidProductDataError("metadados públicos insuficientes"),
        (),
        NOW,
    )
    assert item.final_status is ImportStatus.ERRO
    assert item.product_changed is False
    assert publication == ()


def test_amazon_fallback_allows_optional_catalog_text_with_safe_defaults():
    record = _record(
        description="",
        category="",
        subcategory="",
        product_type="",
        button_text="",
    )
    snapshot = sync._manual_amazon_snapshot(record, NOW)
    assert snapshot.name == record.name
    assert snapshot.description == "Oferta disponível na Amazon."
    assert snapshot.category == "Outros"
    assert snapshot.subcategory == "Geral"
    assert snapshot.product_type == "Físico"


def test_amazon_persisted_error_is_reselected_when_fallback_is_ready():
    record = _record()
    signature = (
        f"v1:{sync._record_link_hash(record)}:"
        f"{sync._permanent_error_hash('invalid_product_data')}"
    )
    record = replace(record, data_signature=signature, status=ImportStatus.ERRO)

    assert sync._manual_amazon_fallback_ready(record) is True
    assert sync._is_selected(record, "pending", NOW) is True


def test_amazon_readiness_stays_false_without_direct_asin():
    record = _record(product_url="https://www.amazon.com.br/s?k=produto")
    assert sync._manual_amazon_fallback_ready(record) is False


def test_amazon_fallback_accepts_link_amazon_as_affiliate_only():
    record = _record(affiliate_url="https://link.amazon/B0iTSeEgH")
    snapshot = sync._manual_amazon_snapshot(record, NOW)

    assert snapshot.external_id == ASIN
    assert snapshot.source_url == record.product_url
    assert snapshot.affiliate_url == "https://link.amazon/B0iTSeEgH"


def test_amazon_link_amazon_is_not_used_as_product_identity():
    record = _record(
        product_url="https://link.amazon/B0iTSeEgH",
        affiliate_url="https://link.amazon/B0iTSeEgH",
    )
    with pytest.raises(InvalidProductDataError):
        sync._manual_amazon_snapshot(record, NOW)
