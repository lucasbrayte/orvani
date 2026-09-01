"""Regressões offline do harness de smoke público opt-in."""

from __future__ import annotations

from automation.connectors.base import ConnectorRegistry
from automation.models import BlockedByStoreError
from tests.live import test_store_smoke as smoke


class _NoNetworkClient:
    def __enter__(self) -> _NoNetworkClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _BlockedConnector:
    partner_key = "mercado_livre"

    def supports(self, url: str) -> bool:
        return url == "https://www.mercadolivre.com.br/p/MLB123456"

    def fetch(self, affiliate_url: str) -> None:
        raise BlockedByStoreError("Leitura pública bloqueada.")


def test_live_smoke_selects_connector_by_url_without_mapping_access(monkeypatch) -> None:
    """A registry API must be selected by URL, never indexed as a mapping."""
    sample = ("mercado_livre", "https://www.mercadolivre.com.br/p/MLB123456")
    registry = ConnectorRegistry((_BlockedConnector(),))

    monkeypatch.setattr(smoke, "SafeHttpClient", _NoNetworkClient)
    monkeypatch.setattr(smoke, "_current_active_store_samples", lambda client: (sample,))
    monkeypatch.setattr(smoke, "build_connector_registry", lambda client: registry)

    smoke.test_current_active_mercado_livre_and_shopee_rows_follow_read_only_contract()
