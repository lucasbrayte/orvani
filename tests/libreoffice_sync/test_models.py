from decimal import Decimal

from libreoffice_sync.models import BackendStatus, CatalogRow
from libreoffice_sync.workbook_schema import (
    CATALOG_SHEET,
    EDITABLE_COLUMNS,
    STATUS_COLUMNS,
    TECHNICAL_COLUMNS,
)


def test_workbook_column_contract_is_stable():
    assert CATALOG_SHEET == "Catálogo"
    assert EDITABLE_COLUMNS["Ativo"] == 0
    assert EDITABLE_COLUMNS["Texto Botão"] == 21
    assert STATUS_COLUMNS == {
        "Status": 22,
        "Mensagem": 23,
        "Desconto": 24,
        "Última Verificação": 25,
        "Última Atualização": 26,
    }
    assert TECHNICAL_COLUMNS["ID Automação"] == 27
    assert TECHNICAL_COLUMNS["Hash Confirmado"] == 33


def test_catalog_row_accepts_decimal_prices():
    row = CatalogRow(
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
        name="Produto",
        description="Descrição",
        category="Casa",
        subcategory="Cozinha",
        product_type="Físico",
        current_price=Decimal("189.99"),
        previous_price=Decimal("331.42"),
        coupon="",
        coupon_expires_at="",
        images=("https://example.com/1.jpg", "", "", ""),
        button_text="Ver oferta",
        row_hash="hash",
        acknowledged_hash="",
    )
    assert row.current_price == Decimal("189.99")


def test_backend_status_is_immutable():
    status = BackendStatus(
        automation_id="uuid-1",
        external_id="MLB12345678",
        status="PUBLICADO",
        message="ok",
        discount="43",
        last_published_url="https://meli.la/teste",
        data_signature="abc",
        last_checked_at="2026-09-03T15:00:00Z",
        last_updated_at="2026-09-03T15:00:01Z",
    )
    assert status.status == "PUBLICADO"
