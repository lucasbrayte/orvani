from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlsplit

from .models import CatalogRow


class LocalValidationError(ValueError):
    pass


YES_NO = {"Sim", "Não"}
UPDATE_MODES = {"Automático", "Manual", "Bloqueado"}
PRODUCT_TYPES = {"Físico", "Digital"}
PARTNERS = {"Mercado Livre", "Shopee", "SHEIN"}


def _https(value: str, field: str) -> None:
    if not value:
        return
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise LocalValidationError(f"{field} deve usar HTTPS.")


def _positive(value: Decimal | None, field: str) -> None:
    if value is not None and value <= 0:
        raise LocalValidationError(f"{field} deve ser maior que zero.")


def validate_catalog_row(row: CatalogRow) -> None:
    for field_name, value in (
        ("Ativo", row.active),
        ("Publicar", row.publish),
        ("Destaque", row.featured),
    ):
        if value not in YES_NO:
            raise LocalValidationError(f"{field_name} deve ser Sim ou Não.")

    if row.update_mode not in UPDATE_MODES:
        raise LocalValidationError("Modo Atualização inválido.")

    if row.partner not in PARTNERS:
        raise LocalValidationError("Plataforma não suportada nesta versão.")

    if row.product_type and row.product_type not in PRODUCT_TYPES:
        raise LocalValidationError("Tipo deve ser Físico ou Digital.")

    if not row.product_url and not row.affiliate_url:
        raise LocalValidationError("Informe Link Produto ou Link Afiliado.")

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
        raise LocalValidationError("Preço Anterior deve ser maior que Preço Atual.")

    if row.update_mode == "Manual" and row.publish == "Sim":
        required = (
            ("Nome", row.name),
            ("Descrição", row.description),
            ("Categoria", row.category),
            ("Subcategoria", row.subcategory),
            ("Tipo", row.product_type),
        )
        for field, value in required:
            if not value.strip():
                raise LocalValidationError(f"{field} é obrigatório no modo Manual.")

        if row.current_price is None:
            raise LocalValidationError("Preço Atual é obrigatório no modo Manual.")

        if not any(image.strip() for image in row.images):
            raise LocalValidationError("Ao menos uma imagem é obrigatória no modo Manual.")
