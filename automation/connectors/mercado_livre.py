"""Conector público e restrito para itens do Mercado Livre."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

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
_STRUCTURED_ID_KEYS = frozenset({"sku", "productid", "mpn", "@id", "url"})
_Clock = Callable[[], datetime]


def extract_mercado_item_id(value: object) -> str | None:
    """Normalize a bounded MLB item ID from a URL path or individual trusted value."""
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    candidate = parsed.path if parsed.scheme or parsed.netloc or value.startswith("/") else value
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
        try:
            item = json.loads(api_response.body)
        except (TypeError, json.JSONDecodeError) as error:
            raise InvalidProductDataError("A API pública retornou dados inválidos.") from error
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
        for canonical in parser.canonicals:
            item_id = self._trusted_canonical_item_id(canonical)
            if item_id is not None:
                return item_id
        for block in parser.jsonld_blocks:
            try:
                document = json.loads(block)
            except json.JSONDecodeError:
                continue
            item_id = _structured_item_id(document, self.allowed_hosts)
            if item_id is not None:
                return item_id
        return None

    def _trusted_canonical_item_id(self, canonical: str) -> str | None:
        try:
            validate_https_url(canonical, self.allowed_hosts)
        except Exception:
            return None
        return extract_mercado_item_id(canonical)


def _structured_item_id(value: object, allowed_hosts: tuple[str, ...]) -> str | None:
    if isinstance(value, Mapping):
        for key, candidate in value.items():
            if isinstance(key, str) and key.casefold() in _STRUCTURED_ID_KEYS:
                item_id = _structured_candidate_item_id(key, candidate, allowed_hosts)
                if item_id is not None:
                    return item_id
            nested = _structured_item_id(candidate, allowed_hosts)
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for candidate in value:
            item_id = _structured_item_id(candidate, allowed_hosts)
            if item_id is not None:
                return item_id
    return None


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
