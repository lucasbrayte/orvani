"""Contrato comum para conectores públicos de parceiros."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
import re
from typing import Protocol, runtime_checkable

from ..categorizer import categorize
from ..config import PARTNERS, PartnerConfig
from ..http_client import SafeHttpClient
from ..metadata import (
    ExtractedProductData,
    clean_text,
    extract_product_metadata,
    unique_https_images,
)
from ..models import (
    ConfigurationError,
    InvalidProductDataError,
    ProductSnapshot,
    UnsupportedUrlError,
)
from ..security import validate_https_url


_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_MetadataExtractor = Callable[[str, str], ExtractedProductData]
_Clock = Callable[[], datetime]
_CURRENCY = re.compile(r"[A-Z]{3}\Z")


@runtime_checkable
class ProductConnector(Protocol):
    """The minimum behavior required to select and fetch a store connector."""

    @property
    def partner_key(self) -> str:
        """Stable partner identifier used by the registry and synchronization."""

    def supports(self, url: str) -> bool:
        """Return whether the connector can safely handle *url* without network I/O."""

    def fetch(self, affiliate_url: str) -> ProductSnapshot:
        """Fetch public product data while retaining the original affiliate URL."""


def snapshot_from_metadata(
    *,
    partner_key: str,
    external_id: str,
    catalog_id: str | None,
    source_url: str,
    affiliate_url: str,
    metadata: ExtractedProductData,
    fetched_at: datetime,
    product_type: str = "",
) -> ProductSnapshot:
    """Create the shared immutable snapshot without filling unknown public fields."""
    category = categorize(
        metadata.source_category,
        metadata.name,
        metadata.description,
    )
    return ProductSnapshot(
        partner=partner_key,
        external_id=external_id,
        catalog_id=catalog_id,
        source_url=source_url,
        affiliate_url=affiliate_url,
        name=metadata.name,
        description=metadata.description,
        current_price=metadata.current_price,
        previous_price=metadata.previous_price,
        currency=metadata.currency,
        category=category.category,
        subcategory=category.subcategory or "",
        product_type=product_type,
        coupon=metadata.coupon,
        coupon_expires_at=None,
        images=metadata.images,
        available=metadata.available,
        fetched_at=fetched_at,
    )


def validate_required_metadata(metadata: object) -> ExtractedProductData:
    """Normalize required public product fields before any snapshot is constructed."""
    if not isinstance(metadata, ExtractedProductData):
        raise InvalidProductDataError("O conector retornou metadados inválidos.")
    name = clean_text(metadata.name) if isinstance(metadata.name, str) else ""
    currency = clean_text(metadata.currency).upper() if isinstance(metadata.currency, str) else ""
    current = metadata.current_price
    if (
        not name
        or not isinstance(current, Decimal)
        or not current.is_finite()
        or current <= 0
        or not _CURRENCY.fullmatch(currency)
    ):
        raise InvalidProductDataError("O produto não contém dados obrigatórios válidos.")
    images = unique_https_images(metadata.images) if isinstance(metadata.images, tuple) else ()
    if not images:
        raise InvalidProductDataError("O produto não contém imagens públicas válidas.")
    previous = metadata.previous_price
    if not isinstance(previous, Decimal) or not previous.is_finite() or previous <= current:
        previous = None
    return replace(
        metadata,
        name=name,
        currency=currency,
        images=images,
        previous_price=previous,
    )


class MetadataConnectorBase:
    """Fetch public HTML and turn shared metadata into a product snapshot."""

    product_type = ""

    def __init__(
        self,
        http_client: SafeHttpClient,
        partner: PartnerConfig,
        *,
        metadata_extractor: _MetadataExtractor = extract_product_metadata,
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
        """Check URL shape and configured partner hosts without resolving or fetching."""
        try:
            validate_https_url(url, self.allowed_hosts)
        except Exception:
            return False
        return True

    def fetch(self, affiliate_url: str) -> ProductSnapshot:
        """Fetch a supported public HTML page and preserve its supplied affiliate URL."""
        if not self.supports(affiliate_url):
            raise UnsupportedUrlError("URL incompatível com o conector selecionado.")
        response = self._http_client.get(
            affiliate_url,
            self.allowed_hosts,
            _HTML_CONTENT_TYPES,
        )
        metadata = self.extract_metadata(
            response.body.decode("utf-8", errors="replace"),
            response.url,
        )
        if not isinstance(metadata, ExtractedProductData):
            raise InvalidProductDataError("O conector retornou metadados inválidos.")
        external_id, catalog_id = self._validated_identifiers(
            self.extract_identifiers(metadata, response.url)
        )
        return snapshot_from_metadata(
            partner_key=self.partner_key,
            external_id=external_id,
            catalog_id=catalog_id,
            source_url=response.url,
            affiliate_url=affiliate_url,
            metadata=metadata,
            fetched_at=self._clock(),
            product_type=self.product_type,
        )

    def extract_metadata(self, html: str, source_url: str) -> ExtractedProductData:
        """Hook for a partner to extend public metadata extraction."""
        return self._metadata_extractor(html, source_url)

    def extract_identifiers(
        self, metadata: ExtractedProductData, source_url: str
    ) -> tuple[str, str | None]:
        """Hook for deriving trusted product and optional catalog identifiers."""
        raise NotImplementedError

    @staticmethod
    def _validated_identifiers(value: object) -> tuple[str, str | None]:
        if not isinstance(value, tuple) or len(value) != 2:
            raise InvalidProductDataError("O conector retornou identificadores inválidos.")
        external_id, catalog_id = value
        if not isinstance(external_id, str) or not external_id.strip():
            raise InvalidProductDataError("O produto não tem um ID externo válido.")
        if catalog_id is not None and (
            not isinstance(catalog_id, str) or not catalog_id.strip()
        ):
            raise InvalidProductDataError("O produto tem um ID de catálogo inválido.")
        return external_id, catalog_id


class ConnectorRegistry:
    """Select exactly one stateless connector without performing network I/O."""

    def __init__(self, connectors: Iterable[ProductConnector]) -> None:
        self._connectors = tuple(connectors)

    def select(self, url: str) -> ProductConnector:
        matches: list[ProductConnector] = []
        for connector in self._connectors:
            try:
                supported = connector.supports(url)
            except Exception:
                continue
            if supported is True:
                matches.append(connector)
        if len(matches) != 1:
            raise UnsupportedUrlError("Nenhum ou mais de um conector suporta a URL.")
        return matches[0]


_FUTURE_CONNECTORS = (
    ("mercado_livre", "MercadoLivreConnector"),
    ("shopee", "ShopeeConnector"),
    ("shein", "SheinConnector"),
    ("tiktok_shop", "TikTokShopConnector"),
)


def build_connector_registry(
    http_client: SafeHttpClient,
    partners: Mapping[str, PartnerConfig] = PARTNERS,
) -> ConnectorRegistry:
    """Build the registry from concrete modules that have been implemented so far."""
    connectors: list[ProductConnector] = []
    for partner_key, class_name in _FUTURE_CONNECTORS:
        module_name = f"{__package__}.{partner_key}"
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as error:
            if error.name == module_name:
                continue
            raise
        partner = partners.get(partner_key)
        if partner is None:
            raise ConfigurationError(
                f"Configuração do parceiro ausente para o conector {partner_key}."
            )
        try:
            connector_class = getattr(module, class_name)
        except AttributeError as error:
            raise ConfigurationError(
                f"Classe {class_name} ausente no conector {partner_key}."
            ) from error
        if not callable(connector_class):
            raise ConfigurationError(
                f"Classe {class_name} inválida no conector {partner_key}."
            )
        connectors.append(connector_class(http_client, partner))
    return ConnectorRegistry(connectors)
