"""Smokes opt-in, somente de leitura, contra o catálogo público atual.

Este módulo não consulta a rede durante importação ou coleta. O opt-in é
deliberado porque as lojas podem bloquear leituras públicas a qualquer momento.
"""

from __future__ import annotations

import csv
import os
from io import StringIO
from typing import Final

import pytest


RUN_LIVE_TESTS = os.getenv("RUN_LIVE_TESTS") == "1"
pytestmark = pytest.mark.skipif(not RUN_LIVE_TESTS, reason="RUN_LIVE_TESTS=1 não definido")

from automation.config import CATALOG_CURRENCY, PRODUCTS_HEADERS
from automation.connectors.base import build_connector_registry
from automation.http_client import SafeHttpClient
from automation.models import (
    BlockedByStoreError,
    InvalidProductDataError,
    ProductNotFoundError,
    ProductSnapshot,
)


_PUBLIC_CATALOG_CSV: Final = (
    "https://docs.google.com/spreadsheets/d/"
    "1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0/export?format=csv&gid=952991100"
)
_CATALOG_HOSTS: Final = ("docs.google.com",)
_CATALOG_CONTENT_TYPES: Final = ("text/csv", "text/plain")
_STORE_LABELS: Final = {
    "Mercado Livre": "mercado_livre",
    "Shopee": "shopee",
}
_EXPECTED_SEMI_AUTOMATIC_OUTCOMES: Final = (
    BlockedByStoreError,
    InvalidProductDataError,
    ProductNotFoundError,
)


def test_current_active_mercado_livre_and_shopee_rows_follow_read_only_contract() -> None:
    """The selected public links either normalize or have a typed safe outcome."""
    try:
        with SafeHttpClient() as client:
            samples = _current_active_store_samples(client)
            registry = build_connector_registry(client)
            for partner_key, source_url in samples:
                connector = registry[partner_key]
                if not connector.supports(source_url):
                    _contract_failure()
                outcome = _fetch_read_only(connector, source_url)
                _assert_contract_outcome(outcome, partner_key)
    except Exception:
        _contract_failure()


def _current_active_store_samples(client: SafeHttpClient) -> tuple[tuple[str, str], ...]:
    response = client.get(_PUBLIC_CATALOG_CSV, _CATALOG_HOSTS, _CATALOG_CONTENT_TYPES)
    try:
        rows = tuple(csv.reader(StringIO(response.body.decode("utf-8-sig", errors="strict"))))
    except (UnicodeError, csv.Error):
        _contract_failure()

    header_index = next(
        (index for index, row in enumerate(rows) if tuple(row) == PRODUCTS_HEADERS),
        None,
    )
    if header_index is None:
        _contract_failure()

    samples: dict[str, str] = {}
    for row in rows[header_index + 1 :]:
        if len(row) != len(PRODUCTS_HEADERS) or row[0] != "Sim":
            continue
        partner_key = _STORE_LABELS.get(row[2])
        source_url = row[11]
        if partner_key is not None and source_url and partner_key not in samples:
            samples[partner_key] = source_url

    if set(samples) != set(_STORE_LABELS.values()):
        _contract_failure()
    return tuple((partner_key, samples[partner_key]) for partner_key in _STORE_LABELS.values())


def _fetch_read_only(connector: object, source_url: str) -> ProductSnapshot | Exception:
    if not hasattr(connector, "fetch"):
        _contract_failure()
    try:
        return connector.fetch(source_url)  # type: ignore[union-attr]
    except _EXPECTED_SEMI_AUTOMATIC_OUTCOMES as outcome:
        return outcome
    except Exception:
        _contract_failure()


def _assert_contract_outcome(outcome: ProductSnapshot | Exception, partner_key: str) -> None:
    if isinstance(outcome, ProductSnapshot):
        if (
            outcome.partner != partner_key
            or not outcome.external_id
            or outcome.currency != CATALOG_CURRENCY
        ):
            _contract_failure()
        return
    if not isinstance(outcome, _EXPECTED_SEMI_AUTOMATIC_OUTCOMES):
        _contract_failure()


def _contract_failure() -> None:
    raise AssertionError("Consulta pública não cumpriu o contrato de leitura.") from None
