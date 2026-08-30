"""Contrato inerte de TikTok Shop, ativável apenas por configuração injetada em teste."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

from ..config import PartnerConfig
from ..http_client import SafeHttpClient
from ..metadata import (
    ExtractedProductData,
    clean_text,
    extract_product_metadata,
)
from ..models import ConnectorError, InvalidProductDataError, ProductSnapshot, UnsupportedUrlError
from ..security import validate_https_url
from .base import (
    MetadataConnectorBase,
    _HTML_CONTENT_TYPES,
    snapshot_from_metadata,
    validate_required_metadata,
)


_PRODUCT_PATH = re.compile(r"(?:^|/)product/(?P<product>[1-9]\d{0,14})(?:/|$)", re.I)
_Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class TikTokShopApiProduct:
    """Public normalized product fields a future official API adapter may return.

    This is an in-process contract only: it defines neither an endpoint nor a
    credential mechanism.
    """

    name: str
    description: str
    current_price: Decimal
    previous_price: Decimal | None
    currency: str
    images: tuple[str, ...]
    source_category: str | None
    available: bool | None
    coupon: str | None = None


@runtime_checkable
class TikTokShopApi(Protocol):
    """Optional future public API dependency; version one injects none in production."""

    def fetch_product(self, external_id: str) -> TikTokShopApiProduct:
        """Return normalized public fields for the already validated external identity."""


def extract_tiktok_shop_product_id(value: object) -> str | None:
    """Read a bounded identity from a safe terminal page path, never visible text/query data."""
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    path = parsed.path if parsed.scheme or parsed.netloc or value.startswith("/") else ""
    match = _PRODUCT_PATH.search(path)
    return match.group("product") if match is not None else None


class TikTokShopConnector(MetadataConnectorBase):
    """Fetch one configured public HTML page; production configuration intentionally has no hosts."""

    product_type = ""

    def __init__(
        self,
        http_client: SafeHttpClient,
        partner: PartnerConfig,
        *,
        api: TikTokShopApi | None = None,
        metadata_extractor: Callable[[str, str], ExtractedProductData] = extract_product_metadata,
        clock: _Clock | None = None,
    ) -> None:
        super().__init__(http_client, partner, metadata_extractor=metadata_extractor, clock=clock)
        self._api = api

    @property
    def live_verified(self) -> bool:
        return self._partner.live_verified

    def fetch(self, affiliate_url: str) -> ProductSnapshot:
        """Preserve the literal affiliate URL and avoid any speculative API request."""
        if not self.supports(affiliate_url):
            raise UnsupportedUrlError("URL incompatível com o conector selecionado.")
        response = self._http_client.get(affiliate_url, self.allowed_hosts, _HTML_CONTENT_TYPES)
        try:
            validate_https_url(response.url, self.allowed_hosts)
        except Exception as error:
            raise InvalidProductDataError("A página terminal TikTok Shop não é confiável.") from error
        external_id = extract_tiktok_shop_product_id(response.url)
        if external_id is None:
            raise InvalidProductDataError("O produto não tem um ID externo válido.")
        if self._api is not None:
            try:
                metadata = _metadata_from_api_product(self._api.fetch_product(external_id))
            except ConnectorError:
                raise
            except Exception as error:
                raise InvalidProductDataError("A API opcional retornou dados inválidos.") from error
        else:
            html = response.body.decode("utf-8", errors="replace")
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


def _metadata_from_api_product(value: object) -> ExtractedProductData:
    if not isinstance(value, TikTokShopApiProduct):
        raise InvalidProductDataError("A API opcional retornou dados inválidos.")
    if not isinstance(value.images, tuple) or not all(isinstance(image, str) for image in value.images):
        raise InvalidProductDataError("A API opcional retornou imagens inválidas.")
    if value.available is not None and not isinstance(value.available, bool):
        raise InvalidProductDataError("A API opcional retornou disponibilidade inválida.")
    if value.coupon is not None and not isinstance(value.coupon, str):
        raise InvalidProductDataError("A API opcional retornou cupom inválido.")
    coupon = clean_text(value.coupon) or None
    return ExtractedProductData(
        name=value.name,
        description=value.description,
        current_price=value.current_price,
        previous_price=value.previous_price,
        currency=value.currency,
        images=value.images,
        coupon=coupon,
        source_category=(clean_text(value.source_category) if isinstance(value.source_category, str) else None),
        available=value.available,
    )
