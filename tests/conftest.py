from datetime import UTC, datetime
from decimal import Decimal

import pytest


@pytest.fixture
def snapshot_kwargs():
    return {
        "partner": "mercado_livre",
        "external_id": "MLB123",
        "catalog_id": None,
        "source_url": "https://www.mercadolivre.com.br/item/MLB123",
        "affiliate_url": "https://www.mercadolivre.com.br/item/MLB123",
        "name": "Produto de teste",
        "description": "Descrição de teste",
        "current_price": Decimal("10.00"),
        "previous_price": None,
        "currency": "BRL",
        "category": "Eletrônicos",
        "subcategory": "Acessórios",
        "product_type": "Físico",
        "coupon": None,
        "coupon_expires_at": None,
        "images": ("https://images.example/item.jpg",),
        "available": True,
        "fetched_at": datetime(2026, 8, 30, tzinfo=UTC),
    }
