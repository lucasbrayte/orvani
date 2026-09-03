# Orvani Manual Update Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `Manual` update mode so reviewed catalog fields from `Importações` are published without public-store metadata replacing them.

**Architecture:** Extend the existing `UpdateMode` domain, build a validated `ProductSnapshot` directly from an `ImportRecord`, and route Manual rows through that snapshot path before connector fetching. Automatic and Blocked modes retain their current behavior, and all existing publication validation/persistence logic remains in force.

**Tech Stack:** Python 3.12, `Decimal`, existing Orvani sync engine, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-03-libreoffice-orvani-sync-design.md`

## Global Constraints

- LibreOffice-authored catalog fields are authoritative only in `Manual` mode.
- `Automático` and `Bloqueado` behavior must not regress.
- Manual mode must still enforce partner allowlists, identity checks, price checks, image checks, publication matching, and `Produtos` persistence verification.
- `ID Externo`, status, messages, attempts, signatures, and timestamps remain backend-controlled.
- No new spreadsheet columns are introduced.
- Existing known full-suite row-layout debt must not increase; targeted suites for touched behavior must be fully green.

---

### Task 1: Add `UpdateMode.MANUAL`

**Files:**
- Modify: `automation/models.py:47-52`
- Modify: `tests/test_models.py`

**Interfaces:**
- Consumes: existing `UpdateMode(StrEnum)` and `ImportRecord.from_sheet_row(...)`.
- Produces: `UpdateMode.MANUAL` with serialized value exactly `"Manual"`.

- [ ] **Step 1: Write the failing enum and parsing tests**

Add:

```python
def test_update_mode_accepts_manual():
    assert UpdateMode("Manual") is UpdateMode.MANUAL


def test_import_record_parses_manual_update_mode():
    row = [""] * 32
    row[0] = "manual-row"
    row[1] = "Sim"
    row[2] = "Sim"
    row[5] = "Manual"
    record, planned = ImportRecord.from_sheet_row(2, row)
    assert planned is None
    assert record.update_mode is UpdateMode.MANUAL
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
python3 -m pytest -q \
  tests/test_models.py::test_update_mode_accepts_manual \
  tests/test_models.py::test_import_record_parses_manual_update_mode
```

Expected: FAIL because `UpdateMode.MANUAL` does not exist.

- [ ] **Step 3: Add the minimal enum member**

Change the enum to:

```python
class UpdateMode(StrEnum):
    AUTOMATICO = "Automático"
    MANUAL = "Manual"
    BLOQUEADO = "Bloqueado"
```

No special parser branch is needed because `ImportRecord.from_sheet_row` already constructs `UpdateMode` from column F.

- [ ] **Step 4: Run the model tests**

Run:

```bash
python3 -m pytest -q tests/test_models.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add automation/models.py tests/test_models.py
git commit -m "feat: add manual update mode"
```

---

### Task 2: Build a safe Manual `ProductSnapshot`

**Files:**
- Modify: `automation/sync.py:897-1080`
- Create: `tests/test_manual_update_mode.py`

**Interfaces:**
- Consumes: `ImportRecord`, `_canonical_partner_key`, `_normalized_partner_link_or_none`, `_unique_normalized_images`, `_valid_price`, `_utc_now`, partner ID extractors already imported by `automation.sync`.
- Produces:
  - `_manual_import_snapshot(record: ImportRecord, fetched_at: datetime) -> ProductSnapshot`
  - `_manual_external_id(record: ImportRecord, partner: str, source_url: str, affiliate_url: str) -> str`
  - `_manual_coupon_expiry(value: str) -> datetime | None`

- [ ] **Step 1: Write failing snapshot tests**

Create `tests/test_manual_update_mode.py` with a helper based on `ImportRecord` and these tests:

```python
def test_manual_snapshot_preserves_reviewed_catalog_fields():
    record = _manual_record(
        product_url="https://www.mercadolivre.com.br/produto/p/MLB62276281"
        "?pdp_filters=item_id%3AMLB4431628133",
        affiliate_url="https://meli.la/abc123",
        name="Panelas revisadas",
        description="Descrição revisada no Calc.",
        category="Casa",
        subcategory="Cozinha",
        product_type="Físico",
        current_price=Decimal("189.99"),
        previous_price=Decimal("331.42"),
        image_1="https://http2.mlstatic.com/test.jpg",
    )

    snapshot = _manual_import_snapshot(record, NOW)

    assert snapshot.partner == "mercado_livre"
    assert snapshot.external_id == "MLB4431628133"
    assert snapshot.name == record.name
    assert snapshot.description == record.description
    assert snapshot.current_price == Decimal("189.99")
    assert snapshot.previous_price == Decimal("331.42")
    assert snapshot.images == (record.image_1,)
    assert snapshot.affiliate_url == record.affiliate_url


def test_manual_snapshot_rejects_missing_required_text():
    with pytest.raises(InvalidProductDataError):
        _manual_import_snapshot(_manual_record(name=""), NOW)


def test_manual_snapshot_rejects_invalid_promotion():
    with pytest.raises(InvalidProductDataError):
        _manual_import_snapshot(
            _manual_record(
                current_price=Decimal("200.00"),
                previous_price=Decimal("199.00"),
            ),
            NOW,
        )


def test_manual_snapshot_rejects_product_without_safe_identity():
    with pytest.raises(InvalidProductDataError):
        _manual_import_snapshot(
            _manual_record(
                product_url="https://www.mercadolivre.com.br/produto/p/MLB62276281"
            ),
            NOW,
        )
```

The helper must use `update_mode=UpdateMode.MANUAL`, status `NOVO`, and otherwise valid fields.

- [ ] **Step 2: Run the new file and verify RED**

```bash
python3 -m pytest -q tests/test_manual_update_mode.py
```

Expected: collection/import failure because `_manual_import_snapshot` is not defined.

- [ ] **Step 3: Implement identity and coupon helpers**

Add to `automation/sync.py` near the existing manual fallback helpers:

```python
def _manual_external_id(
    record: ImportRecord,
    partner: str,
    source_url: str,
    affiliate_url: str,
) -> str:
    extractors = {
        "mercado_livre": extract_mercado_item_id,
        "shopee": extract_shopee_item_id,
        "shein": extract_shein_product_id,
        "tiktok_shop": extract_tiktok_shop_product_id,
    }
    extractor = extractors.get(partner)
    external_id = (
        extractor(source_url) if extractor is not None else None
    ) or (
        extractor(affiliate_url) if extractor is not None else None
    )
    if external_id:
        return external_id
    if partner == "shein" and record.automation_id.strip():
        return f"manual-{record.automation_id.strip()}"
    raise InvalidProductDataError("O produto manual não tem identidade segura.")


def _manual_coupon_expiry(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        if _ISO_DATE.fullmatch(text):
            day = date.fromisoformat(text)
            return datetime(day.year, day.month, day.day, tzinfo=UTC)
        if _ISO_TIMESTAMP.fullmatch(text):
            parsed = text[:-1] + "+00:00" if text.endswith("Z") else text
            point = datetime.fromisoformat(parsed)
            if point.tzinfo is None or point.utcoffset() is None:
                raise ValueError
            return point.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        pass
    raise InvalidProductDataError("A validade manual do cupom é inválida.")
```

This deliberately preserves the stricter Mercado Livre offer-ID rule and the existing SHEIN automation-ID fallback.

- [ ] **Step 4: Implement `_manual_import_snapshot`**

Add:

```python
def _manual_import_snapshot(
    record: ImportRecord,
    fetched_at: datetime,
) -> ProductSnapshot:
    if not isinstance(record, ImportRecord) or record.update_mode is not UpdateMode.MANUAL:
        raise InvalidProductDataError("O registro manual é inválido.")

    partner = _canonical_partner_key(record.partner)
    if not partner or partner not in PARTNERS:
        raise InvalidProductDataError("A plataforma manual é inválida.")

    source_url = record.product_url.strip()
    affiliate_url = record.affiliate_url.strip()
    if _normalized_partner_link_or_none(source_url, partner) is None:
        raise InvalidProductDataError("O link do produto manual é inválido.")
    if _normalized_partner_link_or_none(affiliate_url, partner) is None:
        raise InvalidProductDataError("O link afiliado manual é inválido.")

    required = (
        record.name,
        record.description,
        record.category,
        record.subcategory,
        record.product_type,
    )
    if any(not _text_or_blank(value) for value in required):
        raise InvalidProductDataError("O produto manual está incompleto.")

    if record.current_price is None:
        raise InvalidProductDataError("O preço atual manual está ausente.")
    _valid_price(record.current_price)

    if record.previous_price is not None:
        _valid_price(record.previous_price)
        if record.previous_price <= record.current_price:
            raise InvalidProductDataError("A promoção manual é inválida.")

    images = tuple(
        _unique_normalized_images(
            (record.image_1, record.image_2, record.image_3, record.image_4)
        )
    )
    if not images:
        raise InvalidProductDataError("O produto manual exige uma imagem HTTPS.")

    external_id = _manual_external_id(record, partner, source_url, affiliate_url)

    return ProductSnapshot(
        partner=partner,
        external_id=external_id,
        catalog_id=(
            _mercado_catalog_id_from_url(source_url)
            if partner == "mercado_livre"
            else None
        ),
        source_url=source_url,
        affiliate_url=affiliate_url,
        name=record.name.strip(),
        description=record.description.strip(),
        current_price=record.current_price,
        previous_price=record.previous_price,
        currency=CATALOG_CURRENCY,
        category=record.category.strip(),
        subcategory=record.subcategory.strip(),
        product_type=record.product_type.strip(),
        coupon=record.coupon.strip() or None,
        coupon_expires_at=_manual_coupon_expiry(record.coupon_expires_at),
        images=images,
        available=None,
        fetched_at=_utc_now(fetched_at),
    )
```

- [ ] **Step 5: Run the snapshot tests**

```bash
python3 -m pytest -q tests/test_manual_update_mode.py
```

Expected: PASS for the snapshot tests.

- [ ] **Step 6: Commit**

```bash
git add automation/sync.py tests/test_manual_update_mode.py
git commit -m "feat: build validated manual snapshots"
```

---

### Task 3: Route Manual rows without store connector fetching

**Files:**
- Modify: `automation/sync.py:566-620`
- Modify: `tests/test_manual_update_mode.py`

**Interfaces:**
- Consumes: `_manual_import_snapshot(record, now)`.
- Produces: Manual rows enter the normal `_plan_record` publication path as `ProductSnapshot` values, while `_fetch_all(...)` receives only Automatic rows.

- [ ] **Step 1: Add a failing routing test**

Use a registry stub that fails if connector selection occurs:

```python
class NoConnectorRegistry:
    def select(self, _url):
        raise AssertionError("manual mode must not select a connector")


def test_manual_mode_does_not_fetch_public_store_metadata(gateway):
    record = _manual_record()
    gateway.set_import_records((record,))
    engine = SyncEngine(
        gateway,
        NoConnectorRegistry(),
        clock=lambda: NOW,
    )

    report = engine.run("pending", dry_run=True)

    assert len(report.items) == 1
    assert report.items[0].final_status is ImportStatus.PUBLICADO
    assert len(report.planned_product_updates) == 1
```

Adapt only the gateway setup lines to the existing fake gateway API in `tests/conftest.py`; keep the `NoConnectorRegistry` assertion unchanged.

- [ ] **Step 2: Run the routing test and verify RED**

```bash
python3 -m pytest -q \
  tests/test_manual_update_mode.py::test_manual_mode_does_not_fetch_public_store_metadata
```

Expected: FAIL with `AssertionError: manual mode must not select a connector`.

- [ ] **Step 3: Partition selected rows in `SyncEngine.run`**

Replace the current Blocked-vs-fetch partition with:

```python
blocked_records = tuple(
    record for record in selected
    if record.update_mode is UpdateMode.BLOQUEADO
)
manual_records = tuple(
    record for record in selected
    if record.update_mode is UpdateMode.MANUAL
)
fetch_records = tuple(
    record for record in selected
    if record.update_mode is UpdateMode.AUTOMATICO
)
processing_records = (*manual_records, *fetch_records)
```

Checkpoint `processing_records`, not only `fetch_records`:

```python
if processing_records and not dry_run:
    checkpoint = tuple(
        _processing_update(record, now, self._imports)
        for record in processing_records
    )
    _write_sync_batch(
        self._gateway,
        checkpoint,
        worksheet=self._imports,
        headers=IMPORT_HEADERS,
        phase="checkpoint",
    )
```

Build outcomes before `_fetch_all`:

```python
fetched = {
    record.row_number: _BlockedMode()
    for record in blocked_records
}
for record in manual_records:
    try:
        fetched[record.row_number] = _manual_import_snapshot(record, now)
    except InvalidProductDataError as error:
        fetched[record.row_number] = error
fetched.update(self._fetch_all(fetch_records))
```

- [ ] **Step 4: Run Manual-mode tests**

```bash
python3 -m pytest -q tests/test_manual_update_mode.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add automation/sync.py tests/test_manual_update_mode.py
git commit -m "feat: bypass connectors in manual mode"
```

---

### Task 4: Prove Manual publication does not overwrite reviewed data

**Files:**
- Modify: `tests/test_manual_update_mode.py`
- No production-file change should be needed unless the test exposes a real defect.

**Interfaces:**
- Consumes: the normal `_plan_record`, `_record_from_snapshot`, `plan_publication`, and product persistence mapping.
- Produces: regression coverage proving reviewed Manual values are the values written to `Produtos`.

- [ ] **Step 1: Add the publication regression test**

```python
def test_manual_publication_uses_calc_values_verbatim():
    engine = SyncEngine(object(), object())
    record = _manual_record(
        name="Nome do Calc",
        description="Descrição do Calc",
        category="Casa",
        subcategory="Cozinha",
        current_price=Decimal("189.99"),
        previous_price=Decimal("331.42"),
        image_1="https://http2.mlstatic.com/manual.jpg",
    )
    snapshot = _manual_import_snapshot(record, NOW)

    item, _changes, publication = engine._plan_record(
        record,
        snapshot,
        (),
        NOW,
    )

    assert item.final_status is ImportStatus.PUBLICADO
    values = publication[0].values[0]
    assert values[5] == "Nome do Calc"
    assert values[6] == "Descrição do Calc"
    assert values[3] == "Casa"
    assert values[4] == "Cozinha"
    assert values[7] == Decimal("331.42")
    assert values[8] == Decimal("189.99")
    assert values[14] == "https://http2.mlstatic.com/manual.jpg"
```

- [ ] **Step 2: Run the test**

```bash
python3 -m pytest -q \
  tests/test_manual_update_mode.py::test_manual_publication_uses_calc_values_verbatim
```

Expected: PASS. If it fails, fix only the Manual snapshot/mapping path; do not weaken publication validation.

- [ ] **Step 3: Run focused regressions**

```bash
python3 -m pytest -q \
  tests/test_manual_update_mode.py \
  tests/test_mercado_livre_manual_fallback.py \
  tests/test_shein_manual_fallback.py \
  tests/connectors/test_mercado_livre.py \
  tests/test_fetch_url_selection.py \
  tests/test_security.py \
  tests/test_product_persistence_verification.py
```

Expected: all selected tests PASS.

- [ ] **Step 4: Run full suite as a regression-count check**

```bash
python3 -m pytest -q
```

Expected: no new failures beyond the repository's previously known row-layout baseline. Record the exact pass/fail/skip counts in the implementation checkpoint.

- [ ] **Step 5: Run diff validation**

```bash
git diff --check
git status --short
```

Expected: clean diff formatting and no unexpected generated files.

- [ ] **Step 6: Commit any test-only additions**

```bash
git add tests/test_manual_update_mode.py
git commit -m "test: cover manual catalog publication"
```

If no files changed after the previous commit, skip this commit.

---

## Plan Completion Gate

This plan is complete when `Manual` is accepted by the model, Manual rows bypass connectors, reviewed fields are published through existing safety/persistence logic, and focused Automatic/Blocked/fallback regressions remain green.
