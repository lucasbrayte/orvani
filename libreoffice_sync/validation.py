from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlsplit

from .models import CatalogRow
from .normalization import normalize_catalog_row


class LocalValidationError(ValueError):
    pass


YES_NO = {"Sim", "Não"}
UPDATE_MODES = {"Automático", "Manual", "Bloqueado"}
PRODUCT_TYPES = {"Físico", "Digital"}
PARTNERS = {"Mercado Livre", "Shopee", "SHEIN", "Amazon"}


def _https(value: str, field: str) -> None:
    if not value:
        return
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise LocalValidationError(f"{field} deve usar HTTPS.")


def _positive(value: Decimal | None, field: str) -> None:
    if value is not None and value <= 0:
        raise LocalValidationError(
            f"{field} deve ser maior que zero."
        )


def validate_catalog_row(row: CatalogRow) -> None:
    row = normalize_catalog_row(row)

    for field_name, value in (
        ("Ativo", row.active),
        ("Publicar", row.publish),
        ("Destaque", row.featured),
    ):
        if value not in YES_NO:
            raise LocalValidationError(
                f"{field_name} deve ser Sim ou Não."
            )

    if row.update_mode not in UPDATE_MODES:
        raise LocalValidationError(
            "Modo Atualização inválido."
        )

    if row.partner not in PARTNERS:
        raise LocalValidationError(
            "Plataforma não pôde ser identificada pelos links."
        )

    if row.product_type and row.product_type not in PRODUCT_TYPES:
        raise LocalValidationError(
            "Tipo deve ser Físico ou Digital."
        )

    if not row.product_url:
        raise LocalValidationError(
            "Link Produto é obrigatório."
        )
    if not row.affiliate_url:
        raise LocalValidationError(
            "Link Afiliado é obrigatório."
        )

    _https(row.product_url, "Link Produto")
    _https(row.affiliate_url, "Link Afiliado")
    for index, image in enumerate(row.images, start=1):
        _https(image, f"Imagem {index}")

    _positive(row.current_price, "Preço Atual")
    _positive(row.previous_price, "Preço Anterior")

    if (
        row.current_price is not None
        and row.previous_price is not None
        and row.previous_price <= row.current_price
    ):
        raise LocalValidationError(
            "Preço Anterior deve ser maior que Preço Atual."
        )
