"""Contratos puros de mapeamento e adoção de Produtos."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from threading import Event, Lock, Thread
from uuid import RFC_4122, UUID

import pytest

from automation.config import PRODUCTS_HEADERS
from automation.models import (
    AmbiguousProductMatchError,
    BlockedByStoreError,
    ConfigurationError,
    ImportRecord,
    InvalidProductDataError,
    ProductNotFoundError,
    ProductRow,
    ProductSnapshot,
    ImportStatus,
    SheetSchemaError,
    TemporaryFetchError,
    UnsupportedUrlError,
)
from automation.sync import (
    _canonical_offer_expiry,
    calculate_discount,
    data_signature,
    find_product_match,
    link_signature,
    map_snapshot_to_product_values,
    plan_publication,
)


def test_sync_engine_rejects_an_unknown_execution_mode():
    """Catches accepting a typo that could silently broaden a queue run."""
    from automation.sync import SyncEngine

    with pytest.raises(Exception):
        SyncEngine(object(), object()).run("everything", dry_run=True)


def test_sync_engine_moves_a_new_affiliate_row_to_review_without_writing_in_dry_run():
    """Catches a successful fetch that forgets the NOVO -> REVISAR transition."""
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS
    from automation.sync import SyncEngine, _record_values

    class Connector:
        partner_key = "mercado_livre"

        def fetch(self, _url):
            return _snapshot()

    class Registry:
        def select(self, _url):
            return Connector()

    imported = _record(status=ImportStatus.NOVO, publish="Não", data_signature="")
    sheets = FakeSheetsGateway(
        sheets=(
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 20}}},
        ),
        values={
            _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), list(_record_values(imported))],
            _quoted("Produtos", "A1:T"): [list(PRODUCTS_HEADERS)],
        },
    )

    report = SyncEngine(sheets, Registry(), clock=lambda: datetime(2026, 8, 30, 13, tzinfo=UTC)).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.REVISAR
    assert sheets.value_writes == []


def test_sync_engine_turns_the_third_temporary_failure_into_attention_without_product_plan():
    """Catches overwriting a published snapshot on retry exhaustion."""
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS
    from automation.models import TemporaryFetchError
    from automation.sync import SyncEngine, _record_values

    class Registry:
        def select(self, _url):
            class Connector:
                def fetch(self, _url):
                    raise TemporaryFetchError("private https://secret.invalid/?token=no")
            return Connector()

    imported = _record(status=ImportStatus.PUBLICADO, consecutive_attempts=2)
    sheets = FakeSheetsGateway(
        sheets=(
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 20}}},
        ),
        values={
            _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), list(_record_values(imported))],
            _quoted("Produtos", "A1:T"): [list(PRODUCTS_HEADERS), list(map_snapshot_to_product_values(_snapshot(), imported, None))],
        },
    )

    report = SyncEngine(sheets, Registry()).run("full", dry_run=True)

    assert report.final_status(2) is ImportStatus.ATENCAO
    assert report.planned_product_updates == ()
    assert "secret" not in report.items[0].message


def test_sync_engine_aborts_before_fetch_or_checkpoint_for_malformed_product_row():
    """Catches silently dropping a malformed Produtos row before an append."""
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS
    from automation.models import SheetSchemaError
    from automation.sync import SyncEngine, _record_values

    calls = []
    class Registry:
        def select(self, _url):
            calls.append("select")
            return object()

    sheets = FakeSheetsGateway(
        sheets=(
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 20}}},
        ),
        values={
            _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), list(_record_values(_record(status=ImportStatus.NOVO)))],
            _quoted("Produtos", "A1:T"): [list(PRODUCTS_HEADERS), ["Sim", "tipo", "partner", "cat", "sub", "name", "desc", "not-price"]],
        },
    )

    with pytest.raises(SheetSchemaError):
        SyncEngine(sheets, Registry()).run("pending", dry_run=False)

    assert calls == [] and sheets.value_writes == []


@pytest.mark.parametrize("mode,dry_run", [("pending", True), ("pending", False)])
def test_sync_engine_publishes_an_approved_snapshot_without_name_error(mode, dry_run):
    """Catches the live adoption path using an out-of-scope planning variable."""
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS
    from automation.sync import SyncEngine, _record_values

    class Registry:
        def select(self, _url):
            class Connector:
                partner_key = "mercado_livre"
                def fetch(self, _url): return _snapshot()
            return Connector()

    imported = _record(status=ImportStatus.NOVO, publish="Sim", data_signature="")
    sheets = FakeSheetsGateway(
        sheets=(
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 20, "columnCount": 20}}},
        ), values={_quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), list(_record_values(imported))], _quoted("Produtos", "A1:T"): [list(PRODUCTS_HEADERS)]},
    )
    report = SyncEngine(sheets, Registry()).run(mode, dry_run=dry_run)
    assert report.final_status(2) is ImportStatus.PUBLICADO
    assert report.planned_product_updates[0].range_name == "'Produtos'!A2:T2"
    assert (not sheets.value_writes) is dry_run


@pytest.mark.parametrize("checked,expected", [
    ("2026-08-30T11:30:00Z", True), ("2026-08-30T11:30:01Z", False),
    ("", True), ("not-a-date", True), (46264.47, True),
])
def test_processing_staleness_recovers_missing_invalid_serial_and_exact_boundary(checked, expected):
    """Catches PROCESSANDO rows becoming permanently stuck on bad timestamps."""
    from automation.sync import _is_stale
    assert _is_stale(checked, datetime(2026, 8, 30, 12, tzinfo=UTC)) is expected


class _RaisingTzinfo(tzinfo):
    def __init__(self, error_type):
        self.error_type = error_type

    def utcoffset(self, _value):
        raise self.error_type("secret tzinfo failure")

    def dst(self, _value):
        return None


def _record(**changes):
    values = [
        "auto-1", "Sim", "Sim", "Não", "9", "Automático",
        "https://www.mercadolivre.com.br/item/MLB123",
        "https://meli.la/current?b=2&a=1", "mercado_livre", "MLB123",
        "Nome importado", "Descrição importada", "Eletrônicos", "Áudio", "Físico",
        Decimal("149.90"), Decimal("199.90"), "25", "CUPOM", "2026-09-01",
        "", "", "", "", "", "REVISAR", "", 0,
        "https://meli.la/old", "", "", "",
    ]
    record, planned = ImportRecord.from_sheet_row(4, values)
    assert planned is None
    return replace(record, **changes)


def _snapshot(**changes):
    fields = {
        "partner": "mercado_livre",
        "external_id": "MLB123",
        "catalog_id": None,
        "source_url": "https://www.mercadolivre.com.br/item/MLB123",
        "affiliate_url": "https://meli.la/current?b=2&a=1",
        "name": "Produto de teste",
        "description": "Descrição de teste",
        "current_price": Decimal("149.90"),
        "previous_price": Decimal("199.90"),
        "currency": "BRL",
        "category": "Eletrônicos",
        "subcategory": "Áudio",
        "product_type": "Físico",
        "coupon": "CUPOM",
        "coupon_expires_at": datetime(2026, 9, 1, tzinfo=UTC),
        "images": tuple(f"https://images.example/{number}.jpg" for number in range(1, 5)),
        "available": True,
        "fetched_at": datetime(2026, 8, 30, 12, tzinfo=UTC),
    }
    fields.update(changes)
    return ProductSnapshot(**fields)


def _product_values(row):
    return [
        row.active, row.product_type, row.partner, row.category, row.subcategory,
        row.name, row.description, row.price, row.promotional_price, row.coupon,
        row.offer_expires_at, row.affiliate_url, row.button_text, row.video_url,
        row.image_1, row.image_2, row.image_3, row.image_4, row.order, row.featured,
    ]


def _sync_gateway(records=(), products=(), *, raw_imports=None, raw_products=None, gateway_type=None):
    from conftest import FakeSheetsGateway, _quoted
    from automation.config import IMPORT_HEADERS
    from automation.sync import _record_values

    gateway_type = gateway_type or FakeSheetsGateway
    import_rows = raw_imports if raw_imports is not None else [list(_record_values(record)) for record in records]
    product_rows = raw_products if raw_products is not None else [_product_values(row) for row in products]
    return gateway_type(
        sheets=(
            {"properties": {"sheetId": 1, "title": "Importações", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 32}}},
            {"properties": {"sheetId": 2, "title": "Produtos", "sheetType": "GRID", "gridProperties": {"rowCount": 100, "columnCount": 20}}},
        ),
        values={
            _quoted("Importações", "A1:AF"): [list(IMPORT_HEADERS), *import_rows],
            _quoted("Produtos", "A1:T"): [list(PRODUCTS_HEADERS), *product_rows],
        },
    )


class _OutcomeRegistry:
    def __init__(self, outcomes, *, partner_for_url=None, select_error=None):
        self.outcomes = outcomes
        self.partner_for_url = partner_for_url or {}
        self.select_error = select_error
        self.selected = []
        self.fetched = []

    def select(self, url):
        self.selected.append(url)
        if self.select_error is not None:
            raise self.select_error
        registry = self

        class Connector:
            partner_key = registry.partner_for_url.get(url, "mercado_livre")

            def fetch(self, fetched_url):
                registry.fetched.append(fetched_url)
                outcome = registry.outcomes[fetched_url]
                if callable(outcome):
                    outcome = outcome()
                if isinstance(outcome, Exception):
                    raise outcome
                return replace(outcome, affiliate_url=fetched_url)

        return Connector()


def _row(row_number=7, **changes):
    fields = {
        "row_number": row_number,
        "active": "Sim",
        "product_type": "Físico",
        "partner": "mercado_livre",
        "category": "Eletrônicos",
        "subcategory": "Áudio",
        "name": "Produto anterior",
        "description": "Descrição anterior",
        "price": Decimal("199.90"),
        "promotional_price": Decimal("149.90"),
        "coupon": "CUPOM",
        "offer_expires_at": "2026-09-01T00:00:00Z",
        "affiliate_url": "https://meli.la/old",
        "button_text": "Ver oferta na Mercado Livre",
        "video_url": "https://youtube.example/watch?v=keep",
        "image_1": "https://images.example/old-1.jpg",
        "image_2": "https://images.example/old-2.jpg",
        "image_3": "https://images.example/old-3.jpg",
        "image_4": "https://images.example/old-4.jpg",
        "order": "9",
        "featured": "Não",
        "reconstructed_external_id": "MLB123",
        "reconstructed_catalog_id": None,
    }
    fields.update(changes)
    return ProductRow(**fields)


@pytest.mark.parametrize("mode", ["everything", "Pending", "", None, True, 1])
def test_sync_engine_rejects_invalid_mode_before_reading_sheets(mode):
    """Catches invalid modes reaching a gateway or broadening queue selection."""
    from automation.sync import SyncEngine

    with pytest.raises(ConfigurationError):
        SyncEngine(object(), object()).run(mode, dry_run=True)


@pytest.mark.parametrize("dry_run", [None, 0, 1, "true", object()])
def test_sync_engine_rejects_non_boolean_dry_run_before_reading_sheets(dry_run):
    """Catches truthy values accidentally disabling the live-write gate."""
    from automation.sync import SyncEngine

    with pytest.raises(ConfigurationError):
        SyncEngine(object(), object()).run("pending", dry_run=dry_run)


@pytest.mark.parametrize("column,value", [
    (1, True), (2, "Talvez"), (3, "talvez"), (4, -1), (5, "Manual"),
    (15, "149.90"), (27, -1), (30, []),
])
def test_sync_engine_aborts_before_fetch_for_malformed_import_scalar(column, value):
    """Catches coercing malformed operational cells into a fetchable record."""
    from automation.sync import SyncEngine, _record_values

    raw = list(_record_values(_record(status=ImportStatus.NOVO)))
    raw[column] = value
    registry = _OutcomeRegistry({})
    sheets = _sync_gateway(raw_imports=[raw])

    with pytest.raises(SheetSchemaError):
        SyncEngine(sheets, registry).run("pending", dry_run=False)

    assert registry.selected == [] and sheets.value_writes == []


@pytest.mark.parametrize("column,value", [
    (0, True), (7, "199.90"), (8, float("nan")), (10, 1),
    (10, "2026-09-01junk"), (18, -1), (19, False),
])
def test_sync_engine_aborts_before_fetch_for_malformed_product_scalar(column, value):
    """Catches a malformed catalog row being ignored or overwritten later."""
    from automation.sync import SyncEngine

    raw = _product_values(_row())
    raw[column] = value
    registry = _OutcomeRegistry({})
    sheets = _sync_gateway(
        records=(_record(status=ImportStatus.NOVO),), raw_products=[raw]
    )

    with pytest.raises(SheetSchemaError):
        SyncEngine(sheets, registry).run("pending", dry_run=False)

    assert registry.selected == [] and sheets.value_writes == []


def test_sync_engine_accepts_the_first_valid_google_date_serial_in_products():
    """Catches an off-by-one rejection after excluding pre-1900 serial dates."""
    from automation.sync import SyncEngine

    raw = _product_values(_row())
    raw[10] = 2
    report = SyncEngine(_sync_gateway(raw_products=[raw]), _OutcomeRegistry({})).run(
        "pending", dry_run=True
    )

    assert report.items == ()


def test_sync_engine_preserves_old_images_and_requires_attention_for_partly_invalid_output():
    """Catches one valid fresh image masking invalid output and erasing prior images."""
    from automation.sync import SyncEngine

    record = _record(
        status=ImportStatus.NOVO,
        publish="Não",
        image_1="https://images.example/old-1.jpg",
        image_2="https://images.example/old-2.jpg",
        image_3="https://images.example/old-3.jpg",
        image_4="https://images.example/old-4.jpg",
    )
    url = record.affiliate_url
    registry = _OutcomeRegistry({url: _snapshot(images=("https://images.example/new.jpg", "http://bad.example/image.jpg"))})

    report = SyncEngine(_sync_gateway(records=(record,)), registry).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.ATENCAO
    values = report.planned_import_updates[0].values[0]
    assert values[20:24] == (
        "https://images.example/new.jpg",
        "https://images.example/old-2.jpg",
        "https://images.example/old-3.jpg",
        "https://images.example/old-4.jpg",
    )


def test_blank_id_and_terminal_error_are_combined_in_one_deterministic_full_row_plan():
    """Catches the default-ID range overwriting the terminal state in the same batch."""
    from automation.sync import SyncEngine, _record_values

    raw = list(_record_values(_record(status=ImportStatus.NOVO, automation_id="")))
    dry_registry = _OutcomeRegistry({}, select_error=UnsupportedUrlError("secret URL"))
    live_registry = _OutcomeRegistry({}, select_error=UnsupportedUrlError("secret URL"))
    fixed_now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    dry = SyncEngine(
        _sync_gateway(raw_imports=[raw]), dry_registry, clock=lambda: fixed_now
    ).run("pending", dry_run=True)
    live = SyncEngine(
        _sync_gateway(raw_imports=[raw]), live_registry, clock=lambda: fixed_now
    ).run("pending", dry_run=False)

    assert len(dry.planned_import_updates) == len(live.planned_import_updates) == 1
    dry_values = dry.planned_import_updates[0].values[0]
    live_values = live.planned_import_updates[0].values[0]
    assert dry_values == live_values
    generated = UUID(dry_values[0])
    assert generated.version == 4 and generated.variant == RFC_4122
    assert dry_values[25:28] == (ImportStatus.ERRO.value, "Dados ou URL incompatíveis.", 0)


def test_two_approved_imports_for_one_external_identity_plan_one_product_row_write():
    """Catches same-run identity adoption emitting duplicate/conflicting A:T updates."""
    from automation.sync import SyncEngine

    first = _record(
        status=ImportStatus.NOVO, last_published_url="",
        affiliate_url="https://meli.la/first", external_id="MLB1234567890",
    )
    second = replace(
        first, row_number=5, automation_id="auto-2", affiliate_url="https://meli.la/second"
    )
    outcomes = {
        first.affiliate_url: _snapshot(external_id="MLB1234567890", affiliate_url=first.affiliate_url),
        second.affiliate_url: _snapshot(external_id="MLB1234567890", affiliate_url=second.affiliate_url),
    }

    report = SyncEngine(_sync_gateway(records=(first, second)), _OutcomeRegistry(outcomes)).run(
        "pending", dry_run=True
    )

    assert [item.final_status for item in report.items] == [ImportStatus.PUBLICADO, ImportStatus.PUBLICADO]
    assert [update.range_name for update in report.planned_product_updates] == ["'Produtos'!A2:T2"]


@pytest.mark.parametrize("partner,external_id,existing_url,current_url", [
    ("mercado_livre", "MLB1234567890", "https://www.mercadolivre.com.br/item/MLB1234567890", "https://meli.la/new-link"),
    ("shopee", "123.456", "https://shopee.com.br/item-i.123.456", "https://s.shopee.com.br/new-link"),
    ("shein", "123", "https://br.shein.com/product-p-123.html", "https://br.shein.com/new-link"),
    ("tiktok_shop", "123", "https://shop.tiktok.test/product/123", "https://shop.tiktok.test/new-link"),
])
def test_product_identity_reconstructed_from_partner_url_prevents_append(partner, external_id, existing_url, current_url):
    """Catches losing safely reconstructible existing identities during adoption."""
    from automation.sync import SyncEngine

    existing = _row(
        row_number=2,
        partner=partner,
        affiliate_url=existing_url,
        reconstructed_external_id=None,
    )
    record = _record(
        status=ImportStatus.NOVO, last_published_url="",
        partner=partner, affiliate_url=current_url, external_id=external_id,
    )
    registry = _OutcomeRegistry(
        {record.affiliate_url: _snapshot(partner=partner, external_id=external_id)},
        partner_for_url={record.affiliate_url: partner},
    )

    report = SyncEngine(_sync_gateway(records=(record,), products=(existing,)), registry).run(
        "pending", dry_run=True
    )

    assert report.planned_product_updates[0].range_name == "'Produtos'!A2:T2"


def test_sync_engine_preserves_all_old_images_when_output_has_none():
    """Catches a temporarily empty image collection clearing verified URLs."""
    from automation.sync import SyncEngine

    old_images = tuple(f"https://images.example/old-{number}.jpg" for number in range(1, 5))
    record = _record(
        status=ImportStatus.NOVO, publish="Não",
        image_1=old_images[0], image_2=old_images[1], image_3=old_images[2], image_4=old_images[3],
    )
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({record.affiliate_url: _snapshot(images=())}),
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.ATENCAO
    assert report.planned_import_updates[0].values[0][20:24] == old_images


def test_full_mode_selects_only_active_published_rows():
    """Catches a catalog refresh draining review or retry queue states."""
    from automation.sync import SyncEngine

    published = _record(status=ImportStatus.PUBLICADO, affiliate_url="https://meli.la/published")
    review = replace(published, automation_id="review", status=ImportStatus.REVISAR, affiliate_url="https://meli.la/review")
    attention = replace(published, automation_id="attention", status=ImportStatus.ATENCAO, affiliate_url="https://meli.la/attention")
    inactive = replace(published, automation_id="inactive", active="Não", affiliate_url="https://meli.la/inactive")
    registry = _OutcomeRegistry({published.affiliate_url: _snapshot()})

    report = SyncEngine(_sync_gateway(records=(published, review, attention, inactive)), registry).run(
        "full", dry_run=True
    )

    assert registry.selected == [published.affiliate_url]
    assert [item.row_number for item in report.items] == [2]


def test_pending_selects_new_and_stale_processing_but_not_fresh_processing():
    """Catches interrupted rows staying stuck or active work being duplicated."""
    from automation.sync import SyncEngine

    new = _record(status=ImportStatus.NOVO, affiliate_url="https://meli.la/new")
    stale = replace(new, automation_id="stale", status=ImportStatus.PROCESSANDO, affiliate_url="https://meli.la/stale", last_checked_at="bad-date")
    fresh = replace(new, automation_id="fresh", status=ImportStatus.PROCESSANDO, affiliate_url="https://meli.la/fresh", last_checked_at="2026-08-31T11:45:01Z")
    outcomes = {new.affiliate_url: _snapshot(), stale.affiliate_url: _snapshot()}
    registry = _OutcomeRegistry(outcomes)

    report = SyncEngine(
        _sync_gateway(records=(new, stale, fresh)), registry,
        clock=lambda: datetime(2026, 8, 31, 12, tzinfo=UTC),
    ).run("pending", dry_run=True)

    assert registry.selected == [new.affiliate_url, stale.affiliate_url]
    assert [item.row_number for item in report.items] == [2, 3]


def test_pending_retries_attention_and_error_only_below_three_attempts():
    """Catches exhausted failures being retried forever."""
    from automation.sync import SyncEngine

    base = _record(status=ImportStatus.ATENCAO, affiliate_url="https://meli.la/attention-2", consecutive_attempts=2)
    retry_error = replace(base, automation_id="error", status=ImportStatus.ERRO, affiliate_url="https://meli.la/error-1", consecutive_attempts=1)
    exhausted = replace(base, automation_id="done", affiliate_url="https://meli.la/attention-3", consecutive_attempts=3)
    outcomes = {
        base.affiliate_url: TemporaryFetchError("temporary"),
        retry_error.affiliate_url: TemporaryFetchError("temporary"),
    }
    registry = _OutcomeRegistry(outcomes)

    report = SyncEngine(_sync_gateway(records=(base, retry_error, exhausted)), registry).run(
        "pending", dry_run=True
    )

    assert registry.selected == [base.affiliate_url, retry_error.affiliate_url]
    assert [item.row_number for item in report.items] == [2, 3]


def test_pending_conversion_requires_an_affiliate_link_before_refetch():
    """Catches a manual-conversion row refetching its ordinary product link."""
    from automation.sync import SyncEngine

    waiting = _record(
        status=ImportStatus.AGUARDANDO_CONVERSAO, partner="shopee",
        product_url="https://shopee.com.br/product/1/2", affiliate_url="",
    )
    converted = replace(waiting, automation_id="converted", affiliate_url="https://s.shopee.com.br/converted")
    registry = _OutcomeRegistry(
        {converted.affiliate_url: _snapshot(partner="shopee")},
        partner_for_url={converted.affiliate_url: "shopee"},
    )

    report = SyncEngine(_sync_gateway(records=(waiting, converted)), registry).run(
        "pending", dry_run=True
    )

    assert registry.selected == [converted.affiliate_url]
    assert [item.row_number for item in report.items] == [3]


def test_pending_review_and_ready_rows_require_human_publication_approval():
    """Catches unapproved review records publishing themselves."""
    from automation.sync import SyncEngine

    review_no = _record(status=ImportStatus.REVISAR, publish="Não", affiliate_url="https://meli.la/review-no")
    review_yes = replace(review_no, automation_id="review-yes", publish="Sim", affiliate_url="https://meli.la/review-yes")
    ready_no = replace(review_no, automation_id="ready-no", status=ImportStatus.PRONTO_PARA_PUBLICAR, affiliate_url="https://meli.la/ready-no")
    ready_yes = replace(ready_no, automation_id="ready-yes", publish="Sim", affiliate_url="https://meli.la/ready-yes")
    outcomes = {review_yes.affiliate_url: _snapshot(), ready_yes.affiliate_url: _snapshot()}
    registry = _OutcomeRegistry(outcomes)

    SyncEngine(_sync_gateway(records=(review_no, review_yes, ready_no, ready_yes)), registry).run(
        "pending", dry_run=True
    )

    assert registry.selected == [review_yes.affiliate_url, ready_yes.affiliate_url]


def test_pending_published_row_is_selected_only_when_link_signature_changes():
    """Catches hourly work refreshing an unchanged published catalog row."""
    from automation.sync import SyncEngine, _signature_envelope

    unchanged = _record(status=ImportStatus.PUBLICADO, affiliate_url="https://meli.la/stable")
    unchanged = replace(unchanged, data_signature=_signature_envelope(unchanged, "0" * 64))
    changed = replace(
        unchanged, automation_id="changed", affiliate_url="https://meli.la/changed"
    )
    registry = _OutcomeRegistry({changed.affiliate_url: _snapshot()})

    report = SyncEngine(_sync_gateway(records=(unchanged, changed)), registry).run(
        "pending", dry_run=True
    )

    assert registry.selected == [changed.affiliate_url]
    assert [item.row_number for item in report.items] == [3]


def test_common_shopee_link_waits_for_conversion_without_fetching_store_data():
    """Catches ordinary Shopee links bypassing the manual affiliate conversion gate."""
    from automation.sync import SyncEngine

    record = _record(
        status=ImportStatus.NOVO, publish="Não", partner="shopee",
        product_url="https://shopee.com.br/product/1/2", affiliate_url="",
    )
    registry = _OutcomeRegistry(
        {record.product_url: _snapshot(partner="shopee")},
        partner_for_url={record.product_url: "shopee"},
    )

    report = SyncEngine(_sync_gateway(records=(record,)), registry).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.AGUARDANDO_CONVERSAO
    assert registry.fetched == [] and report.planned_product_updates == ()


@pytest.mark.parametrize("error", [UnsupportedUrlError("raw secret"), InvalidProductDataError("raw secret")])
def test_incompatible_url_or_data_ends_error_with_sanitized_message(error):
    """Catches typed permanent failures leaking connector detail or becoming retryable."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO)
    report = SyncEngine(
        _sync_gateway(records=(record,)), _OutcomeRegistry({record.affiliate_url: error})
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.ERRO
    assert report.items[0].message == "Dados ou URL incompatíveis."
    assert "secret" not in report.items[0].message
    assert report.planned_product_updates == ()


def test_store_blocking_ends_attention_and_preserves_all_product_metadata_columns():
    """Catches a public-store block replacing the last valid snapshot."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO, consecutive_attempts=1)
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({record.affiliate_url: BlockedByStoreError("secret response")}),
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.ATENCAO
    assert [update.range_name for update in report.planned_import_updates] == [
        "'Importações'!Z2:AB2", "'Importações'!AE2:AE2",
    ]
    assert report.planned_import_updates[0].values[0][2] == 2
    assert report.planned_product_updates == ()


@pytest.mark.parametrize("attempts,expected", [(0, 1), (1, 2)])
def test_first_two_temporary_failures_keep_status_and_data(attempts, expected):
    """Catches a transient failure erasing metadata or escalating too early."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO, consecutive_attempts=attempts)
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({record.affiliate_url: TemporaryFetchError("secret temporary")}),
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.NOVO
    assert report.planned_import_updates[0].values[0][2] == expected
    assert all(":AF" not in update.range_name for update in report.planned_import_updates)
    assert report.planned_product_updates == ()


@pytest.mark.parametrize("initial,mode,expected", [
    (ImportStatus.NOVO, "pending", ImportStatus.REVISAR),
    (ImportStatus.PUBLICADO, "full", ImportStatus.ATENCAO),
])
def test_confirmed_not_found_preserves_publication_and_requests_review(initial, mode, expected):
    """Catches automatic unpublishing after a confirmed unavailable response."""
    from automation.sync import SyncEngine

    record = _record(status=initial)
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({record.affiliate_url: ProductNotFoundError("gone secret")}),
    ).run(mode, dry_run=True)

    assert report.final_status(2) is expected
    assert report.planned_product_updates == ()
    assert all(update.range_name.endswith(("Z2:AB2", "AE2:AE2")) for update in report.planned_import_updates)


@pytest.mark.parametrize("initial,mode,expected", [
    (ImportStatus.NOVO, "pending", ImportStatus.REVISAR),
    (ImportStatus.PUBLICADO, "full", ImportStatus.ATENCAO),
])
def test_snapshot_marked_unavailable_never_changes_the_published_product(initial, mode, expected):
    """Catches availability=false toggling Ativo in Produtos automatically."""
    from automation.sync import SyncEngine

    record = _record(status=initial)
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({record.affiliate_url: _snapshot(available=False)}),
    ).run(mode, dry_run=True)

    assert report.final_status(2) is expected
    assert report.planned_product_updates == ()


def test_unchanged_snapshot_writes_only_state_and_verification_not_metadata():
    """Catches a stable data signature causing a full metadata rewrite."""
    from automation.sync import SyncEngine, _signature_envelope, _snapshot_signature

    record = _record(status=ImportStatus.NOVO, publish="Não")
    snapshot = replace(_snapshot(), affiliate_url=record.affiliate_url)
    record = replace(record, data_signature=_signature_envelope(record, _snapshot_signature(snapshot)))
    report = SyncEngine(
        _sync_gateway(records=(record,)), _OutcomeRegistry({record.affiliate_url: snapshot})
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.REVISAR
    assert [update.range_name for update in report.planned_import_updates] == [
        "'Importações'!Z2:AB2", "'Importações'!AE2:AE2",
    ]


def test_ambiguous_publication_stays_review_and_never_writes_products():
    """Catches two matching catalog rows being silently overwritten."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO, last_published_url="https://meli.la/duplicate")
    rows = (
        _row(2, affiliate_url="https://meli.la/duplicate"),
        _row(3, affiliate_url="https://meli.la/duplicate#fragment"),
    )
    report = SyncEngine(
        _sync_gateway(records=(record,), products=rows),
        _OutcomeRegistry({record.affiliate_url: _snapshot()}),
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.REVISAR
    assert report.items[0].message == "Correspondência de produto ambígua."
    assert report.planned_product_updates == ()


def test_blocked_update_mode_changes_only_operational_state_ranges():
    """Catches Bloqueado rewriting imported metadata or a product row."""
    from automation.models import UpdateMode
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.PUBLICADO, update_mode=UpdateMode.BLOQUEADO)
    registry = _OutcomeRegistry({})
    report = SyncEngine(_sync_gateway(records=(record,), products=(_row(2),)), registry).run(
        "full", dry_run=True
    )

    assert report.final_status(2) is ImportStatus.PUBLICADO
    assert registry.selected == []
    assert [update.range_name for update in report.planned_import_updates] == [
        "'Importações'!Z2:AB2", "'Importações'!AE2:AE2",
    ]
    assert report.planned_product_updates == ()


def test_live_publication_uses_checkpoint_product_terminal_phase_order_and_batch_limits():
    """Catches terminal PUBLICADO persistence before its durable product write."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO)
    sheets = _sync_gateway(records=(record,))
    report = SyncEngine(
        sheets, _OutcomeRegistry({record.affiliate_url: _snapshot()}),
        clock=lambda: datetime(2026, 8, 31, 12, tzinfo=UTC),
    ).run("pending", dry_run=False)

    batches = [[item["range"] for item in write["data"]] for write in sheets.value_writes]
    assert batches[0] == ["'Importações'!Z2:AE2"]
    assert batches[1] == ["'Produtos'!A2:T2"]
    assert all(name.startswith("'Importações'!") for name in batches[2])
    assert len(sheets.value_writes) == 3
    assert report.final_status(2) is ImportStatus.PUBLICADO


def test_many_rows_still_use_two_import_batches_and_one_product_batch():
    """Catches batching once per item instead of once per durable phase."""
    from automation.sync import SyncEngine

    first = _record(status=ImportStatus.NOVO, affiliate_url="https://meli.la/first", external_id="MLB111111")
    second = replace(first, automation_id="second", affiliate_url="https://meli.la/second", external_id="MLB222222")
    third = replace(first, automation_id="third", publish="Não", affiliate_url="https://meli.la/third", external_id="MLB333333")
    outcomes = {
        first.affiliate_url: _snapshot(external_id=first.external_id),
        second.affiliate_url: _snapshot(external_id=second.external_id),
        third.affiliate_url: TemporaryFetchError("temporary"),
    }
    sheets = _sync_gateway(records=(first, second, third))

    SyncEngine(sheets, _OutcomeRegistry(outcomes)).run("pending", dry_run=False)

    batches = [[item["range"] for item in write["data"]] for write in sheets.value_writes]
    assert len(batches) == 3
    assert len(batches[0]) == 3 and all(name.startswith("'Importações'!") for name in batches[0])
    assert len(batches[1]) == 2 and all(name.startswith("'Produtos'!") for name in batches[1])
    assert all(name.startswith("'Importações'!") for name in batches[2])


def test_dry_run_matches_live_plan_at_same_clock_and_performs_zero_writes():
    """Catches dry-run planning a materially different result from the live run."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO)
    fixed_now = datetime(2026, 8, 31, 12, tzinfo=UTC)
    dry_sheets, live_sheets = _sync_gateway(records=(record,)), _sync_gateway(records=(record,))
    dry = SyncEngine(dry_sheets, _OutcomeRegistry({record.affiliate_url: _snapshot()}), clock=lambda: fixed_now).run("pending", dry_run=True)
    live = SyncEngine(live_sheets, _OutcomeRegistry({record.affiliate_url: _snapshot()}), clock=lambda: fixed_now).run("pending", dry_run=False)

    assert dry.items == live.items
    assert dry.planned_import_updates == live.planned_import_updates
    assert dry.planned_product_updates == live.planned_product_updates
    assert dry_sheets.value_writes == [] and len(live_sheets.value_writes) == 3


def test_checkpoint_failure_prevents_registry_and_connector_calls():
    """Catches fetch work starting before PROCESSANDO is durable."""
    from conftest import FakeSheetsGateway
    from automation.sync import SyncEngine

    class FailingCheckpointGateway(FakeSheetsGateway):
        def batch_values_update(self, data, value_input_option):
            raise RuntimeError("checkpoint unavailable")

    record = _record(status=ImportStatus.NOVO)
    registry = _OutcomeRegistry({record.affiliate_url: _snapshot()})
    with pytest.raises(RuntimeError):
        SyncEngine(
            _sync_gateway(records=(record,), gateway_type=FailingCheckpointGateway), registry
        ).run("pending", dry_run=False)

    assert registry.selected == [] and registry.fetched == []


@pytest.mark.parametrize("failed_phase,expected", [("Produtos", ["Importações", "Produtos"]), ("terminal", ["Importações", "Produtos", "Importações"])])
def test_write_failure_never_advances_past_its_durable_phase(failed_phase, expected):
    """Catches a failed product/final batch being represented as fully persisted."""
    from conftest import FakeSheetsGateway
    from automation.sync import SyncEngine

    class PhaseGateway(FakeSheetsGateway):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.phases = []

        def batch_values_update(self, data, value_input_option):
            title = "Produtos" if data[0]["range"].startswith("'Produtos'!") else "Importações"
            self.phases.append(title)
            if title == failed_phase or (failed_phase == "terminal" and self.phases == expected):
                raise RuntimeError("phase unavailable")
            return super().batch_values_update(data, value_input_option)

    record = _record(status=ImportStatus.NOVO)
    sheets = _sync_gateway(records=(record,), gateway_type=PhaseGateway)
    with pytest.raises(RuntimeError):
        SyncEngine(sheets, _OutcomeRegistry({record.affiliate_url: _snapshot()})).run(
            "pending", dry_run=False
        )

    assert sheets.phases == expected


def test_unexpected_registry_failure_is_sanitized_as_temporary():
    """Catches registry internals leaking URL or exception text into Importações."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO)
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({}, select_error=RuntimeError("secret registry URL")),
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.NOVO
    assert report.items[0].message == "Falha temporária na coleta."
    assert "secret" not in report.items[0].message


def test_unexpected_connector_failure_is_sanitized_as_temporary():
    """Catches connector internals leaking response detail into Importações."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO)
    report = SyncEngine(
        _sync_gateway(records=(record,)),
        _OutcomeRegistry({record.affiliate_url: RuntimeError("secret body and URL")}),
    ).run("pending", dry_run=True)

    assert report.final_status(2) is ImportStatus.NOVO
    assert report.items[0].message == "Falha temporária na coleta."


def test_same_partner_fetches_never_overlap():
    """Catches simultaneous requests to one partner despite multiple workers."""
    from automation.sync import SyncEngine

    first_started, release_first, second_started = Event(), Event(), Event()
    active = 0
    maximum = 0
    calls = 0
    guard = Lock()

    def fetch_snapshot():
        nonlocal active, maximum, calls
        with guard:
            calls += 1
            active += 1
            maximum = max(maximum, active)
            number = calls
        if number == 1:
            first_started.set()
            release_first.wait(2)
        else:
            second_started.set()
        with guard:
            active -= 1
        return _snapshot()

    first = _record(status=ImportStatus.NOVO, publish="Não", affiliate_url="https://meli.la/one")
    second = replace(first, automation_id="two", affiliate_url="https://meli.la/two")
    registry = _OutcomeRegistry({first.affiliate_url: fetch_snapshot, second.affiliate_url: fetch_snapshot})
    result = {}
    runner = Thread(target=lambda: result.setdefault("report", SyncEngine(_sync_gateway(records=(first, second)), registry).run("pending", dry_run=True)))
    runner.start()
    assert first_started.wait(1)
    assert not second_started.wait(0.05)
    release_first.set()
    runner.join(2)

    assert not runner.is_alive() and maximum == 1
    assert [item.final_status for item in result["report"].items] == [ImportStatus.REVISAR, ImportStatus.REVISAR]


def test_different_partners_can_fetch_concurrently_and_results_stay_in_sheet_order():
    """Catches a global lock or completion-order report nondeterminism."""
    from automation.sync import SyncEngine

    mercado_started, shopee_started = Event(), Event()

    def mercado_fetch():
        mercado_started.set()
        if not shopee_started.wait(1):
            raise RuntimeError("shopee did not overlap")
        return _snapshot()

    def shopee_fetch():
        shopee_started.set()
        if not mercado_started.wait(1):
            raise RuntimeError("mercado did not overlap")
        return _snapshot(partner="shopee")

    first = _record(status=ImportStatus.NOVO, publish="Não", affiliate_url="https://meli.la/one")
    second = replace(first, automation_id="two", partner="shopee", affiliate_url="https://s.shopee.com.br/two")
    registry = _OutcomeRegistry(
        {first.affiliate_url: mercado_fetch, second.affiliate_url: shopee_fetch},
        partner_for_url={first.affiliate_url: "mercado_livre", second.affiliate_url: "shopee"},
    )

    report = SyncEngine(_sync_gateway(records=(first, second)), registry).run("pending", dry_run=True)

    assert mercado_started.is_set() and shopee_started.is_set()
    assert [item.row_number for item in report.items] == [2, 3]
    assert [item.final_status for item in report.items] == [ImportStatus.REVISAR, ImportStatus.REVISAR]


def test_sync_does_not_mutate_input_records_or_snapshots():
    """Catches orchestration mutating frozen inputs shared with connector callers."""
    from automation.sync import SyncEngine

    record = _record(status=ImportStatus.NOVO, publish="Não")
    snapshot = _snapshot()
    before_record, before_snapshot = record, snapshot

    SyncEngine(
        _sync_gateway(records=(record,)), _OutcomeRegistry({record.affiliate_url: snapshot})
    ).run("pending", dry_run=True)

    assert record == before_record and snapshot == before_snapshot


def test_mapping_places_a_valid_promotion_in_the_two_price_columns():
    values = map_snapshot_to_product_values(_snapshot(), _record(), existing=None)

    assert len(values) == len(PRODUCTS_HEADERS) == 20
    assert values[7:9] == (Decimal("199.90"), Decimal("149.90"))
    assert calculate_discount(Decimal("149.90"), Decimal("199.90")) == 25


def test_discount_rounds_half_up_without_float_intermediates():
    assert calculate_discount(Decimal("75.50"), Decimal("100")) == 25
    assert calculate_discount(Decimal("75.49"), Decimal("100")) == 25
    assert calculate_discount(Decimal("74.50"), Decimal("100")) == 26


@pytest.mark.parametrize("current, previous", [
    (Decimal("0"), Decimal("10")),
    (Decimal("10"), Decimal("0")),
    (Decimal("10"), Decimal("10")),
    (Decimal("11"), Decimal("10")),
    (Decimal("NaN"), Decimal("10")),
    (Decimal("10"), Decimal("Infinity")),
])
def test_discount_refuses_nonpositive_nonfinite_or_nonpromotional_prices(current, previous):
    with pytest.raises(InvalidProductDataError):
        calculate_discount(current, previous)


def test_mapping_keeps_regular_price_decimal_and_blanks_promotion():
    values = map_snapshot_to_product_values(
        _snapshot(previous_price=None, coupon=None, coupon_expires_at=None), _record(), existing=None
    )

    assert values[7:11] == (Decimal("149.90"), "", "", "")
    assert isinstance(values[7], Decimal)


def test_mapping_preserves_human_video_and_missing_old_images_without_deletion():
    existing = _row()
    values = map_snapshot_to_product_values(_snapshot(images=("https://images.example/new.jpg",)), _record(), existing)

    assert values[13] == existing.video_url
    assert values[14:18] == (
        "https://images.example/new.jpg", existing.image_2, existing.image_3, existing.image_4,
    )


@pytest.mark.parametrize("images", [(), ("http://images.example/item.jpg",), ("not a url",)])
def test_mapping_refuses_new_product_without_a_valid_primary_https_image(images):
    with pytest.raises(InvalidProductDataError):
        map_snapshot_to_product_values(_snapshot(images=images), _record(), None)


def test_new_publication_with_no_valid_image_produces_no_sheet_update():
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(images=()), _record(last_published_url="", affiliate_url=""), ())


def test_mapping_deduplicates_normalized_new_images_and_preserves_valid_adopted_primary():
    existing = _row(
        image_1="HTTPS://IMAGES.EXAMPLE/old.jpg#fragment",
        image_2="http://bad.example/old.jpg",
    )
    adopted = map_snapshot_to_product_values(_snapshot(images=()), _record(), existing)
    replaced = map_snapshot_to_product_values(
        _snapshot(images=(
            "HTTPS://IMAGES.EXAMPLE/new.jpg?b=2&a=1#fragment",
            "https://images.example/new.jpg?a=1&b=2",
        )),
        _record(),
        existing,
    )

    assert adopted[14] == "https://images.example/old.jpg"
    assert adopted[15] == ""
    assert adopted[16:18] == ("https://images.example/old-3.jpg", "https://images.example/old-4.jpg")
    assert replaced[14:18] == (
        "https://images.example/new.jpg?a=1&b=2", "",
        "https://images.example/old-3.jpg", "https://images.example/old-4.jpg",
    )


def test_mapping_refuses_adoption_without_new_or_existing_valid_primary_image():
    with pytest.raises(InvalidProductDataError):
        map_snapshot_to_product_values(
            _snapshot(images=()), _record(), _row(image_1="http://bad.example/image.jpg")
        )


def test_mapping_uses_original_affiliate_link_and_normalizes_default_or_custom_button():
    default_values = map_snapshot_to_product_values(_snapshot(), _record(button_text="  \t "), None)
    custom_values = map_snapshot_to_product_values(_snapshot(), _record(button_text="  Comprar\n agora  "), None)

    assert default_values[11:14] == (
        "https://meli.la/current?b=2&a=1", "Ver oferta na Mercado Livre", "",
    )
    assert custom_values[12] == "Comprar agora"


def test_mapping_gates_active_and_keeps_the_header_order_and_typed_expiry():
    values = map_snapshot_to_product_values(_snapshot(), _record(active="Não", publish="Sim"), None)

    assert values == (
        "Não", "Físico", "mercado_livre", "Eletrônicos", "Áudio", "Produto de teste",
        "Descrição de teste", Decimal("199.90"), Decimal("149.90"), "CUPOM",
        datetime(2026, 9, 1, tzinfo=UTC), "https://meli.la/current?b=2&a=1",
        "Ver oferta na Mercado Livre", "", "https://images.example/1.jpg",
        "https://images.example/2.jpg", "https://images.example/3.jpg",
        "https://images.example/4.jpg", "9", "Não",
    )


def test_data_signature_is_canonical_for_nested_mapping_decimal_and_timezone_equivalents():
    utc = datetime(2026, 8, 30, 15, 0, tzinfo=UTC)
    offset = utc.astimezone(timezone(timedelta(hours=-3)))
    first = {"b": [Decimal("10.00"), None, True], "a": {"when": utc}}
    second = {"a": {"when": offset}, "b": [Decimal("10.00"), None, True]}

    assert data_signature(first) == data_signature(second)
    assert data_signature(first) == "34eec51dfdd819fe24a1df28737ca1f315a224e2110c245032a522ba5bf12393"


def test_data_signature_preserves_decimal_scale_image_order_and_treats_naive_datetime_as_utc():
    point = datetime(2026, 8, 30, 15, 0)

    assert data_signature({"price": Decimal("10.0"), "images": ["one", "two"], "at": point}) == data_signature(
        {"at": point.replace(tzinfo=UTC), "images": ["one", "two"], "price": Decimal("10.0")}
    )
    assert data_signature({"price": Decimal("10.0")}) != data_signature({"price": Decimal("10.00")})
    assert data_signature({"images": ["one", "two"]}) != data_signature({"images": ["two", "one"]})


@dataclass
class _CustomPayload:
    value: object


def test_data_signature_rejects_custom_dataclasses_and_cycles_before_recursing():
    self_list = []
    self_list.append(self_list)
    self_mapping = {}
    self_mapping["self"] = self_mapping
    tuple_cycle_list = []
    tuple_cycle = (tuple_cycle_list,)
    tuple_cycle_list.append(tuple_cycle)

    for value in (
        _CustomPayload("custom"), self_list, self_mapping, tuple_cycle,
        {"bytes": b"nope"}, {"set": {"nope"}},
    ):
        with pytest.raises(InvalidProductDataError):
            data_signature(value)


def test_data_signature_keeps_type_boundaries_between_equal_looking_scalars_and_sequences():
    assert data_signature(True) != data_signature(1)
    assert data_signature("1") != data_signature(1)
    assert data_signature(["x"]) != data_signature(("x",))


@pytest.mark.parametrize("value", [object(), {1: "not-a-string-key"}, float("nan"), Decimal("NaN")])
def test_data_signature_rejects_unsupported_or_nonfinite_values(value):
    with pytest.raises(InvalidProductDataError):
        data_signature(value)


def test_link_signatures_use_the_security_normalization_without_link_disclosure():
    first = "HTTPS://MELI.LA/current?b=2&a=1#fragment"
    equivalent = "https://meli.la/current?a=1&b=2"

    assert link_signature(first) == link_signature(equivalent)
    assert link_signature(first) != link_signature("https://meli.la/other?a=1&b=2")
    with pytest.raises(Exception) as raised:
        link_signature("https://user:secret@meli.la/private?token=not-for-output")
    assert "secret" not in str(raised.value)
    assert "not-for-output" not in str(raised.value)


def test_match_uses_last_published_link_before_current_link_or_identity():
    record = _record(last_published_url="https://meli.la/old", affiliate_url="https://meli.la/current")
    old_match = _row(7, affiliate_url="https://meli.la/old", reconstructed_external_id="OTHER")
    current_match = _row(8, affiliate_url="https://meli.la/current", reconstructed_external_id="MLB123")

    assert find_product_match(record, (old_match, current_match)) is old_match


def test_match_falls_through_to_current_link_then_normalized_partner_external_id():
    record = _record(last_published_url="", affiliate_url="https://meli.la/current")
    current_match = _row(8, affiliate_url="HTTPS://MELI.LA/current#ignored", reconstructed_external_id="OTHER")
    id_match = _row(9, affiliate_url="https://meli.la/else", partner="  MERCADO_LIVRE ", reconstructed_external_id=" mlb123 ")

    assert find_product_match(record, (current_match, id_match)) is current_match
    assert find_product_match(replace(record, affiliate_url=""), (id_match,)) is id_match


def test_match_never_uses_substrings_or_empty_identity_values():
    record = _record(last_published_url="", affiliate_url="", external_id="MLB123")
    lookalike = _row(7, reconstructed_external_id="xMLB123x", affiliate_url="https://meli.la/lookalike")
    empty = _row(8, partner="", reconstructed_external_id="", affiliate_url="")

    assert find_product_match(record, (lookalike, empty)) is None


def test_match_refuses_an_ambiguous_tier_before_considering_lower_tiers():
    record = _record(last_published_url="https://meli.la/old")
    first = _row(7, affiliate_url="https://meli.la/old", reconstructed_external_id="other")
    second = _row(8, affiliate_url="https://meli.la/old#fragment", reconstructed_external_id="MLB123")

    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(record, (first, second))


def test_match_refuses_ambiguous_current_link_or_identity_tiers_independently():
    current_record = _record(last_published_url="", affiliate_url="https://meli.la/current")
    current_rows = (
        _row(7, affiliate_url="https://meli.la/current", reconstructed_external_id="OTHER"),
        _row(8, affiliate_url="https://meli.la/current#fragment", reconstructed_external_id="MLB123"),
    )
    identity_record = _record(last_published_url="", affiliate_url="")
    identity_rows = (
        _row(7, affiliate_url="https://meli.la/first"),
        _row(8, affiliate_url="https://meli.la/second"),
    )

    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(current_record, current_rows)
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(identity_record, identity_rows)


def test_match_refuses_duplicate_or_invalid_product_row_identity():
    first = _row(7)
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(_record(), (first, replace(first, affiliate_url="https://meli.la/other")))
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(_record(), (_row(True),))


def test_publication_plans_an_update_for_adoption_without_erasing_preserved_values():
    record = _record(last_published_url="https://meli.la/old")
    update, = plan_publication(_snapshot(), record, (_row(),))

    assert update.range_name == "'Produtos'!A7:T7"
    assert len(update.values) == 1
    assert len(update.values[0]) == 20
    assert update.values[0][11] == "https://meli.la/current?b=2&a=1"
    assert update.values[0][13] == "https://youtube.example/watch?v=keep"


def test_publication_plans_the_next_row_for_create_and_no_writes_for_noop_or_unapproved_record():
    snapshot = _snapshot()
    record = _record(last_published_url="", affiliate_url="https://meli.la/current?b=2&a=1")
    create, = plan_publication(snapshot, record, (_row(7, affiliate_url="https://meli.la/other", reconstructed_external_id="OTHER"),))
    matching_values = map_snapshot_to_product_values(snapshot, record, _row(7, affiliate_url=snapshot.affiliate_url, video_url=""))
    exact = _row(7, affiliate_url=snapshot.affiliate_url, video_url="", **{
        "active": matching_values[0], "product_type": matching_values[1], "partner": matching_values[2],
        "category": matching_values[3], "subcategory": matching_values[4], "name": matching_values[5],
        "description": matching_values[6], "price": matching_values[7], "promotional_price": matching_values[8],
        "coupon": matching_values[9], "offer_expires_at": "2026-09-01T00:00:00Z", "button_text": matching_values[12],
        "image_1": matching_values[14], "image_2": matching_values[15], "image_3": matching_values[16],
        "image_4": matching_values[17], "order": matching_values[18], "featured": matching_values[19],
    })

    assert create.range_name == "'Produtos'!A8:T8"
    assert plan_publication(snapshot, record, (exact,)) == ()
    assert plan_publication(snapshot, replace(record, publish="Não"), ()) == ()


def test_publication_rejects_invalid_domain_objects_before_planning_a_write():
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(), object(), ())


def test_publication_compares_expiry_semantically_and_rejects_malformed_existing_expiry():
    snapshot = _snapshot(
        coupon_expires_at=datetime(2026, 8, 31, 21, tzinfo=timezone(timedelta(hours=-3)))
    )
    record = _record(last_published_url="", affiliate_url="https://meli.la/current?b=2&a=1")
    desired = map_snapshot_to_product_values(
        snapshot, record, _row(affiliate_url=snapshot.affiliate_url, video_url="")
    )
    equal = _row(affiliate_url=snapshot.affiliate_url, video_url="", **{
        "active": desired[0], "product_type": desired[1], "partner": desired[2],
        "category": desired[3], "subcategory": desired[4], "name": desired[5],
        "description": desired[6], "price": desired[7], "promotional_price": desired[8],
        "coupon": desired[9], "offer_expires_at": "2026-09-01T00:00:00Z",
        "button_text": desired[12], "image_1": desired[14], "image_2": desired[15],
        "image_3": desired[16], "image_4": desired[17], "order": desired[18],
        "featured": desired[19],
    })

    assert plan_publication(snapshot, record, (equal,)) == ()
    assert plan_publication(snapshot, record, (replace(equal, offer_expires_at="2026-09-01"),)) == ()
    assert plan_publication(
        snapshot, record, (replace(equal, offer_expires_at="2026-08-31T21:00:00-03:00"),)
    ) == ()
    assert plan_publication(
        snapshot, record, (replace(equal, offer_expires_at="2026-09-01T05:30:00+05:30"),)
    ) == ()
    changed, = plan_publication(
        snapshot, record, (replace(equal, offer_expires_at="2026-09-02"),)
    )
    assert changed.range_name == "'Produtos'!A7:T7"
    with pytest.raises(InvalidProductDataError):
        plan_publication(snapshot, record, (replace(equal, offer_expires_at="tomorrow"),))
    with pytest.raises(InvalidProductDataError):
        plan_publication(
            snapshot, record, (replace(equal, offer_expires_at="2026-09-01 00:00:00Z"),)
        )
    with pytest.raises(InvalidProductDataError):
        plan_publication(snapshot, record, (replace(equal, offer_expires_at="2026-09-01T00:00:00"),))
    with pytest.raises(InvalidProductDataError):
        plan_publication(snapshot, record, (replace(equal, offer_expires_at="2026-09-01T00:00:00+99:00"),))
    with pytest.raises(InvalidProductDataError):
        plan_publication(
            snapshot, record,
            (replace(equal, offer_expires_at="0001-01-01T00:00:00+23:59"),),
        )


@pytest.mark.parametrize("invalid_expiry", [
    "2026-09-01T00:00:00Z\x00",
    "2026-09-01T00:00:00Z ",
    "2026-09-01T00:00:00Zjunk",
    "prefix2026-09-01T00:00:00Z",
    "2026-09-01T00:00:00Z\n",
    "2026-09-01T00:00:00+05",
    "2026-09-01T00:00:00+0530",
])
def test_publication_rejects_any_non_iso_suffix_or_prefix_in_existing_expiry(invalid_expiry):
    snapshot = _snapshot()
    record = _record(last_published_url="", affiliate_url=snapshot.affiliate_url)
    desired = map_snapshot_to_product_values(snapshot, record, _row(affiliate_url=snapshot.affiliate_url))
    existing = _row(affiliate_url=snapshot.affiliate_url, **{
        "active": desired[0], "product_type": desired[1], "partner": desired[2],
        "category": desired[3], "subcategory": desired[4], "name": desired[5],
        "description": desired[6], "price": desired[7], "promotional_price": desired[8],
        "coupon": desired[9], "offer_expires_at": invalid_expiry, "button_text": desired[12],
        "image_1": desired[14], "image_2": desired[15], "image_3": desired[16],
        "image_4": desired[17], "order": desired[18], "featured": desired[19],
    })

    with pytest.raises(InvalidProductDataError):
        plan_publication(snapshot, record, (existing,))


def test_publication_accepts_a_fractional_iso_timestamp_with_a_valid_offset():
    snapshot = _snapshot(coupon_expires_at=datetime(2026, 8, 31, 21, 0, 0, 123456, tzinfo=timezone(timedelta(hours=-3))))
    record = _record(last_published_url="", affiliate_url=snapshot.affiliate_url)
    desired = map_snapshot_to_product_values(snapshot, record, _row(affiliate_url=snapshot.affiliate_url))
    existing = _row(affiliate_url=snapshot.affiliate_url, **{
        "active": desired[0], "product_type": desired[1], "partner": desired[2],
        "category": desired[3], "subcategory": desired[4], "name": desired[5],
        "description": desired[6], "price": desired[7], "promotional_price": desired[8],
        "coupon": desired[9], "offer_expires_at": "2026-08-31T21:00:00.123456-03:00",
        "button_text": desired[12], "image_1": desired[14], "image_2": desired[15],
        "image_3": desired[16], "image_4": desired[17], "order": desired[18],
        "featured": desired[19],
    })

    assert plan_publication(snapshot, record, (existing,)) == ()


def test_canonical_offer_expiry_normalizes_an_aware_datetime():
    point = datetime(2026, 8, 31, 21, 0, 0, 123456, tzinfo=timezone(timedelta(hours=-3)))

    assert _canonical_offer_expiry(point) == "2026-09-01T00:00:00.123456Z"


def test_canonical_offer_expiry_rejects_a_naive_datetime():
    with pytest.raises(InvalidProductDataError):
        _canonical_offer_expiry(datetime(2026, 9, 1))


def test_canonical_offer_expiry_rejects_datetime_utc_overflow_without_leaking():
    point = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=23, minutes=59)))

    with pytest.raises(InvalidProductDataError) as raised:
        _canonical_offer_expiry(point)

    error = raised.value
    assert error.__cause__ is None and error.__context__ is None
    assert "date value out of range" not in str(error)


@pytest.mark.parametrize("error_type", [ValueError, TypeError])
def test_canonical_offer_expiry_rejects_datetime_with_broken_tzinfo_without_leaking(error_type):
    point = datetime(2026, 9, 1, tzinfo=_RaisingTzinfo(error_type))

    with pytest.raises(InvalidProductDataError) as raised:
        _canonical_offer_expiry(point)

    error = raised.value
    assert error.__cause__ is None and error.__context__ is None
    assert "secret tzinfo failure" not in str(error)


@pytest.mark.parametrize("invalid_rows", [None, 3, "not rows", b"not rows", (_row(7), object())])
def test_matching_and_publication_reject_invalid_product_row_collections(invalid_rows):
    record = _record()
    with pytest.raises(InvalidProductDataError):
        find_product_match(record, invalid_rows)
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(), record, invalid_rows)


def test_matching_and_publication_reject_generator_product_rows_outside_sequence_contract():
    with pytest.raises(InvalidProductDataError):
        find_product_match(_record(), (_row() for _ in range(1)))
    with pytest.raises(InvalidProductDataError):
        plan_publication(_snapshot(), _record(), (_row() for _ in range(1)))
