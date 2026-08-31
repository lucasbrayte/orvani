"""Funções puras para assinar, mapear e adotar linhas de Produtos.

Este módulo não conhece gateways, credenciais ou arquivos: ele apenas produz
valores de domínio e planos de escrita que podem ser revisados pelo chamador.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any
from urllib.parse import urlsplit

from .config import PARTNERS, PRODUCTS_HEADERS, PRODUCTS_WORKSHEET, normalize_unicode_text
from .models import (
    AmbiguousProductMatchError,
    ImportRecord,
    InvalidProductDataError,
    ProductRow,
    ProductSnapshot,
    SheetSchemaError,
    SheetUpdate,
    UnsafeUrlError,
)
from .security import normalize_url_for_signature, validate_https_url


_YES = "sim"
_PRODUCT_LAST_COLUMN = "T"
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", flags=re.ASCII)
_ISO_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
    flags=re.ASCII,
)


def calculate_discount(current: Decimal, previous: Decimal) -> int:
    """Return the percentage discount, rounded to the nearest integer half-up."""
    _valid_price(current)
    _valid_price(previous)
    if previous <= current:
        raise InvalidProductDataError("O desconto exige um preço anterior maior.")
    percentage = (previous - current) * Decimal("100") / previous
    return int(percentage.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def data_signature(value: Any) -> str:
    """SHA-256 of a typed canonical JSON value.

    The public input contract is mappings with string keys, ``list``/``tuple``,
    and scalar ``None``, ``bool``, ``str``, ``int``, ``Decimal``, or
    ``datetime`` values. Naive datetimes are explicitly interpreted as UTC;
    aware datetimes are converted to UTC. Decimal values use fixed-point text.
    Sets, bytes, dataclasses, arbitrary objects, floats, and cyclic containers
    are rejected rather than receiving an unstable representation.
    """
    canonical = _canonical_value(value, active=set())
    encoded = json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def link_signature(url: str) -> str:
    """Sign a validated, normalized URL without ever echoing the input URL."""
    try:
        if not isinstance(url, str):
            raise ValueError("link não textual")
        parsed = urlsplit(url)
        if parsed.hostname is None:
            raise ValueError("link sem host")
        # The host is only an allowlist for shape validation here; this routine
        # never resolves or fetches it.
        validate_https_url(url, (parsed.hostname,))
        normalized = normalize_url_for_signature(url)
    except Exception:
        raise UnsafeUrlError("Link inválido para assinatura.") from None
    return sha256(normalized.encode("utf-8")).hexdigest()


def map_snapshot_to_product_values(
    snapshot: ProductSnapshot,
    import_record: ImportRecord,
    existing: ProductRow | None,
) -> tuple[Any, ...]:
    """Map one normalized snapshot to the immutable 20-column Produtos contract."""
    if not isinstance(snapshot, ProductSnapshot) or not isinstance(import_record, ImportRecord):
        raise InvalidProductDataError("Os dados de publicação são inválidos.")
    if existing is not None and not isinstance(existing, ProductRow):
        raise InvalidProductDataError("A linha existente de Produtos é inválida.")

    _valid_price(snapshot.current_price)
    has_promotion = snapshot.previous_price is not None
    if has_promotion:
        _valid_price(snapshot.previous_price)
        if snapshot.previous_price <= snapshot.current_price:
            has_promotion = False

    price = snapshot.previous_price if has_promotion else snapshot.current_price
    promotional_price: Decimal | str = snapshot.current_price if has_promotion else ""
    coupon = _text_or_blank(snapshot.coupon)
    expiry = snapshot.coupon_expires_at if coupon else ""
    if expiry and not isinstance(expiry, datetime):
        raise InvalidProductDataError("A validade do cupom é inválida.")

    images = _mapped_images(snapshot.images, existing)
    button_text = _button_text(import_record.button_text, snapshot.partner)
    values = (
        "Sim" if _is_yes(import_record.active) and _is_yes(import_record.publish) else "Não",
        _required_text(snapshot.product_type),
        _required_text(snapshot.partner),
        _required_text(snapshot.category),
        _required_text(snapshot.subcategory),
        _required_text(snapshot.name),
        _required_text(snapshot.description),
        price,
        promotional_price,
        coupon,
        expiry,
        _required_literal(snapshot.affiliate_url),
        button_text,
        existing.video_url if existing is not None else "",
        *images,
        _text_or_blank(import_record.order),
        _text_or_blank(import_record.featured),
    )
    if len(values) != len(PRODUCTS_HEADERS):
        raise AssertionError("contrato Produtos interno inválido")
    _validate_sheet_values(values)
    return values


def find_product_match(
    import_record: ImportRecord,
    product_rows: Sequence[ProductRow],
) -> ProductRow | None:
    """Find a unique product using the approved independent tier precedence."""
    if not isinstance(import_record, ImportRecord):
        raise InvalidProductDataError("O registro de Importações é inválido.")
    rows = _validated_product_rows(product_rows)

    for target in (import_record.last_published_url, import_record.affiliate_url):
        normalized_target = _normalized_link_or_none(target)
        if normalized_target is None:
            continue
        matches = tuple(
            row for row in rows
            if _normalized_link_or_none(row.affiliate_url) == normalized_target
        )
        match = _unique_match(matches)
        if match is not None:
            return match

    partner = _identity_part(import_record.partner)
    external_id = _identity_part(import_record.external_id)
    if not partner or not external_id:
        return None
    matches = tuple(
        row for row in rows
        if _identity_part(row.partner) == partner
        and _identity_part(row.reconstructed_external_id) == external_id
    )
    return _unique_match(matches)


def plan_publication(
    snapshot: ProductSnapshot,
    import_record: ImportRecord,
    product_rows: Sequence[ProductRow],
    *,
    worksheet: str = PRODUCTS_WORKSHEET,
) -> tuple[SheetUpdate, ...]:
    """Return zero or one safe A:T update for a reviewed publication.

    A non-approved record is intentionally a no-op. Existing Products rows are
    adopted in place; a new product is appended after the greatest valid row.
    """
    _validate_worksheet(worksheet)
    if not isinstance(snapshot, ProductSnapshot) or not isinstance(import_record, ImportRecord):
        raise InvalidProductDataError("Os dados de publicação são inválidos.")
    rows = _validated_product_rows(product_rows)
    if not _is_yes(import_record.publish):
        return ()
    existing = find_product_match(import_record, rows)
    values = map_snapshot_to_product_values(snapshot, import_record, existing)
    if existing is not None:
        if _publication_values_equal(values, _product_row_values(existing)):
            return ()
        row_number = existing.row_number
    else:
        row_number = max((row.row_number for row in rows), default=1) + 1
    range_name = _products_range(worksheet, row_number)
    return (SheetUpdate(range_name, (values,)),)


def _canonical_value(value: Any, *, active: set[int]) -> list[Any]:
    if value is None:
        return ["none"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise InvalidProductDataError("A assinatura contém Decimal inválido.")
        return ["decimal", format(value, "f")]
    if isinstance(value, datetime):
        point = (
            value.replace(tzinfo=UTC)
            if value.tzinfo is None or value.utcoffset() is None
            else value.astimezone(UTC)
        )
        return ["datetime", point.isoformat(timespec="microseconds").replace("+00:00", "Z")]
    if isinstance(value, float):
        if not isfinite(value):
            raise InvalidProductDataError("A assinatura contém número inválido.")
        raise InvalidProductDataError("A assinatura não aceita float.")
    if isinstance(value, Mapping):
        return _canonical_mapping(value, active)
    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in active:
            raise InvalidProductDataError("A assinatura contém estrutura cíclica.")
        active.add(identity)
        try:
            kind = "list" if isinstance(value, list) else "tuple"
            return [kind, [_canonical_value(item, active=active) for item in value]]
        finally:
            active.remove(identity)
    raise InvalidProductDataError("A assinatura contém um tipo não suportado.")


def _canonical_mapping(value: Mapping[Any, Any], active: set[int]) -> list[Any]:
    if not all(isinstance(key, str) for key in value):
        raise InvalidProductDataError("A assinatura exige chaves textuais.")
    identity = id(value)
    if identity in active:
        raise InvalidProductDataError("A assinatura contém estrutura cíclica.")
    active.add(identity)
    try:
        return [
            "mapping",
            [[key, _canonical_value(value[key], active=active)] for key in sorted(value)],
        ]
    finally:
        active.remove(identity)


def _valid_price(value: Any) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= Decimal("0"):
        raise InvalidProductDataError("O preço deve ser Decimal finito e positivo.")


def _mapped_images(images: Any, existing: ProductRow | None) -> tuple[str, str, str, str]:
    if not isinstance(images, tuple) or len(images) > 4:
        raise InvalidProductDataError("As imagens do produto são inválidas.")
    replacement = _unique_normalized_images(images)
    preserved = tuple(_normalized_https_image_or_none(image) or "" for image in _existing_images(existing))
    if replacement:
        mapped = replacement + list(preserved[len(replacement):])
        seen: set[str] = set()
        mapped = [image if not image or image not in seen else "" for image in mapped]
        for image in mapped:
            if image:
                seen.add(image)
    else:
        mapped = list(preserved)
    if not mapped[0]:
        raise InvalidProductDataError("Produtos publicados exigem uma imagem HTTPS válida.")
    mapped = (mapped + [""] * 4)[:4]
    return mapped[0], mapped[1], mapped[2], mapped[3]


def _unique_normalized_images(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = _normalized_https_image_or_none(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _normalized_https_image_or_none(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.hostname is None:
            raise ValueError
        validate_https_url(value, (parsed.hostname,))
    except Exception:
        return None
    return normalize_url_for_signature(value)


def _existing_images(existing: ProductRow | None) -> tuple[str, str, str, str]:
    if existing is None:
        return ("", "", "", "")
    return (existing.image_1, existing.image_2, existing.image_3, existing.image_4)


def _button_text(value: Any, partner: str) -> str:
    custom = _text_or_blank(value)
    if custom:
        return custom
    configuration = PARTNERS.get(partner)
    return f"Ver oferta na {configuration.display_name}" if configuration else "Ver oferta"


def _text_or_blank(value: Any) -> str:
    return normalize_unicode_text(value) if isinstance(value, str) else ""


def _required_text(value: Any) -> str:
    result = _text_or_blank(value)
    if not result:
        raise InvalidProductDataError("O produto contém texto obrigatório ausente.")
    return result


def _required_literal(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidProductDataError("O produto contém texto obrigatório ausente.")
    return value


def _is_yes(value: Any) -> bool:
    return _text_or_blank(value).casefold() == _YES


def _validate_sheet_values(values: Sequence[Any]) -> None:
    for value in values:
        if isinstance(value, Decimal):
            _valid_price(value)
        elif isinstance(value, float) and not isfinite(value):
            raise InvalidProductDataError("O valor de planilha é inválido.")


def _normalized_link_or_none(value: Any) -> str | None:
    try:
        if not isinstance(value, str) or not value.strip():
            return None
        parsed = urlsplit(value)
        if parsed.hostname is None:
            return None
        validate_https_url(value, (parsed.hostname,))
        return normalize_url_for_signature(value)
    except Exception:
        return None


def _identity_part(value: Any) -> str:
    return _text_or_blank(value).casefold()


def _validate_product_row_identities(rows: Sequence[ProductRow]) -> None:
    identities: set[int] = set()
    for row in rows:
        if not isinstance(row, ProductRow) or not isinstance(row.row_number, int) or isinstance(row.row_number, bool) or row.row_number < 2:
            raise AmbiguousProductMatchError("A identidade de uma linha de Produtos é inválida.")
        if row.row_number in identities:
            raise AmbiguousProductMatchError("Há linhas de Produtos com identidade duplicada.")
        identities.add(row.row_number)


def _validated_product_rows(product_rows: Any) -> tuple[ProductRow, ...]:
    if not isinstance(product_rows, Sequence) or isinstance(product_rows, (str, bytes)):
        raise InvalidProductDataError("As linhas de Produtos são inválidas.")
    rows = tuple(product_rows)
    if not all(isinstance(row, ProductRow) for row in rows):
        raise InvalidProductDataError("As linhas de Produtos são inválidas.")
    _validate_product_row_identities(rows)
    return rows


def _unique_match(matches: Sequence[ProductRow]) -> ProductRow | None:
    if len(matches) > 1:
        raise AmbiguousProductMatchError("A correspondência de Produtos é ambígua.")
    return matches[0] if matches else None


def _product_row_values(row: ProductRow) -> tuple[Any, ...]:
    return (
        row.active, row.product_type, row.partner, row.category, row.subcategory,
        row.name, row.description, row.price, row.promotional_price, row.coupon,
        row.offer_expires_at, row.affiliate_url, row.button_text, row.video_url,
        row.image_1, row.image_2, row.image_3, row.image_4, row.order, row.featured,
    )


def _publication_values_equal(desired: Sequence[Any], existing: Sequence[Any]) -> bool:
    if len(desired) != len(PRODUCTS_HEADERS) or len(existing) != len(PRODUCTS_HEADERS):
        raise InvalidProductDataError("Os valores de Produtos são inválidos.")
    for index, (wanted, stored) in enumerate(zip(desired, existing, strict=True)):
        if index == 10:
            if _canonical_offer_expiry(wanted) != _canonical_offer_expiry(stored):
                return False
        elif wanted != stored:
            return False
    return True


def _canonical_offer_expiry(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        point = value.replace(tzinfo=UTC) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(UTC)
        return point.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if not isinstance(value, str):
        raise InvalidProductDataError("A validade da oferta existente é inválida.")
    try:
        if _ISO_DATE.fullmatch(value):
            day = date.fromisoformat(value)
            point = datetime(day.year, day.month, day.day, tzinfo=UTC)
        elif _ISO_TIMESTAMP.fullmatch(value):
            parsed = value[:-1] + "+00:00" if value.endswith("Z") else value
            point = datetime.fromisoformat(parsed)
            if point.tzinfo is None or point.utcoffset() is None:
                raise ValueError
        else:
            raise ValueError
        return point.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        raise InvalidProductDataError("A validade da oferta existente é inválida.") from None


def _validate_worksheet(worksheet: Any) -> None:
    if not isinstance(worksheet, str) or not worksheet or worksheet.isspace() or len(worksheet) > 100 or any(character in worksheet for character in "[]:*?/\\!\x00\n\r"):
        raise SheetSchemaError("O nome da aba de Produtos é inválido.")


def _products_range(worksheet: str, row_number: int) -> str:
    if not isinstance(row_number, int) or isinstance(row_number, bool) or row_number < 2:
        raise SheetSchemaError("A linha de Produtos é inválida.")
    return "'" + worksheet.replace("'", "''") + f"'!A{row_number}:{_PRODUCT_LAST_COLUMN}{row_number}"
