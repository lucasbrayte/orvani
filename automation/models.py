"""Modelos de domínio imutáveis para a automação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ConnectorError(Exception):
    """Falha esperada ao obter dados de uma loja."""


class UnsupportedUrlError(ConnectorError):
    pass


class ProductNotFoundError(ConnectorError):
    pass


class TemporaryFetchError(ConnectorError):
    pass


class BlockedByStoreError(ConnectorError):
    pass


class InvalidProductDataError(ConnectorError):
    pass


class UnsafeUrlError(ConnectorError):
    pass


class UnsafeRedirectError(ConnectorError):
    pass


class ResponseTooLargeError(ConnectorError):
    pass


class UnexpectedContentTypeError(ConnectorError):
    pass


class AmbiguousProductMatchError(ConnectorError):
    pass


class SheetSchemaError(ConnectorError):
    pass


class ConfigurationError(ConnectorError):
    pass


class ImportStatus(StrEnum):
    NOVO = "NOVO"
    AGUARDANDO_CONVERSAO = "AGUARDANDO CONVERSÃO"
    PROCESSANDO = "PROCESSANDO"
    REVISAR = "REVISAR"
    PRONTO_PARA_PUBLICAR = "PRONTO PARA PUBLICAR"
    PUBLICADO = "PUBLICADO"
    ATENCAO = "ATENÇÃO"
    ERRO = "ERRO"
    DESATIVADO = "DESATIVADO"


class UpdateMode(StrEnum):
    AUTOMATICO = "Automático"
    MANUAL = "Manual"
    BLOQUEADO = "Bloqueado"


@dataclass(frozen=True, slots=True)
class ProductSnapshot:
    partner: str
    external_id: str
    catalog_id: str | None
    source_url: str
    affiliate_url: str
    name: str
    description: str
    current_price: Decimal
    previous_price: Decimal | None
    currency: str
    category: str
    subcategory: str
    product_type: str
    coupon: str | None
    coupon_expires_at: datetime | None
    images: tuple[str, ...]
    available: bool | None
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.current_price <= Decimal("0"):
            raise InvalidProductDataError("O preço atual deve ser positivo.")
        if len(self.images) > 4:
            raise InvalidProductDataError("Um produto pode ter no máximo quatro imagens.")
        if self.previous_price is not None and self.previous_price <= self.current_price:
            object.__setattr__(self, "previous_price", None)


@dataclass(frozen=True, slots=True)
class ImportRecord:
    row_number: int
    automation_id: str
    active: str
    publish: str
    featured: str
    order: str
    update_mode: UpdateMode
    product_url: str
    affiliate_url: str
    partner: str
    external_id: str
    name: str
    description: str
    category: str
    subcategory: str
    product_type: str
    current_price: Decimal | None
    previous_price: Decimal | None
    calculated_discount: str
    coupon: str
    coupon_expires_at: str
    image_1: str
    image_2: str
    image_3: str
    image_4: str
    button_text: str
    status: ImportStatus
    message: str
    consecutive_attempts: int
    last_published_url: str
    data_signature: str
    last_checked_at: str
    last_updated_at: str
    link_signature: str | None = None

    @classmethod
    def from_sheet_row(
        cls, row_number: int, values: tuple[Any, ...] | list[Any]
    ) -> tuple["ImportRecord", "SheetUpdate | None"]:
        cells = tuple(values) + ("",) * max(0, 32 - len(values))
        if len(cells) > 32:
            raise SheetSchemaError("A linha de Importações excede 32 colunas.")
        automation_id = "" if cells[0] is None else str(cells[0]).strip()
        planned_write = None
        if not automation_id:
            automation_id = str(uuid4())
            planned_write = SheetUpdate(f"Importações!A{row_number}", ((automation_id,),))
        return (
            cls(
                row_number=row_number,
                automation_id=automation_id,
                active=str(cells[1]),
                publish=str(cells[2]) or "Não",
                featured=str(cells[3]) or "Não",
                order=str(cells[4]),
                update_mode=UpdateMode(str(cells[5]) or UpdateMode.AUTOMATICO),
                product_url=str(cells[6]), affiliate_url=str(cells[7]), partner=str(cells[8]),
                external_id=str(cells[9]), name=str(cells[10]), description=str(cells[11]),
                category=str(cells[12]), subcategory=str(cells[13]), product_type=str(cells[14]),
                current_price=_decimal_or_none(cells[15]), previous_price=_decimal_or_none(cells[16]),
                calculated_discount=str(cells[17]), coupon=str(cells[18]), coupon_expires_at=str(cells[19]),
                image_1=str(cells[20]), image_2=str(cells[21]), image_3=str(cells[22]), image_4=str(cells[23]),
                button_text=str(cells[24]), status=ImportStatus(str(cells[25]) or ImportStatus.NOVO),
                message=str(cells[26]), consecutive_attempts=int(cells[27] or 0),
                last_published_url=str(cells[28]), data_signature=str(cells[29]),
                last_checked_at=str(cells[30]), last_updated_at=str(cells[31]),
            ),
            planned_write,
        )


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


@dataclass(frozen=True, slots=True)
class ProductRow:
    row_number: int
    active: str
    product_type: str
    partner: str
    category: str
    subcategory: str
    name: str
    description: str
    price: Decimal | None
    promotional_price: Decimal | None
    coupon: str
    offer_expires_at: str
    affiliate_url: str
    button_text: str
    video_url: str
    image_1: str
    image_2: str
    image_3: str
    image_4: str
    order: str
    featured: str
    reconstructed_external_id: str | None = None
    reconstructed_catalog_id: str | None = None


@dataclass(frozen=True, slots=True)
class SheetUpdate:
    range_name: str
    values: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True, slots=True)
class SyncItemResult:
    row_number: int
    initial_status: ImportStatus
    final_status: ImportStatus
    message: str
    import_changed: bool
    product_changed: bool


@dataclass(frozen=True, slots=True)
class SyncReport:
    items: tuple[SyncItemResult, ...]
    planned_import_updates: tuple[SheetUpdate, ...]
    planned_product_updates: tuple[SheetUpdate, ...]
    dry_run: bool

    def final_status(self, row_number: int) -> ImportStatus:
        for item in self.items:
            if item.row_number == row_number:
                return item.final_status
        raise KeyError(row_number)
