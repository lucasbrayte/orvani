from dataclasses import replace

from libreoffice_sync.hashing import editable_payload
from libreoffice_sync.normalization import infer_partner, normalize_catalog_row
from libreoffice_sync.validation import validate_catalog_row


def amazon_row(valid_row, **overrides):
    values = {
        "partner": "Amazon",
        "update_mode": "Automático",
        "product_url": "https://www.amazon.com.br/dp/B0D123ABCD",
        "affiliate_url": "https://amzn.to/4abcXYZ",
        "name": "Produto Amazon",
        "current_price": valid_row.current_price,
        "images": ("https://m.media-amazon.com/images/I/test.jpg", "", "", ""),
    }
    values.update(overrides)
    return replace(valid_row, **values)


def test_amazon_is_normalized_validated_and_uploaded_with_canonical_label(valid_row):
    row = amazon_row(valid_row, partner="amazon")
    normalized = normalize_catalog_row(row)
    assert normalized.partner == "Amazon"
    validate_catalog_row(row)
    assert editable_payload(row)["Plataforma"] == "Amazon"


def test_amazon_is_inferred_from_direct_and_short_hosts(valid_row):
    assert infer_partner("https://www.amazon.com.br/dp/B0D123ABCD") == "Amazon"
    assert infer_partner("https://amzn.to/4abcXYZ") == "Amazon"
    assert infer_partner("https://link.amazon/B0iTSeEgH") == "Amazon"

    direct = normalize_catalog_row(amazon_row(valid_row, partner=""))
    assert direct.partner == "Amazon"

    short = normalize_catalog_row(
        amazon_row(
            valid_row,
            partner="",
            product_url="https://amzn.to/4abcXYZ",
            affiliate_url="https://amzn.to/4abcXYZ",
        )
    )
    assert short.partner == "Amazon"


def test_amazon_host_inference_rejects_lookalike_domain():
    assert infer_partner("https://amazon.com.br.evil.example/dp/B0D123ABCD") == ""
    assert infer_partner("https://link.amazon.evil.example/B0iTSeEgH") == ""
    assert infer_partner("https://evil-link.amazon.example/B0iTSeEgH") == ""
