"""Categorização pública, pequena e determinística."""

from __future__ import annotations

from dataclasses import dataclass

from .config import (
    CATEGORY_FIRST_SEGMENTS,
    CATEGORY_KEYWORDS,
    CATEGORY_SOURCE_MAPPINGS,
    normalize_category_key,
)


@dataclass(frozen=True, slots=True)
class CategoryDecision:
    category: str
    subcategory: str | None
    confident: bool


def categorize(
    source_category: str | None,
    product_name: str | None,
    description: str | None,
) -> CategoryDecision:
    """Apply official source data before conservative keyword matching."""
    source_key = normalize_category_key(source_category)
    source_mapping = CATEGORY_SOURCE_MAPPINGS.get(source_key)
    if source_mapping is not None:
        return CategoryDecision(*source_mapping, True)

    first_segment = source_key.split(">", 1)[0].strip()
    known_category = CATEGORY_FIRST_SEGMENTS.get(first_segment)
    if known_category is not None:
        return CategoryDecision(known_category, None, True)

    searchable = " ".join((
        normalize_category_key(product_name),
        normalize_category_key(description),
    ))
    for keyword, category, subcategory in CATEGORY_KEYWORDS:
        if normalize_category_key(keyword) in searchable:
            return CategoryDecision(category, subcategory, True)
    return CategoryDecision("Outros", None, False)
