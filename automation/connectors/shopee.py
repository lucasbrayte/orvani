"""Conector Shopee de metadados públicos e fila manual de conversão."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from ..config import PartnerConfig
from ..http_client import SafeHttpClient
from ..metadata import ExtractedProductData, extract_product_metadata
from ..models import ImportRecord, ImportStatus, InvalidProductDataError, ProductSnapshot, UnsupportedUrlError
from ..security import validate_https_url
from .base import _HTML_CONTENT_TYPES, snapshot_from_metadata


_ITEM_ID_IN_PATH = re.compile(
    r"(?:^|[-_/])i\.(?P<shop>[1-9]\d{0,14})\.(?P<item>[1-9]\d{0,14})(?=$|[-_/.])",
    re.IGNORECASE,
)
_PRODUCT_PATH = re.compile(
    r"(?:^|/)product/(?P<shop>[1-9]\d{0,14})/(?P<item>[1-9]\d{0,14})(?:/|$)",
    re.IGNORECASE,
)
_EXACT_ITEM_ID = re.compile(r"[1-9]\d{0,14}\.[1-9]\d{0,14}\Z")
_IDENTITY_KEYS = frozenset({"sku", "productid", "mpn", "@id", "url"})
_Clock = Callable[[], datetime]


def extract_shopee_item_id(value: object) -> str | None:
    """Extract a bounded Shopee identity from a URL or page path, never query/text."""
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    path = parsed.path if parsed.scheme or parsed.netloc or value.startswith("/") else ""
    for pattern in (_ITEM_ID_IN_PATH, _PRODUCT_PATH):
        match = pattern.search(path)
        if match is not None:
            return f"{match.group('shop')}.{match.group('item')}"
    return None


class _IdentityParser(HTMLParser):
    """Collect only canonical URLs and JSON-LD blocks; visible text is never identity."""

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


class ShopeeConnector:
    """Build snapshots from one public Shopee HTML response only."""

    product_type = ""

    def __init__(
        self,
        http_client: SafeHttpClient,
        partner: PartnerConfig,
        *,
        metadata_extractor: Callable[[str, str], ExtractedProductData] = extract_product_metadata,
        clock: _Clock | None = None,
    ) -> None:
        self._http_client = http_client
        self._partner = partner
        self._metadata_extractor = metadata_extractor
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def partner_key(self) -> str:
        return self._partner.key

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        return self._partner.allowed_hosts

    def supports(self, url: str) -> bool:
        try:
            validate_https_url(url, self.allowed_hosts)
        except Exception:
            return False
        return True

    def fetch(self, affiliate_url: str) -> ProductSnapshot:
        """Resolve a public page through SafeHttpClient and retain the literal input URL."""
        if not self.supports(affiliate_url):
            raise UnsupportedUrlError("URL incompatível com o conector selecionado.")
        response = self._http_client.get(affiliate_url, self.allowed_hosts, _HTML_CONTENT_TYPES)
        try:
            validate_https_url(response.url, self.allowed_hosts)
        except Exception as error:
            raise InvalidProductDataError("A página terminal Shopee não é confiável.") from error
        html = response.body.decode("utf-8", errors="replace")
        external_id = self._trusted_item_id(response.url, html)
        if external_id is None:
            raise InvalidProductDataError("O produto não tem um ID externo válido.")
        metadata = self._metadata_extractor(html, response.url)
        if not isinstance(metadata, ExtractedProductData):
            raise InvalidProductDataError("O conector retornou metadados inválidos.")
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

    def _trusted_item_id(self, source_url: str, html: str) -> str | None:
        direct = extract_shopee_item_id(source_url)
        if direct is not None:
            return direct
        parser = _IdentityParser()
        parser.feed(html)
        parser.close()
        canonical_urls: list[str] = []
        for canonical in parser.canonicals:
            candidate = urljoin(source_url, canonical)
            if not _is_trusted_page_url(candidate, self.allowed_hosts):
                continue
            canonical_urls.append(candidate)
            item_id = extract_shopee_item_id(candidate)
            if item_id is not None:
                return item_id
        for block in parser.jsonld_blocks:
            try:
                document = json.loads(block)
            except (TypeError, json.JSONDecodeError):
                continue
            item_id = _jsonld_main_product_id(
                document, source_url, tuple(canonical_urls), self.allowed_hosts
            )
            if item_id is not None:
                return item_id
        return None


def build_conversion_batches(
    records: Iterable[ImportRecord], batch_size: int = 5
) -> tuple[tuple[ImportRecord, ...], ...]:
    """Return immutable, sheet-ordered manual Shopee conversion batches.

    The source records are never changed.  Eligible records are copied with the
    waiting status and their assigned human-facing batch message.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int):
        raise TypeError("batch_size deve ser um inteiro positivo.")
    if batch_size <= 0:
        raise ValueError("batch_size deve ser um inteiro positivo.")

    selected: list[ImportRecord] = []
    for record in records:
        if not isinstance(record, ImportRecord):
            raise TypeError("records deve conter apenas ImportRecord.")
        if _is_conversion_candidate(record):
            selected.append(record)

    batches: list[tuple[ImportRecord, ...]] = []
    for start in range(0, len(selected), batch_size):
        number = len(batches) + 1
        message = f"Lote Shopee {number:02d} — máximo {batch_size} links"
        batches.append(
            tuple(
                replace(
                    record,
                    status=ImportStatus.AGUARDANDO_CONVERSAO,
                    message=message,
                )
                for record in selected[start : start + batch_size]
            )
        )
    return tuple(batches)


def _is_conversion_candidate(record: ImportRecord) -> bool:
    return (
        record.active == "Sim"
        and isinstance(record.product_url, str)
        and bool(record.product_url.strip())
        and isinstance(record.affiliate_url, str)
        and not record.affiliate_url.strip()
        and record.status in (ImportStatus.NOVO, ImportStatus.AGUARDANDO_CONVERSAO)
    )


def _is_trusted_page_url(value: str, allowed_hosts: tuple[str, ...]) -> bool:
    try:
        validate_https_url(value, allowed_hosts)
    except Exception:
        return False
    return True


def _jsonld_main_product_id(
    document: object,
    source_url: str,
    canonical_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> str | None:
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
        for key, value in product.items():
            if isinstance(key, str) and key.casefold() in _IDENTITY_KEYS:
                item_id = _structured_item_id(key, value, allowed_hosts)
                if item_id is not None:
                    return item_id
    return None


def _top_level_nodes(document: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(document, list):
        return tuple(node for node in document if isinstance(node, Mapping))
    if not isinstance(document, Mapping):
        return ()
    graph = document.get("@graph")
    graph_nodes = graph if isinstance(graph, list) else ()
    return (document, *(node for node in graph_nodes if isinstance(node, Mapping)))


def _main_products(
    nodes: tuple[Mapping[str, object], ...],
    index: Mapping[str, Mapping[str, object]],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> Iterable[tuple[Mapping[str, object], bool]]:
    webpage_nodes = (node for node in nodes if _has_type(node, "webpage") and "mainEntity" in node)
    found_webpage = False
    for webpage in webpage_nodes:
        found_webpage = True
        if not _webpage_belongs_to_page(webpage, page_urls, allowed_hosts):
            continue
        value = webpage.get("mainEntity")
        candidates = value if isinstance(value, list) else (value,)
        for candidate in candidates:
            product = _resolve_node(candidate, index)
            if product is not None and _has_type(product, "product"):
                yield product, True
    if found_webpage:
        return
    for product in (node for node in nodes if _has_type(node, "product")):
        yield product, False


def _webpage_belongs_to_page(
    webpage: Mapping[str, object],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> bool:
    references = tuple(
        reference
        for value in (webpage.get("@id"), webpage.get("url"))
        if (reference := _reference_url(value)) is not None
    )
    return not references or all(
        _matches_page_reference(reference, page_urls, allowed_hosts)
        for reference in references
    )


def _resolve_node(value: object, index: Mapping[str, Mapping[str, object]]) -> Mapping[str, object] | None:
    if isinstance(value, str):
        return index.get(value)
    if not isinstance(value, Mapping):
        return None
    identifier = value.get("@id")
    if isinstance(identifier, str) and identifier in index:
        return index[identifier]
    return value


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
    if not references:
        return designated
    return all(_matches_page_reference(reference, page_urls, allowed_hosts) for reference in references)


def _reference_url(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        identifier = value.get("@id") or value.get("url")
        return identifier if isinstance(identifier, str) else None
    return None


def _matches_page_reference(
    candidate: str, page_urls: tuple[str, ...], allowed_hosts: tuple[str, ...]
) -> bool:
    if candidate.startswith("#"):
        return True
    if not _is_trusted_page_url(candidate, allowed_hosts):
        return False
    candidate_key = _page_key(candidate)
    return any(candidate_key == _page_key(page_url) for page_url in page_urls)


def _page_key(url: str) -> tuple[str, str, str]:
    parsed = urlsplit(url)
    return (parsed.scheme.casefold(), (parsed.hostname or "").casefold(), parsed.path.rstrip("/") or "/")


def _has_type(value: Mapping[str, object], expected: str) -> bool:
    raw_type = value.get("@type")
    types = raw_type if isinstance(raw_type, list) else (raw_type,)
    return any(
        isinstance(item, str)
        and item.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1].casefold() == expected
        for item in types
    )


def _structured_item_id(key: str, value: object, allowed_hosts: tuple[str, ...]) -> str | None:
    if key.casefold() in {"sku", "productid", "mpn"}:
        return _exact_item_id(value)
    if not isinstance(value, str) or not _is_trusted_page_url(value, allowed_hosts):
        return None
    return extract_shopee_item_id(value)


def _exact_item_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if _EXACT_ITEM_ID.fullmatch(candidate) else None
