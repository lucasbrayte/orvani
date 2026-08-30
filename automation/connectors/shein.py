"""Conector SHEIN limitado a metadados públicos e fixtures sanitizadas."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from ..config import PartnerConfig
from ..http_client import SafeHttpClient
from ..metadata import ExtractedProductData, extract_product_metadata
from ..models import InvalidProductDataError, ProductSnapshot, UnsupportedUrlError
from ..security import validate_https_url
from .base import (
    MetadataConnectorBase,
    _HTML_CONTENT_TYPES,
    snapshot_from_metadata,
    validate_required_metadata,
)


_PRODUCT_PATH = re.compile(r"(?:^|/)product-p-(?P<product>\d{1,15})\.html(?:$|/)", re.I)
_IDENTITY_KEYS = frozenset({"sku", "productid", "mpn", "@id", "url"})
_Clock = Callable[[], datetime]


def extract_shein_product_id(value: object) -> str | None:
    """Extract one bounded product ID only from a page path, never query or text."""
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    path = parsed.path if parsed.scheme or parsed.netloc or value.startswith("/") else ""
    match = _PRODUCT_PATH.search(path)
    if match is None:
        return None
    product_id = match.group("product")
    return None if set(product_id) == {"0"} else product_id


class _IdentityParser(HTMLParser):
    """Collect canonical URLs and JSON-LD only; visible page text cannot identify a product."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonicals: list[str] = []
        self.jsonld_blocks: list[str] = []
        self._jsonld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.casefold(): value for key, value in attrs}
        if tag.casefold() == "link":
            rel = (attributes.get("rel") or "").casefold().split()
            href = attributes.get("href")
            if "canonical" in rel and href:
                self.canonicals.append(href)
        elif tag.casefold() == "script":
            media_type = (attributes.get("type") or "").split(";", 1)[0].strip().casefold()
            if media_type == "application/ld+json":
                self._jsonld_parts = []

    def handle_data(self, data: str) -> None:
        if self._jsonld_parts is not None:
            self._jsonld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script" and self._jsonld_parts is not None:
            self.jsonld_blocks.append("".join(self._jsonld_parts))
            self._jsonld_parts = None


class SheinConnector(MetadataConnectorBase):
    """Build snapshots from a single public SHEIN HTML response.

    ``live_verified`` deliberately mirrors configuration and remains false: the
    local fixture establishes only the parser contract, not production support.
    """

    product_type = ""

    def __init__(
        self,
        http_client: SafeHttpClient,
        partner: PartnerConfig,
        *,
        metadata_extractor: Callable[[str, str], ExtractedProductData] = extract_product_metadata,
        clock: _Clock | None = None,
    ) -> None:
        super().__init__(http_client, partner, metadata_extractor=metadata_extractor, clock=clock)

    @property
    def live_verified(self) -> bool:
        return self._partner.live_verified

    def fetch(self, affiliate_url: str) -> ProductSnapshot:
        """Fetch public metadata once and retain the literal affiliate URL for publication."""
        if not self.supports(affiliate_url):
            raise UnsupportedUrlError("URL incompatível com o conector selecionado.")
        response = self._http_client.get(affiliate_url, self.allowed_hosts, _HTML_CONTENT_TYPES)
        try:
            validate_https_url(response.url, self.allowed_hosts)
        except Exception as error:
            raise InvalidProductDataError("A página terminal SHEIN não é confiável.") from error
        html = response.body.decode("utf-8", errors="replace")
        external_id = self._trusted_product_id(response.url, html)
        if external_id is None:
            raise InvalidProductDataError("O produto não tem um ID externo válido.")
        metadata = self._metadata_extractor(html, response.url)
        metadata = validate_required_metadata(metadata)
        return snapshot_from_metadata(
            partner_key=self.partner_key,
            external_id=external_id,
            catalog_id=None,
            source_url=response.url,
            affiliate_url=affiliate_url,
            metadata=metadata,
            fetched_at=self._clock(),
            product_type=self.product_type,
        )

    def _trusted_product_id(self, source_url: str, html: str) -> str | None:
        direct = extract_shein_product_id(source_url)
        if direct is not None:
            return direct
        parser = _IdentityParser()
        parser.feed(html)
        parser.close()
        canonical_urls = tuple(
            candidate
            for canonical in parser.canonicals
            if _is_trusted_page_url(candidate := urljoin(source_url, canonical), self.allowed_hosts)
        )
        for canonical in canonical_urls:
            product_id = extract_shein_product_id(canonical)
            if product_id is not None:
                return product_id
        for block in parser.jsonld_blocks:
            try:
                document = json.loads(block)
            except (TypeError, json.JSONDecodeError):
                continue
            product_id, has_designated_main = _main_product_id(
                document, source_url, canonical_urls, self.allowed_hosts
            )
            if product_id is not None:
                return product_id
            if has_designated_main:
                return None
        return None


def _is_trusted_page_url(value: str, allowed_hosts: tuple[str, ...]) -> bool:
    try:
        validate_https_url(value, allowed_hosts)
    except Exception:
        return False
    return True


def _main_product_id(
    document: object,
    source_url: str,
    canonical_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> tuple[str | None, bool]:
    nodes = _top_level_nodes(document)
    index = {
        identifier: node
        for node in nodes
        if isinstance((identifier := node.get("@id")), str)
    }
    page_urls = (source_url, *canonical_urls)
    for product, designated in _main_products(nodes, index, page_urls, allowed_hosts):
        if not _product_belongs_to_page(product, designated, page_urls, allowed_hosts):
            continue
        product_id = _structured_product_id(product, allowed_hosts)
        if product_id is not None:
            return product_id, designated
    return None, _has_designated_main_page(nodes, page_urls, allowed_hosts)


def _top_level_nodes(document: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(document, list):
        return tuple(node for node in document if isinstance(node, Mapping))
    if not isinstance(document, Mapping):
        return ()
    graph = document.get("@graph")
    return (document, *(node for node in graph if isinstance(node, Mapping))) if isinstance(graph, list) else (document,)


def _has_type(value: Mapping[str, object], expected: str) -> bool:
    raw_type = value.get("@type")
    values = raw_type if isinstance(raw_type, list) else (raw_type,)
    return any(
        isinstance(item, str)
        and item.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1].casefold() == expected
        for item in values
    )


def _main_products(
    nodes: tuple[Mapping[str, object], ...],
    index: Mapping[str, Mapping[str, object]],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
):
    found_webpage = False
    for webpage in (node for node in nodes if _has_type(node, "webpage") and "mainEntity" in node):
        found_webpage = True
        if not _webpage_belongs_to_page(webpage, page_urls, allowed_hosts):
            continue
        values = webpage["mainEntity"]
        for candidate in values if isinstance(values, list) else (values,):
            product = _resolve_node(candidate, index)
            if product is not None and _has_type(product, "product"):
                yield product, True
    if found_webpage:
        return
    for product in (node for node in nodes if _has_type(node, "product")):
        yield product, False


def _has_designated_main_page(
    nodes: tuple[Mapping[str, object], ...],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> bool:
    return any(
        _has_type(node, "webpage")
        and "mainEntity" in node
        and _webpage_belongs_to_page(node, page_urls, allowed_hosts)
        for node in nodes
    )


def _webpage_belongs_to_page(
    webpage: Mapping[str, object], page_urls: tuple[str, ...], allowed_hosts: tuple[str, ...]
) -> bool:
    references = tuple(
        reference
        for value in (webpage.get("@id"), webpage.get("url"))
        if (reference := _reference_url(value)) is not None
    )
    return not references or all(
        _reference_matches_page(reference, page_urls, allowed_hosts) for reference in references
    )


def _resolve_node(
    value: object, index: Mapping[str, Mapping[str, object]]
) -> Mapping[str, object] | None:
    if isinstance(value, str):
        return index.get(value)
    if not isinstance(value, Mapping):
        return None
    identifier = value.get("@id")
    return index[identifier] if isinstance(identifier, str) and identifier in index else value


def _product_belongs_to_page(
    product: Mapping[str, object],
    designated: bool,
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> bool:
    references = tuple(
        reference
        for value in (product.get("mainEntityOfPage"), product.get("url"), product.get("@id"))
        if (reference := _reference_url(value)) is not None
    )
    absolute_references = tuple(reference for reference in references if not reference.startswith("#"))
    return designated if not absolute_references else all(
        _reference_matches_page(reference, page_urls, allowed_hosts)
        for reference in absolute_references
    )


def _reference_url(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        reference = value.get("@id") or value.get("url")
        return reference if isinstance(reference, str) else None
    return None


def _reference_matches_page(
    value: object, page_urls: tuple[str, ...], allowed_hosts: tuple[str, ...]
) -> bool:
    if not isinstance(value, str) or not _is_trusted_page_url(value, allowed_hosts):
        return False
    candidate = _page_key(value)
    return any(candidate == _page_key(page_url) for page_url in page_urls)


def _page_key(url: str) -> tuple[str, str, str]:
    parsed = urlsplit(url)
    return (parsed.scheme.casefold(), (parsed.hostname or "").casefold(), parsed.path.rstrip("/") or "/")


def _structured_product_id(product: Mapping[str, object], allowed_hosts: tuple[str, ...]) -> str | None:
    for key, value in product.items():
        if not isinstance(key, str) or key.casefold() not in _IDENTITY_KEYS:
            continue
        if key.casefold() in {"sku", "productid", "mpn"}:
            if isinstance(value, str) and value.isascii() and value.isdigit() and 1 <= len(value) <= 15 and set(value) != {"0"}:
                return value
            continue
        if isinstance(value, str) and _is_trusted_page_url(value, allowed_hosts):
            product_id = extract_shein_product_id(value)
            if product_id is not None:
                return product_id
    return None
