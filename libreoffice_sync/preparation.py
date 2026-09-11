from __future__ import annotations

from dataclasses import replace

from .affiliate_urls import compose_affiliate_url
from .models import CatalogRow
from .normalization import normalize_catalog_row


def prepare_catalog_row(row: CatalogRow) -> CatalogRow:
    normalized = normalize_catalog_row(row)
    effective_affiliate_url = compose_affiliate_url(
        normalized.product_url,
        normalized.affiliate_url,
        normalized.partner,
    )
    return replace(
        normalized,
        affiliate_url=effective_affiliate_url,
    )
