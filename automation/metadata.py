"""Extração offline de metadados públicos de páginas de produto."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from .config import DESCRIPTION_LIMIT, IMAGE_LIMIT, normalize_unicode_text
from .models import InvalidProductDataError


@dataclass(frozen=True, slots=True)
class ExtractedProductData:
    name: str
    description: str
    current_price: Decimal
    previous_price: Decimal | None
    currency: str
    images: tuple[str, ...]
    coupon: None
    source_category: str | None
    available: bool | None


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jsonld_blocks: list[str] = []
        self.metas: list[tuple[str, str]] = []
        self._jsonld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.casefold(): value for name, value in attrs}
        if tag.casefold() == "script":
            media_type = (attributes.get("type") or "").split(";", 1)[0].strip().casefold()
            if media_type == "application/ld+json":
                self._jsonld_parts = []
        elif tag.casefold() == "meta":
            key = attributes.get("property") or attributes.get("name")
            content = attributes.get("content")
            if key and content is not None:
                self.metas.append((key.casefold(), content))

    def handle_data(self, data: str) -> None:
        if self._jsonld_parts is not None:
            self._jsonld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._jsonld_parts is not None:
            self.jsonld_blocks.append("".join(self._jsonld_parts))
            self._jsonld_parts = None


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def clean_text(value: object | None) -> str:
    """Strip markup and executable content, then bound user-visible text."""
    parser = _TextParser()
    parser.feed("" if value is None else str(value))
    parser.close()
    return normalize_unicode_text(" ".join(parser.parts))[:DESCRIPTION_LIMIT]


def parse_decimal(value: object | None) -> Decimal | None:
    """Parse common public price formats without ever performing float arithmetic."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    text = normalize_unicode_text(value)
    numeric = re.sub(r"[^0-9,\.\-+]", "", text)
    if not numeric or numeric in {"+", "-"}:
        return None
    if numeric.count("+") + numeric.count("-") > 1 or ("+" in numeric[1:] or "-" in numeric[1:]):
        return None

    commas = [index for index, character in enumerate(numeric) if character == ","]
    dots = [index for index, character in enumerate(numeric) if character == "."]
    if commas and dots:
        decimal_separator = "," if commas[-1] > dots[-1] else "."
        grouping_separator = "." if decimal_separator == "," else ","
        numeric = numeric.replace(grouping_separator, "").replace(decimal_separator, ".")
    elif commas:
        numeric = _normalize_single_separator(numeric, ",")
    elif dots:
        numeric = _normalize_single_separator(numeric, ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", numeric):
        return None
    try:
        parsed = Decimal(numeric)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _normalize_single_separator(value: str, separator: str) -> str:
    positions = [index for index, character in enumerate(value) if character == separator]
    trailing_digits = len(value) - positions[-1] - 1
    if trailing_digits in {1, 2}:
        return value.replace(separator, "", len(positions) - 1).replace(separator, ".", 1)
    return value.replace(separator, "")


def unique_https_images(images: Iterable[object]) -> tuple[str, ...]:
    """Return at most four usable public image URLs without downloading anything."""
    accepted: list[str] = []
    seen: set[str] = set()
    for candidate in images:
        url, width, height, context = _image_details(candidate)
        normalized = _normalize_https_image_url(url)
        if normalized is None or _looks_like_non_product_image(f"{normalized} {context}"):
            continue
        if width is not None and height is not None and (width < 120 or height < 120):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        accepted.append(normalized)
        if len(accepted) == IMAGE_LIMIT:
            break
    return tuple(accepted)


def _image_details(candidate: object) -> tuple[object | None, int | None, int | None, str]:
    if isinstance(candidate, Mapping):
        url = candidate.get("url") or candidate.get("contentUrl") or candidate.get("@id")
        width = _dimension(candidate.get("width"))
        height = _dimension(candidate.get("height"))
        context = " ".join(
            str(candidate.get(key, "")) for key in ("name", "alt", "caption", "description")
        )
        return url, width, height, context
    return candidate, None, None, ""


def _dimension(value: object | None) -> int | None:
    parsed = parse_decimal(value)
    if parsed is None or parsed < 0 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def _normalize_https_image_url(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme.casefold() != "https" or not parsed.netloc:
        return None
    return urlunsplit(("https", parsed.netloc.casefold(), parsed.path or "/", parsed.query, ""))


def _looks_like_non_product_image(value: str) -> bool:
    return bool(re.search(r"(?:logo|icon|sprite|tracking|pixel|beacon|spacer|analytics)", value, re.I))


def extract_product_metadata(html: str, source_url: str) -> ExtractedProductData:
    """Extract a Product/Offer pair, falling back to public Open Graph metadata."""
    del source_url  # Extraction is offline; the connector owns URL fetching and validation.
    parser = _MetadataParser()
    parser.feed(html)
    parser.close()
    for product in _jsonld_products(parser.jsonld_blocks):
        result = _extract_jsonld_product(product, parser.metas)
        if result is not None:
            return result
    return _extract_open_graph(parser.metas)


def _jsonld_products(blocks: Iterable[str]) -> Iterable[Mapping[str, Any]]:
    for block in blocks:
        try:
            parsed = json.loads(block)
        except (TypeError, json.JSONDecodeError):
            continue
        for node in _walk_json(parsed):
            if _has_type(node, "product"):
                yield node


def _walk_json(value: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _has_type(value: Mapping[str, Any], expected: str) -> bool:
    raw_type = value.get("@type")
    types = raw_type if isinstance(raw_type, list) else (raw_type,)
    return any(
        isinstance(item, str)
        and item.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1].casefold() == expected
        for item in types
    )


def _extract_jsonld_product(
    product: Mapping[str, Any], metas: list[tuple[str, str]]
) -> ExtractedProductData | None:
    name = clean_text(product.get("name"))
    if not name:
        return None
    for offer in _offer_nodes(product.get("offers")):
        offer_data = _offer_data(offer)
        if offer_data is None:
            continue
        current, previous, currency, available = offer_data
        description = clean_text(product.get("description")) or _meta_value(metas, "og:description", "description")
        images = unique_https_images(_product_images(product.get("image")) + _og_images(metas))
        category = clean_text(product.get("category")) or None
        return ExtractedProductData(
            name=name,
            description=description,
            current_price=current,
            previous_price=previous,
            currency=currency,
            images=images,
            coupon=None,
            source_category=category,
            available=available,
        )
    return None


def _offer_nodes(value: object) -> Iterable[Mapping[str, Any]]:
    for node in _walk_json(value):
        if _has_type(node, "offer"):
            yield node


def _offer_data(offer: Mapping[str, Any]) -> tuple[Decimal, Decimal | None, str, bool | None] | None:
    direct_values = [parse_decimal(offer.get(key)) for key in ("price", "lowPrice")]
    direct_current = next((value for value in direct_values if value is not None and value > 0), None)
    specifications = list(_walk_json(offer.get("priceSpecification")))
    specification_prices = [
        parse_decimal(specification.get(key))
        for specification in specifications
        for key in ("price", "lowPrice")
    ]
    current = direct_current or next(
        (value for value in specification_prices if value is not None and value > 0), None
    )
    if current is None:
        return None
    possible_previous = [parse_decimal(offer.get("highPrice"))]
    possible_previous.extend(
        parse_decimal(specification.get(key))
        for specification in specifications
        for key in ("highPrice", "price", "lowPrice")
    )
    previous_values = [value for value in possible_previous if value is not None and value > current]
    previous = max(previous_values) if previous_values else None
    currency = clean_text(offer.get("priceCurrency"))
    if not currency:
        for specification in specifications:
            currency = clean_text(specification.get("priceCurrency"))
            if currency:
                break
    availability = _availability(offer.get("availability"))
    return current, previous, currency, availability


def _availability(value: object | None) -> bool | None:
    if not isinstance(value, str):
        return None
    normalized = value.casefold()
    if "instock" in normalized or "in stock" in normalized:
        return True
    if "outofstock" in normalized or "out of stock" in normalized:
        return False
    return None


def _product_images(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]


def _meta_value(metas: Iterable[tuple[str, str]], *keys: str) -> str:
    wanted = set(keys)
    for key, value in metas:
        if key in wanted and clean_text(value):
            return clean_text(value)
    return ""


def _og_images(metas: Iterable[tuple[str, str]]) -> list[object]:
    images: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for key, value in metas:
        if key == "og:image":
            current = {"url": value}
            images.append(current)
        elif current is not None and key == "og:image:width":
            current["width"] = value
        elif current is not None and key == "og:image:height":
            current["height"] = value
    return images


def _extract_open_graph(metas: list[tuple[str, str]]) -> ExtractedProductData:
    name = _meta_value(metas, "og:title", "twitter:title", "title")
    current = _first_price(metas, "product:price:amount", "og:price:amount", "price:amount")
    if not name or current is None or current <= 0:
        raise InvalidProductDataError("Metadados públicos não contêm produto com preço válido.")
    previous = _first_price(
        metas, "product:price:original_amount", "product:price:high_amount", "og:price:original_amount"
    )
    if previous is not None and previous <= current:
        previous = None
    return ExtractedProductData(
        name=name,
        description=_meta_value(metas, "og:description", "description"),
        current_price=current,
        previous_price=previous,
        currency=_meta_value(metas, "product:price:currency", "og:price:currency"),
        images=unique_https_images(_og_images(metas)),
        coupon=None,
        source_category=_meta_value(metas, "product:category", "og:product:category") or None,
        available=_availability(_meta_value(metas, "product:availability", "og:availability")),
    )


def _first_price(metas: Iterable[tuple[str, str]], *keys: str) -> Decimal | None:
    wanted = set(keys)
    for key, value in metas:
        if key in wanted:
            parsed = parse_decimal(value)
            if parsed is not None:
                return parsed
    return None
