from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from automation.models import (
    ImportRecord,
    ImportStatus,
    UpdateMode,
)
from automation.sync import (
    _is_selected,
    _permanent_error_hash,
    _signature_envelope,
)


NOW = datetime(2026, 9, 11, 23, 55, tzinfo=UTC)


def _record(*, description: str) -> ImportRecord:
    record = ImportRecord(
        row_number=43,
        automation_id="41407d7f-b292-4305-928a-6b9ee712d800",
        active="Sim",
        publish="Sim",
        featured="Não",
        order="",
        update_mode=UpdateMode.MANUAL,
        product_url=(
            "https://contingenciamaxima.com.br/produto/"
            "995d4549-50f4-4b76-a857-20e64ec51da1"
        ),
        affiliate_url=(
            "https://contingenciamaxima.com.br/produto/"
            "995d4549-50f4-4b76-a857-20e64ec51da1?ref=lukn"
        ),
        partner="afiliado",
        external_id="995d4549-50f4-4b76-a857-20e64ec51da1",
        name="26MIL JOGOS NA SUA CONTA STEAM | VITALÍCIO",
        description=description,
        category="Jogos",
        subcategory="Jogos Digitais",
        product_type="Digital",
        current_price=Decimal("49.90"),
        previous_price=Decimal("299.90"),
        calculated_discount="",
        coupon="",
        coupon_expires_at="",
        image_1=(
            "https://cdn.nxtcommerce.online/product-images/"
            "6882f8c0-e0f5-4459-9a44-ebab9be45c04/products/test.webp"
        ),
        image_2="",
        image_3="",
        image_4="",
        button_text="Ver Oferta",
        status=ImportStatus.ERRO,
        message="Dados públicos do produto são inválidos.",
        consecutive_attempts=0,
        last_published_url="",
        data_signature="",
        last_checked_at="",
        last_updated_at="",
    )
    signature = _signature_envelope(
        record,
        _permanent_error_hash("invalid_product_data"),
    )
    return replace(record, data_signature=signature)


def test_pending_keeps_incomplete_affiliate_manual_error_quiet():
    record = _record(description="")
    assert _is_selected(record, "pending", NOW) is False


def test_pending_retries_affiliate_manual_error_after_metadata_is_fixed():
    record = _record(
        description="26 mil jogos para sua conta Steam com acesso digital."
    )
    assert _is_selected(record, "pending", NOW) is True
