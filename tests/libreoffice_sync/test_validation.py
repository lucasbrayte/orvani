from dataclasses import replace
from decimal import Decimal

import pytest

from libreoffice_sync.validation import LocalValidationError, validate_catalog_row


def test_only_core_fields_are_required_locally(valid_row):
    validate_catalog_row(
        replace(
            valid_row,
            update_mode="",
            partner="",
            name="",
            description="",
            category="",
            subcategory="",
            product_type="",
            current_price=None,
            previous_price=None,
            images=("", "", "", ""),
            button_text="",
            product_url="https://shopee.com.br/produto-i.123.456",
            affiliate_url="https://s.shopee.com.br/abc123",
        )
    )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("product_url", "Link Produto"),
        ("affiliate_url", "Link Afiliado"),
    ],
)
def test_both_links_are_required(valid_row, field, message):
    with pytest.raises(LocalValidationError, match=message):
        validate_catalog_row(replace(valid_row, **{field: ""}))


def test_lowercase_choice_values_are_accepted(valid_row):
    validate_catalog_row(
        replace(
            valid_row,
            active="sim",
            publish="SIM",
            featured="não",
            update_mode="automatico",
            partner="shopee",
        )
    )


def test_previous_price_must_exceed_current(valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(
            replace(
                valid_row,
                current_price=Decimal("200.00"),
                previous_price=Decimal("199.00"),
            )
        )


def test_https_is_required_for_nonempty_urls(valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(
            replace(valid_row, affiliate_url="http://meli.la/teste")
        )


def test_valid_manual_row_passes(valid_row):
    validate_catalog_row(valid_row)
