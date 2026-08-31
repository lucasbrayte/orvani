"""Funções puras para assinar, mapear e adotar linhas de Produtos.

Este módulo não conhece gateways, credenciais ou arquivos: ele apenas produz
valores de domínio e planos de escrita que podem ser revisados pelo chamador.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from math import isfinite
import re
from threading import Lock, Semaphore
from typing import Any
from urllib.parse import urlsplit

from .config import (
    IMPORT_HEADERS,
    IMPORT_WORKSHEET,
    PARTNERS,
    PRODUCTS_HEADERS,
    PRODUCTS_WORKSHEET,
    normalize_unicode_text,
)
from .models import (
    AmbiguousProductMatchError,
    BlockedByStoreError,
    ConfigurationError,
    ImportRecord,
    ImportStatus,
    InvalidProductDataError,
    ProductNotFoundError,
    ProductRow,
    ProductSnapshot,
    SheetSchemaError,
    SheetUpdate,
    SyncItemResult,
    SyncReport,
    TemporaryFetchError,
    UnsupportedUrlError,
    UpdateMode,
    UnsafeUrlError,
)
from .security import normalize_url_for_signature, validate_https_url
from .sheets import SheetsGateway, batch_write, plan_new_import_row, read_table


_YES = "sim"
_PRODUCT_LAST_COLUMN = "T"
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", flags=re.ASCII)
_ISO_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
    flags=re.ASCII,
)
_PROCESSING_TIMEOUT = timedelta(minutes=30)
_MAX_WORKERS = 4


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
    if not isinstance(value, (datetime, str)):
        raise InvalidProductDataError("A validade da oferta existente é inválida.")
    try:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError
            point = value
        elif _ISO_DATE.fullmatch(value):
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
        invalid = InvalidProductDataError("A validade da oferta existente é inválida.")
    raise invalid from None


def _validate_worksheet(worksheet: Any) -> None:
    if not isinstance(worksheet, str) or not worksheet or worksheet.isspace() or len(worksheet) > 100 or any(character in worksheet for character in "[]:*?/\\!\x00\n\r"):
        raise SheetSchemaError("O nome da aba de Produtos é inválido.")


def _products_range(worksheet: str, row_number: int) -> str:
    if not isinstance(row_number, int) or isinstance(row_number, bool) or row_number < 2:
        raise SheetSchemaError("A linha de Produtos é inválida.")
    return "'" + worksheet.replace("'", "''") + f"'!A{row_number}:{_PRODUCT_LAST_COLUMN}{row_number}"


class SyncEngine:
    """Deterministic, side-effect-contained synchronization coordinator.

    Connectors are deliberately the only concurrent portion of a run.  Table
    reads, planning and writes stay on the caller thread, so a fake (and the
    Google gateway) never needs to be thread-safe.  A run first creates a
    complete immutable report; dry-runs simply decline to apply that plan.
    """

    def __init__(
        self,
        gateway: SheetsGateway,
        registry: Any,
        *,
        clock: Callable[[], datetime] | None = None,
        executor_factory: Callable[..., Executor] = ThreadPoolExecutor,
        sleep: Callable[[float], None] | None = None,
        max_workers: int = _MAX_WORKERS,
        import_worksheet: str = IMPORT_WORKSHEET,
        products_worksheet: str = PRODUCTS_WORKSHEET,
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int) or not 1 <= max_workers <= _MAX_WORKERS:
            raise ConfigurationError("O limite de concorrência é inválido.")
        self._gateway = gateway
        self._registry = registry
        self._clock = clock or (lambda: datetime.now(UTC))
        self._executor_factory = executor_factory
        self._sleep = sleep or (lambda _seconds: None)
        self._max_workers = max_workers
        self._imports = import_worksheet
        self._products = products_worksheet

    def run(self, mode: str, dry_run: bool = False) -> SyncReport:
        if mode not in {"pending", "full"}:
            raise ConfigurationError("O modo de sincronização é inválido.")
        if not isinstance(dry_run, bool):
            raise ConfigurationError("O modo dry-run é inválido.")
        now = _utc_now(self._clock())
        records, default_rows = self._read_import_records()
        product_rows = _read_product_rows(self._gateway, self._products)
        selected = tuple(record for record in records if _is_selected(record, mode, now))
        fetched = self._fetch_all(selected)

        import_updates: list[SheetUpdate] = list(default_rows)
        product_updates: list[SheetUpdate] = []
        results: list[SyncItemResult] = []
        working_products = list(product_rows)
        for record in selected:
            outcome = fetched[record.row_number]
            item, changes, publication = self._plan_record(record, outcome, working_products, now)
            results.append(item)
            import_updates.extend(changes)
            if publication:
                product_updates.extend(publication)
                _apply_product_plan(working_products, publication[0])

        import_updates = _dedupe_import_updates(import_updates)
        product_updates.sort(key=_sheet_update_row)
        report = SyncReport(
            items=tuple(sorted(results, key=lambda item: item.row_number)),
            planned_import_updates=tuple(import_updates),
            planned_product_updates=tuple(product_updates),
            dry_run=dry_run,
        )
        if not dry_run:
            # Cross-sheet writes cannot be atomic.  Publish first, then expose
            # PUBLICADO in Importações, so a failed product write is never
            # falsely represented as a published item.
            if report.planned_product_updates:
                batch_write(self._gateway, report.planned_product_updates, worksheet=self._products, headers=PRODUCTS_HEADERS)
            if report.planned_import_updates:
                batch_write(self._gateway, report.planned_import_updates, worksheet=self._imports, headers=IMPORT_HEADERS)
        return report

    def _read_import_records(self) -> tuple[tuple[ImportRecord, ...], tuple[SheetUpdate, ...]]:
        rows = read_table(self._gateway, self._imports, headers=IMPORT_HEADERS)
        records: list[ImportRecord] = []
        defaults: list[SheetUpdate] = []
        for offset, row in enumerate(rows, start=2):
            # Preserve physical sheet identity even for entirely blank lines.
            normalized = list(row) + [""] * (len(IMPORT_HEADERS) - len(row))
            default = plan_new_import_row(self._imports, offset, current_values=row)
            if default is not None:
                normalized = list(default.values[0])
                defaults.append(default)
            try:
                record, id_only = ImportRecord.from_sheet_row(offset, normalized)
            except (ValueError, TypeError, ArithmeticError) as error:
                # A malformed row must not abort unrelated rows.  There is no
                # safe ImportRecord to fetch, so it is intentionally omitted.
                continue
            if id_only is not None and default is None:
                defaults.append(id_only)
            records.append(record)
        return tuple(records), tuple(defaults)

    def _fetch_all(self, records: Sequence[ImportRecord]) -> dict[int, object]:
        locks: dict[str, Semaphore] = {}
        locks_guard = Lock()

        def fetch(record: ImportRecord) -> object:
            url = _fetch_url(record)
            hostname = _hostname(url)
            with locks_guard:
                gate = locks.setdefault(hostname, Semaphore(1))
            with gate:
                try:
                    connector = self._registry.select(url)
                    if _is_common_shopee(record, connector):
                        return _ShopeeConversion()
                    snapshot = connector.fetch(url)
                    if not isinstance(snapshot, ProductSnapshot):
                        raise InvalidProductDataError("O conector retornou um produto inválido.")
                    return snapshot
                except (UnsupportedUrlError, ProductNotFoundError, TemporaryFetchError, BlockedByStoreError, InvalidProductDataError) as error:
                    return error
                except Exception:
                    # Connector details may include raw URLs, headers or store
                    # messages, so never propagate them into the spreadsheet.
                    return TemporaryFetchError("Falha temporária na coleta.")

        if not records:
            return {}
        futures: dict[Future[object], int] = {}
        with self._executor_factory(max_workers=self._max_workers) as executor:
            for record in records:
                futures[executor.submit(fetch, record)] = record.row_number
            output: dict[int, object] = {}
            for future, row_number in futures.items():
                output[row_number] = future.result()
        return output

    def _plan_record(
        self,
        record: ImportRecord,
        outcome: object,
        product_rows: Sequence[ProductRow],
        now: datetime,
    ) -> tuple[SyncItemResult, tuple[SheetUpdate, ...], tuple[SheetUpdate, ...]]:
        if isinstance(outcome, _ShopeeConversion):
            target = replace(record, status=ImportStatus.AGUARDANDO_CONVERSAO, message="Aguardando conversão Shopee.", consecutive_attempts=0)
            changes = _state_updates(target, now, blocked=record.update_mode is UpdateMode.BLOQUEADO, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()
        if isinstance(outcome, TemporaryFetchError):
            attempts = record.consecutive_attempts + 1
            status = ImportStatus.ATENCAO if attempts >= 3 else record.status
            target = replace(record, status=status, message="Falha temporária na coleta.", consecutive_attempts=attempts)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()
        if isinstance(outcome, BlockedByStoreError):
            target = replace(record, status=ImportStatus.ATENCAO, message="A loja bloqueou a coleta pública.", consecutive_attempts=record.consecutive_attempts + 1)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()
        if isinstance(outcome, ProductNotFoundError):
            status = ImportStatus.ATENCAO if record.status is ImportStatus.PUBLICADO else ImportStatus.REVISAR
            target = replace(record, status=status, message="Produto indisponível para verificação.", consecutive_attempts=0)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()
        if isinstance(outcome, (UnsupportedUrlError, InvalidProductDataError)):
            target = replace(record, status=ImportStatus.ERRO, message="Dados ou URL incompatíveis.", consecutive_attempts=0)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()
        if not isinstance(outcome, ProductSnapshot):
            target = replace(record, status=ImportStatus.ATENCAO, message="Falha temporária na coleta.", consecutive_attempts=record.consecutive_attempts + 1)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()

        snapshot, partial = _merge_snapshot(record, outcome)
        if snapshot.available is False:
            status = ImportStatus.ATENCAO if record.status is ImportStatus.PUBLICADO else ImportStatus.REVISAR
            target = replace(record, status=status, message="Produto indisponível para verificação.", consecutive_attempts=0)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()
        signature = _snapshot_signature(snapshot)
        changed = signature != record.data_signature
        if record.update_mode is UpdateMode.BLOQUEADO:
            target = replace(record, status=ImportStatus.ATENCAO if partial else ImportStatus.REVISAR, message="Modo bloqueado: dados preservados.", consecutive_attempts=0)
            changes = _state_updates(target, now, blocked=True, worksheet=self._imports)
            return _result(record, target, bool(changes), False), changes, ()

        status = ImportStatus.ATENCAO if partial else ImportStatus.REVISAR
        message = "Imagens anteriores preservadas; revisão necessária." if partial else "Dados atualizados para revisão."
        target = _record_from_snapshot(record, snapshot, signature, status=status, message=message)
        publication: tuple[SheetUpdate, ...] = ()
        if _is_yes(record.publish) and not partial:
            target = replace(target, status=ImportStatus.PRONTO_PARA_PUBLICAR, message="Publicação planejada.")
            try:
                publication = plan_publication(snapshot, target, product_rows, worksheet=self._products)
            except AmbiguousProductMatchError:
                target = replace(target, status=ImportStatus.REVISAR, message="Correspondência de produto ambígua.")
            except InvalidProductDataError:
                target = replace(target, status=ImportStatus.ATENCAO, message="Dados de publicação exigem revisão.")
            else:
                target = replace(target, status=ImportStatus.PUBLICADO, message="Produto publicado.", last_published_url=record.affiliate_url or record.product_url)
        # A stable signature means no metadata rewrite; state/counter updates
        # still occur when their observable values changed.
        if changed:
            target = replace(target, last_checked_at=now.isoformat(), last_updated_at=now.isoformat())
            changes = _full_record_update(target, worksheet=self._imports)
        else:
            changes = _state_updates(target, now, blocked=False, worksheet=self._imports)
        return _result(record, target, bool(changes), bool(publication)), changes, publication


class _ShopeeConversion:
    pass


def _result(original: ImportRecord, target: ImportRecord, import_changed: bool, product_changed: bool) -> SyncItemResult:
    return SyncItemResult(original.row_number, original.status, target.status, target.message, import_changed, product_changed)


def _is_selected(record: ImportRecord, mode: str, now: datetime) -> bool:
    if not _is_yes(record.active) or record.status is ImportStatus.DESATIVADO:
        return False
    if record.update_mode is UpdateMode.BLOQUEADO:
        return True
    stale = record.status is ImportStatus.PROCESSANDO and _is_stale(record.last_checked_at, now)
    if mode == "full":
        return record.status is not ImportStatus.PROCESSANDO or stale
    if record.status in {ImportStatus.NOVO, ImportStatus.ATENCAO, ImportStatus.ERRO} or stale:
        return True
    if record.status is ImportStatus.AGUARDANDO_CONVERSAO:
        return bool(record.affiliate_url.strip())
    try:
        return record.link_signature is not None and record.link_signature != link_signature(_fetch_url(record))
    except UnsafeUrlError:
        return record.status is not ImportStatus.PUBLICADO


def _is_stale(value: str, now: datetime) -> bool:
    try:
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        instant = datetime.fromisoformat(text)
        if instant.tzinfo is None or instant.utcoffset() is None:
            return False
        return now - instant.astimezone(UTC) > _PROCESSING_TIMEOUT
    except (TypeError, ValueError, OverflowError):
        return False


def _fetch_url(record: ImportRecord) -> str:
    return record.affiliate_url.strip() or record.product_url.strip()


def _hostname(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "invalid").lower().rstrip(".")
    except Exception:
        return "invalid"


def _is_common_shopee(record: ImportRecord, connector: Any) -> bool:
    return not record.affiliate_url.strip() and (
        record.partner.strip().casefold() == "shopee" or getattr(connector, "partner_key", "") == "shopee"
    )


def _utc_now(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise ConfigurationError("O relógio de sincronização é inválido.")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _merge_snapshot(record: ImportRecord, snapshot: ProductSnapshot) -> tuple[ProductSnapshot, bool]:
    def choose(new: str, old: str) -> str:
        return new.strip() if isinstance(new, str) and new.strip() else old
    old_images = tuple(image for image in (record.image_1, record.image_2, record.image_3, record.image_4) if image)
    no_images = not snapshot.images
    images = snapshot.images or old_images
    merged = replace(
        snapshot,
        affiliate_url=record.affiliate_url or snapshot.affiliate_url,
        name=choose(snapshot.name, record.name), description=choose(snapshot.description, record.description),
        category=choose(snapshot.category, record.category), subcategory=choose(snapshot.subcategory, record.subcategory),
        product_type=choose(snapshot.product_type, record.product_type), images=images,
    )
    return merged, no_images


def _snapshot_signature(snapshot: ProductSnapshot) -> str:
    return data_signature({
        "partner": snapshot.partner, "external_id": snapshot.external_id, "catalog_id": snapshot.catalog_id,
        "affiliate_url": snapshot.affiliate_url, "name": snapshot.name, "description": snapshot.description,
        "current_price": snapshot.current_price, "previous_price": snapshot.previous_price, "currency": snapshot.currency,
        "category": snapshot.category, "subcategory": snapshot.subcategory, "product_type": snapshot.product_type,
        "coupon": snapshot.coupon, "coupon_expires_at": snapshot.coupon_expires_at, "images": snapshot.images,
        "available": snapshot.available,
    })


def _record_from_snapshot(record: ImportRecord, snapshot: ProductSnapshot, signature: str, *, status: ImportStatus, message: str) -> ImportRecord:
    images = tuple(snapshot.images) + ("",) * 4
    previous = snapshot.previous_price
    discount = str(calculate_discount(snapshot.current_price, previous)) if previous is not None else ""
    return replace(record, partner=snapshot.partner, external_id=snapshot.external_id, name=snapshot.name, description=snapshot.description,
        category=snapshot.category, subcategory=snapshot.subcategory, product_type=snapshot.product_type,
        current_price=snapshot.current_price, previous_price=previous, calculated_discount=discount,
        coupon=snapshot.coupon or "", coupon_expires_at=snapshot.coupon_expires_at.isoformat() if snapshot.coupon_expires_at else "",
        image_1=images[0], image_2=images[1], image_3=images[2], image_4=images[3],
        status=status, message=message, consecutive_attempts=0, data_signature=signature)


def _full_record_update(record: ImportRecord, *, worksheet: str = IMPORT_WORKSHEET) -> tuple[SheetUpdate, ...]:
    return (SheetUpdate(_import_range(record.row_number, "A", "AF", worksheet), (_record_values(record),)),)


def _state_updates(record: ImportRecord, now: datetime, *, blocked: bool, worksheet: str = IMPORT_WORKSHEET) -> tuple[SheetUpdate, ...]:
    # The two disjoint ranges intentionally omit all product metadata.  This is
    # the mechanical guarantee behind blocked/error preservation.
    return (
        SheetUpdate(_import_range(record.row_number, "Z", "AB", worksheet), ((record.status.value, record.message, record.consecutive_attempts),)),
        SheetUpdate(_import_range(record.row_number, "AE", "AE", worksheet), ((now,),)),
    )


def _import_range(row: int, first: str, last: str, worksheet: str = IMPORT_WORKSHEET) -> str:
    return "'" + worksheet.replace("'", "''") + f"'!{first}{row}:{last}{row}"


def _record_values(record: ImportRecord) -> tuple[Any, ...]:
    return (record.automation_id, record.active, record.publish, record.featured, record.order, record.update_mode.value,
        record.product_url, record.affiliate_url, record.partner, record.external_id, record.name, record.description,
        record.category, record.subcategory, record.product_type, record.current_price or "", record.previous_price or "",
        record.calculated_discount, record.coupon, record.coupon_expires_at, record.image_1, record.image_2, record.image_3,
        record.image_4, record.button_text, record.status.value, record.message, record.consecutive_attempts,
        record.last_published_url, record.data_signature, record.last_checked_at, record.last_updated_at)


def _dedupe_import_updates(updates: Sequence[SheetUpdate]) -> list[SheetUpdate]:
    # A full A:AF update already contains UUID/default values, so it supersedes
    # earlier provisional default writes for the same physical row.
    full_rows = { _sheet_update_row(update) for update in updates if ":AF" in update.range_name }
    return [update for update in updates if not (_sheet_update_row(update) in full_rows and ":AF" not in update.range_name)]


def _sheet_update_row(update: SheetUpdate) -> int:
    match = re.search(r"[A-Z]+([0-9]+)", update.range_name)
    if match is None:
        raise SheetSchemaError("A atualização planejada não tem linha válida.")
    return int(match.group(1))


def _read_product_rows(gateway: SheetsGateway, worksheet: str) -> tuple[ProductRow, ...]:
    raw = read_table(gateway, worksheet, headers=PRODUCTS_HEADERS)
    output: list[ProductRow] = []
    for row_number, row in enumerate(raw, start=2):
        cells = tuple(row) + ("",) * (20 - len(row))
        try:
            output.append(ProductRow(row_number, str(cells[0]), str(cells[1]), str(cells[2]), str(cells[3]), str(cells[4]), str(cells[5]), str(cells[6]),
                _product_decimal(cells[7]), _product_decimal(cells[8]), str(cells[9]), str(cells[10]), str(cells[11]), str(cells[12]), str(cells[13]),
                str(cells[14]), str(cells[15]), str(cells[16]), str(cells[17]), str(cells[18]), str(cells[19])))
        except (ValueError, ArithmeticError):
            continue
    return tuple(output)


def _product_decimal(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


def _apply_product_plan(rows: list[ProductRow], update: SheetUpdate) -> None:
    row_number = _sheet_update_row(update)
    values = update.values[0]
    candidate = ProductRow(row_number, *values)
    for index, row in enumerate(rows):
        if row.row_number == row_number:
            rows[index] = candidate
            return
    rows.append(candidate)
