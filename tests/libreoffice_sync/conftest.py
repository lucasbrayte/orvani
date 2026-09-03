from decimal import Decimal

import pytest

from libreoffice_sync.models import CatalogRow


@pytest.fixture
def valid_row():
    return CatalogRow(
        row_number=2,
        automation_id="uuid-1",
        active="Sim",
        publish="Sim",
        featured="Não",
        order="1",
        update_mode="Manual",
        product_url="https://www.mercadolivre.com.br/produto/p/MLB12345678",
        affiliate_url="https://meli.la/teste",
        partner="Mercado Livre",
        name="Produto Teste",
        description="Descrição completa",
        category="Casa",
        subcategory="Cozinha",
        product_type="Físico",
        current_price=Decimal("189.99"),
        previous_price=Decimal("331.42"),
        coupon="ORVANI10",
        coupon_expires_at="2026-09-30",
        images=("https://example.com/1.jpg", "", "", ""),
        button_text="Ver oferta",
        row_hash="",
        acknowledged_hash="",
    )
