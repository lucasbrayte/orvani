"""Contratos e implementações isoladas por parceiro."""

from .base import (
    ConnectorRegistry,
    MetadataConnectorBase,
    ProductConnector,
    build_connector_registry,
    snapshot_from_metadata,
)

__all__ = (
    "ConnectorRegistry",
    "MetadataConnectorBase",
    "ProductConnector",
    "build_connector_registry",
    "snapshot_from_metadata",
)
