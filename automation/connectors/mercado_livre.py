"""Conector público e restrito para itens do Mercado Livre."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from ..config import MERCADO_LIVRE_API_ALLOWED_HOSTS, PartnerConfig
from ..http_client import SafeHttpClient
from ..metadata import (
    ExtractedProductData,
    clean_text,
    extract_product_metadata,
    parse_decimal,
    unique_https_images,
)
from ..models import (
    BlockedByStoreError,
    InvalidProductDataError,
    ProductSnapshot,
    TemporaryFetchError,
    UnexpectedContentTypeError,
    UnsupportedUrlError,
)
from ..security import validate_https_url
from .base import snapshot_from_metadata


_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_API_CONTENT_TYPES = ("application/json",)
_ITEM_ID = re.compile(r"(?<![A-Za-z0-9])MLB[-_]?(\d{6,})(?![A-Za-z0-9])", re.I)
_EXACT_ITEM_ID = re.compile(r"MLB\d{6,}\Z", re.I)
_CATALOG_ID = re.compile(r"MLB\d{4,}\Z", re.I)
_CATALOG_PATH = re.compile(r"(?:^|/)p/MLB\d{4,}(?:/|$)", re.I)
_PDP_FILTER_ITEM_ID = re.compile(r"(?:^|\|)item_id:MLB[-_]?(\d{6,})(?=\||$)", re.I)
_STRUCTURED_ID_KEYS = frozenset({"sku", "productid", "mpn", "@id", "url"})
_Clock = Callable[[], datetime]


def extract_mercado_item_id(value: object) -> str | None:
    """Normalize a bounded MLB item ID from a trusted URL shape or individual value."""
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None

    is_url = bool(parsed.scheme or parsed.netloc or value.startswith("/"))
    candidate = parsed.path if is_url else value

    if is_url and _CATALOG_PATH.search(candidate):
        try:
            query = parse_qs(
                parsed.query,
                keep_blank_values=False,
                strict_parsing=False,
                max_num_fields=20,
            )
        except ValueError:
            return None
        for raw_filters in query.get("pdp_filters", ()):
            match = _PDP_FILTER_ITEM_ID.search(raw_filters)
            if match is not None:
                return f"MLB{match.group(1)}"
        return None

    match = _ITEM_ID.search(candidate)
    if match is None:
        return None
    return f"MLB{match.group(1)}"


def extract_mercado_catalog_id(value: object) -> str | None:
    """Return a bounded catalog identifier without confusing it with an item ID."""
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper()
    return candidate if _CATALOG_ID.fullmatch(candidate) else None


class _TrustedIdParser(HTMLParser):
    """Collect canonical URLs and JSON-LD blocks, never arbitrary visible text."""

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


class MercadoLivreConnector:
    """Map public Mercado Livre HTML and documented item responses to snapshots."""

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
        """Resolve public HTML, then prefer the documented unauthenticated item API."""
        if not self.supports(affiliate_url):
            raise UnsupportedUrlError("URL incompatível com o conector selecionado.")
        response = self._http_client.get(affiliate_url, self.allowed_hosts, _HTML_CONTENT_TYPES)
        html = response.body.decode("utf-8", errors="replace")
        item_id = self._trusted_item_id(response.url, html)
        if item_id is None:
            raise InvalidProductDataError("O produto não tem um ID externo válido.")
        try:
            api_response = self._http_client.get(
                f"https://api.mercadolibre.com/items/{item_id}",
                MERCADO_LIVRE_API_ALLOWED_HOSTS,
                _API_CONTENT_TYPES,
            )
        except (BlockedByStoreError, TemporaryFetchError, UnexpectedContentTypeError):
            return self._snapshot_from_html(html, response.url, affiliate_url, item_id)
        body = api_response.body
        if type(body) is not bytes:
            raise InvalidProductDataError("A API pública retornou dados inválidos.")
        try:
            item = json.loads(body, parse_constant=_reject_json_constant)
        except (TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
            raise InvalidProductDataError("A API pública retornou dados inválidos.") from error
        if not isinstance(item, Mapping):
            raise InvalidProductDataError("A API pública retornou dados inválidos.")
        return self.snapshot_from_api(item, affiliate_url, response.url, expected_item_id=item_id)

    def snapshot_from_api(
        self,
        item: object,
        affiliate_url: str,
        source_url: str,
        *,
        expected_item_id: str | None = None,
    ) -> ProductSnapshot:
        """Map one documented ``/items/{ID}`` object without any extra API calls."""
        if not isinstance(item, Mapping):
            raise InvalidProductDataError("A API pública retornou dados inválidos.")
        external_id = _exact_item_id(item.get("id"))
        if external_id is None or (expected_item_id is not None and external_id != expected_item_id):
            raise InvalidProductDataError("O produto não tem um ID externo válido.")
        catalog_id = extract_mercado_catalog_id(item.get("catalog_product_id"))
        if item.get("catalog_product_id") is not None and catalog_id is None:
            raise InvalidProductDataError("O produto tem um ID de catálogo inválido.")
        current_price = parse_decimal(item.get("price"))
        if current_price is None or current_price <= 0:
            raise InvalidProductDataError("O produto não tem um preço atual válido.")
        raw_previous = parse_decimal(item.get("original_price"))
        previous_price = raw_previous if raw_previous is not None and raw_previous > current_price else None
        currency = item.get("currency_id")
        title = clean_text(item.get("title"))
        status = item.get("status")
        if not isinstance(currency, str) or not currency.strip() or not title or not isinstance(status, str):
            raise InvalidProductDataError("A API pública não contém os dados obrigatórios do produto.")
        metadata = ExtractedProductData(
            name=title,
            description=clean_text(item.get("subtitle")),
            current_price=current_price,
            previous_price=previous_price,
            currency=currency.strip().upper(),
            images=unique_https_images(_picture_urls(item.get("pictures"))),
            coupon=None,
            source_category=_clean_category(item.get("category_id")),
            available=status.casefold() == "active",
        )
        return snapshot_from_metadata(
            partner_key=self.partner_key,
            external_id=external_id,
            catalog_id=catalog_id,
            source_url=source_url,
            affiliate_url=affiliate_url,
            metadata=metadata,
            fetched_at=self._clock(),
        )

    def _snapshot_from_html(
        self,
        html: str,
        source_url: str,
        affiliate_url: str,
        item_id: str,
    ) -> ProductSnapshot:
        metadata = self._metadata_extractor(html, source_url)
        if not isinstance(metadata, ExtractedProductData):
            raise InvalidProductDataError("O conector retornou metadados inválidos.")
        return snapshot_from_metadata(
            partner_key=self.partner_key,
            external_id=item_id,
            catalog_id=None,
            source_url=source_url,
            affiliate_url=affiliate_url,
            metadata=metadata,
            fetched_at=self._clock(),
        )

    def _trusted_item_id(self, source_url: str, html: str) -> str | None:
        direct = extract_mercado_item_id(source_url)
        if direct is not None:
            return direct
        parser = _TrustedIdParser()
        parser.feed(html)
        parser.close()
        valid_canonicals: list[str] = []
        for canonical in parser.canonicals:
            if not self._is_trusted_page_url(canonical):
                continue
            valid_canonicals.append(canonical)
            item_id = self._trusted_canonical_item_id(canonical)
            if item_id is not None:
                return item_id
        for block in parser.jsonld_blocks:
            try:
                document = json.loads(block)
            except json.JSONDecodeError:
                continue
            item_id = _structured_item_id(
                document,
                self.allowed_hosts,
                source_url,
                valid_canonicals,
            )
            if item_id is not None:
                return item_id
        return None

    def _trusted_canonical_item_id(self, canonical: str) -> str | None:
        if not self._is_trusted_page_url(canonical):
            return None
        return extract_mercado_item_id(canonical)

    def _is_trusted_page_url(self, value: str) -> bool:
        try:
            validate_https_url(value, self.allowed_hosts)
        except Exception:
            return False
        return True


def _structured_item_id(
    document: object,
    allowed_hosts: tuple[str, ...],
    source_url: str,
    canonical_urls: Iterable[str],
) -> str | None:
    """Read identity fields only from a Product selected as this page's main entity."""
    page_urls = (source_url, *canonical_urls)
    top_nodes = _top_level_nodes(document)
    index = _top_level_id_index(top_nodes)
    for product in _designated_products(top_nodes, index, page_urls, allowed_hosts):
        for key, candidate in product.items():
            if isinstance(key, str) and key.casefold() in _STRUCTURED_ID_KEYS:
                item_id = _structured_candidate_item_id(key, candidate, allowed_hosts)
                if item_id is not None:
                    return item_id
    return None


def _top_level_nodes(document: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(document, list):
        return tuple(node for node in document if isinstance(node, Mapping))
    if not isinstance(document, Mapping):
        return ()
    nodes: list[Mapping[str, object]] = [document]
    graph = document.get("@graph")
    if isinstance(graph, list):
        nodes.extend(node for node in graph if isinstance(node, Mapping))
    return tuple(nodes)


def _top_level_id_index(
    nodes: Iterable[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    return {
        identifier: node
        for node in nodes
        if isinstance((identifier := node.get("@id")), str)
    }


def _designated_products(
    nodes: tuple[Mapping[str, object], ...],
    index: Mapping[str, Mapping[str, object]],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> Iterable[Mapping[str, object]]:
    webpage_nodes = tuple(
        node for node in nodes if _has_type(node, "webpage") and "mainEntity" in node
    )
    if webpage_nodes:
        for webpage in webpage_nodes:
            if not _node_belongs_to_page(webpage, page_urls, allowed_hosts):
                continue
            for product in _resolved_products(webpage.get("mainEntity"), index):
                if _product_belongs_to_page(product, page_urls, allowed_hosts, designated=True):
                    yield product
        return
    document = nodes[0] if nodes else None
    if isinstance(document, Mapping) and _has_type(document, "product"):
        if _product_belongs_to_page(document, page_urls, allowed_hosts, designated=False):
            yield document
        return
    for product in (node for node in nodes[1:] if _has_type(node, "product")):
        if _product_belongs_to_page(product, page_urls, allowed_hosts, designated=False):
            yield product


def _node_belongs_to_page(
    node: Mapping[str, object],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> bool:
    references = tuple(
        reference
        for value in (node.get("@id"), node.get("url"))
        if (reference := _reference_url(value)) is not None
    )
    return not references or all(
        _matches_page_reference(reference, page_urls, allowed_hosts)
        for reference in references
    )


def _product_belongs_to_page(
    product: Mapping[str, object],
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
    *,
    designated: bool,
) -> bool:
    references = tuple(
        reference
        for value in (
            product.get("mainEntityOfPage"),
            product.get("url"),
            product.get("@id"),
        )
        if (reference := _reference_url(value)) is not None
    )
    if references:
        return all(
            _matches_page_reference(reference, page_urls, allowed_hosts)
            for reference in references
        )
    return designated


def _matches_page_reference(
    candidate: str,
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> bool:
    if candidate.startswith("#"):
        return True
    return _matches_page_url(candidate, page_urls, allowed_hosts)


def _resolved_products(
    value: object,
    index: Mapping[str, Mapping[str, object]],
) -> Iterable[Mapping[str, object]]:
    values = value if isinstance(value, list) else (value,)
    for candidate in values:
        product = _resolve_top_level_node(candidate, index)
        if product is not None and _has_type(product, "product"):
            yield product


def _resolve_top_level_node(
    value: object,
    index: Mapping[str, Mapping[str, object]],
) -> Mapping[str, object] | None:
    if isinstance(value, str):
        return index.get(value)
    if not isinstance(value, Mapping):
        return None
    identifier = value.get("@id")
    if isinstance(identifier, str) and identifier in index:
        return index[identifier]
    return value


def _reference_url(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        identifier = value.get("@id") or value.get("url")
        return identifier if isinstance(identifier, str) else None
    return None


def _matches_page_url(
    candidate: str,
    page_urls: tuple[str, ...],
    allowed_hosts: tuple[str, ...],
) -> bool:
    try:
        validate_https_url(candidate, allowed_hosts)
    except Exception:
        return False
    candidate_key = _page_key(candidate)
    return any(candidate_key == _page_key(page_url) for page_url in page_urls)


def _page_key(url: str) -> tuple[str, str, str]:
    parsed = urlsplit(url)
    return (
        parsed.scheme.casefold(),
        (parsed.hostname or "").casefold(),
        parsed.path.rstrip("/") or "/",
    )


def _has_type(value: Mapping[str, object], expected: str) -> bool:
    raw_type = value.get("@type")
    types = raw_type if isinstance(raw_type, list) else (raw_type,)
    return any(
        isinstance(item, str)
        and item.rstrip("/").rsplit("/", 1)[-1].rsplit("#", 1)[-1].casefold() == expected
        for item in types
    )


def _structured_candidate_item_id(
    key: str,
    candidate: object,
    allowed_hosts: tuple[str, ...],
) -> str | None:
    normalized_key = key.casefold()
    if normalized_key in {"sku", "productid", "mpn"}:
        return _exact_item_id(candidate)
    if normalized_key in {"@id", "url"}:
        if not isinstance(candidate, str):
            return None
        try:
            validate_https_url(candidate, allowed_hosts)
        except Exception:
            return None
    return extract_mercado_item_id(candidate)


def _exact_item_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().upper()
    return candidate if _EXACT_ITEM_ID.fullmatch(candidate) else None


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Constante JSON não permitida: {value}")


def _picture_urls(value: object) -> tuple[object, ...]:
    if not isinstance(value, list):
        return ()
    pictures: list[object] = []
    for picture in value:
        if isinstance(picture, Mapping):
            pictures.append(picture.get("secure_url") or picture.get("url"))
    return tuple(pictures)


def _clean_category(value: object) -> str | None:
    return clean_text(value) or None
