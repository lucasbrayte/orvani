"""Contratos e implementações isoladas por parceiro."""

from .base import (
    ConnectorRegistry,
    MetadataConnectorBase,
    ProductConnector,
    build_connector_registry,
    snapshot_from_metadata,
)
from .mercado_livre import (
    MercadoLivreConnector,
    extract_mercado_catalog_id,
    extract_mercado_item_id,
)
from .shopee import ShopeeConnector, build_conversion_batches, extract_shopee_item_id
from .shein import SheinConnector, extract_shein_product_id
from .tiktok_shop import TikTokShopApi, TikTokShopApiProduct, TikTokShopConnector, extract_tiktok_shop_product_id

__all__ = (
    "ConnectorRegistry",
    "MetadataConnectorBase",
    "MercadoLivreConnector",
    "ProductConnector",
    "ShopeeConnector",
    "SheinConnector",
    "TikTokShopApi",
    "TikTokShopApiProduct",
    "TikTokShopConnector",
    "build_conversion_batches",
    "build_connector_registry",
    "snapshot_from_metadata",
    "extract_mercado_catalog_id",
    "extract_mercado_item_id",
    "extract_shopee_item_id",
    "extract_shein_product_id",
    "extract_tiktok_shop_product_id",
)
