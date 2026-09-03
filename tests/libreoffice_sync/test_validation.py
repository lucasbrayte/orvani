from dataclasses import replace
from decimal import Decimal

import pytest

from libreoffice_sync.validation import LocalValidationError, validate_catalog_row


@pytest.mark.parametrize("field", ["name", "description", "category", "subcategory", "product_type"])
def test_required_manual_text(field, valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(replace(valid_row, **{field: ""}))


def test_previous_price_must_exceed_current(valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(
            replace(
                valid_row,
                current_price=Decimal("200.00"),
                previous_price=Decimal("199.00"),
            )
        )


def test_manual_published_row_requires_image(valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(replace(valid_row, images=("", "", "", "")))


def test_https_is_required_for_nonempty_urls(valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(replace(valid_row, affiliate_url="http://meli.la/teste"))


def test_valid_manual_row_passes(valid_row):
    validate_catalog_row(valid_row)
