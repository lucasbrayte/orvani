"""Planejamento idempotente do backfill da Central de Divulgação."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from .config import DIVULGATION_HEADERS, normalize_unicode_text
from .models import (
    AmbiguousProductMatchError,
    ImportRecord,
    ImportStatus,
    InvalidProductDataError,
    ProductRow,
    SheetSchemaError,
    SheetUpdate,
)
from .sync import find_product_match, plan_divulgation_update, validate_import_row


@dataclass(frozen=True, slots=True)
class BackfillReport:
    scanned: int
    eligible: int
    planned: int
    already_queued: int
    not_eligible: int
    missing_product: int
    inactive_product: int
    invalid: int
    updates: tuple[SheetUpdate, ...]


def _yes(value: Any) -> bool:
    return normalize_unicode_text(value).casefold() == "sim" if isinstance(value, str) else False


def _blank_row(row: Sequence[Any]) -> bool:
    return not row or all(cell in (None, "") for cell in row)


def _existing_ids(rows: Sequence[tuple[Any, ...]]) -> set[str]:
    output: set[str] = set()
    for row in rows:
        if not isinstance(row, tuple) or len(row) > len(DIVULGATION_HEADERS):
            raise SheetSchemaError("Uma linha de Divulgação é inválida.")
        if _blank_row(row):
            continue
        cells = row + ("",) * (len(DIVULGATION_HEADERS) - len(row))
        share_id = normalize_unicode_text(cells[0]).casefold()
        if re.fullmatch(r"[0-9a-f]{32}", share_id) is None:
            raise SheetSchemaError("Um ID de Divulgação existente é inválido.")
        if share_id in output:
            raise SheetSchemaError("Há ID Divulgação duplicado.")
        output.add(share_id)
    return output


def plan_divulgation_backfill(
    import_rows: Sequence[tuple[Any, ...]],
    product_rows: Sequence[ProductRow],
    divulgation_rows: Sequence[tuple[Any, ...]],
    *,
    created_at: datetime,
    worksheet: str,
) -> BackfillReport:
    """Planeje itens antigos sem alterar Importações nem Produtos."""
    if not isinstance(import_rows, Sequence) or isinstance(import_rows, (str, bytes)):
        raise SheetSchemaError("As Importações do backfill são inválidas.")
    if not isinstance(product_rows, Sequence) or isinstance(product_rows, (str, bytes)):
        raise SheetSchemaError("Os Produtos do backfill são inválidos.")
    if not isinstance(divulgation_rows, Sequence) or isinstance(divulgation_rows, (str, bytes)):
        raise SheetSchemaError("A fila de Divulgação é inválida.")

    products = tuple(product_rows)
    if not all(isinstance(product, ProductRow) for product in products):
        raise SheetSchemaError("Os Produtos do backfill são inválidos.")

    existing_ids = _existing_ids(tuple(divulgation_rows))
    next_row = len(divulgation_rows) + 2
    scanned = eligible = already_queued = not_eligible = 0
    missing_product = inactive_product = invalid = 0
    updates: list[SheetUpdate] = []

    for row_number, row in enumerate(import_rows, start=2):
        if not isinstance(row, tuple):
            scanned += 1
            invalid += 1
            continue
        if _blank_row(row):
            continue
        scanned += 1

        # "Elegível" mede a intenção de publicação já registrada na planilha,
        # mesmo quando outro campo da linha está inválido. Assim o relatório
        # separa corretamente "candidato" de "válido para enfileirar".
        is_candidate = (
            len(row) > 25
            and row[25] == ImportStatus.PUBLICADO.value
            and _yes(row[1])
            and _yes(row[2])
        )
        if is_candidate:
            eligible += 1

        try:
            validate_import_row(row)
            record, default_write = ImportRecord.from_sheet_row(row_number, row)
        except (ArithmeticError, SheetSchemaError, TypeError, ValueError):
            invalid += 1
            continue

        if default_write is not None:
            invalid += 1
            continue
        if not is_candidate:
            not_eligible += 1
            continue
        try:
            product = find_product_match(record, products)
        except (AmbiguousProductMatchError, InvalidProductDataError, SheetSchemaError):
            invalid += 1
            continue
        if product is None:
            missing_product += 1
            continue
        if not _yes(product.active):
            inactive_product += 1
            continue

        try:
            update = plan_divulgation_update(
                record,
                product,
                existing_ids=existing_ids,
                row_number=next_row,
                created_at=created_at,
                worksheet=worksheet,
            )
        except (AmbiguousProductMatchError, InvalidProductDataError, SheetSchemaError):
            invalid += 1
            continue

        if update is None:
            already_queued += 1
            continue
        updates.append(update)
        existing_ids.add(str(update.values[0][0]))
        next_row += 1

    return BackfillReport(
        scanned=scanned,
        eligible=eligible,
        planned=len(updates),
        already_queued=already_queued,
        not_eligible=not_eligible,
        missing_product=missing_product,
        inactive_product=inactive_product,
        invalid=invalid,
        updates=tuple(updates),
    )
