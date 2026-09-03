# Orvani LibreOffice Sync Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Linux-side Python client that treats the open `Orvani.ods` workbook as the catalog-management UI, uploads changed rows on save, and refreshes backend status every 20 seconds through UNO without rewriting the file externally.

**Architecture:** Keep local pure logic independent from LibreOffice. Models, canonical hashing, validation, protocol signing, and HTTP transport are normal Python modules with unit tests; `uno_client.py` is a thin adapter around the live Calc document; `sync_service.py` coordinates save events and polling in one control loop so UNO writes are serialized.

**Tech Stack:** Python 3.12, stdlib (`dataclasses`, `Decimal`, `hashlib`, `hmac`, `json`, `threading`, `uuid`), `httpx==0.28.1`, LibreOffice UNO via Linux `python3-uno`, pytest 9.1.1.

**Spec:** `docs/superpowers/specs/2026-09-03-libreoffice-orvani-sync-design.md`

## Global Constraints

- Workbook visible sheet is exactly `Catálogo`.
- User-editable columns are A:V.
- Backend-returned columns are W:AA.
- Hidden technical columns are fixed by this plan as AB:AH.
- The client writes only W:AA and AB:AH; it never rewrites A:V during status refresh.
- `Ctrl + S` / LibreOffice `OnSaveDone` is the upload trigger.
- Backend status poll default is 20 seconds.
- Unsynchronized edits remain detectable after restart because acknowledged hash advances only after server acknowledgement.
- No Google password, service-account JSON, or GitHub PAT exists locally.
- Local request signing must be byte-for-byte compatible with the Apps Script canonicalization plan.
- No direct `.ods` package edits while LibreOffice has the workbook open.

---

### Task 1: Define local row/status models and exact workbook columns

**Files:**
- Create: `libreoffice_sync/__init__.py`
- Create: `libreoffice_sync/models.py`
- Create: `libreoffice_sync/workbook_schema.py`
- Create: `tests/libreoffice_sync/test_models.py`

**Interfaces:**
- Produces:
  - `CatalogRow`
  - `BackendStatus`
  - `EDITABLE_COLUMNS`
  - `STATUS_COLUMNS`
  - `TECHNICAL_COLUMNS`
  - `CATALOG_SHEET = "Catálogo"`

Technical columns are fixed as:
- AB `ID Automação`
- AC `ID Externo`
- AD `Último Link Publicado`
- AE `Assinatura`
- AF `Última Sincronização Local`
- AG `Hash da Linha`
- AH `Hash Confirmado`

- [ ] **Step 1: Write failing model/schema tests**

```python
def test_workbook_column_contract_is_stable():
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
```

Add a `CatalogRow` construction test using `Decimal("189.99")`.

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_models.py
```

Expected: import failure because the package does not exist.

- [ ] **Step 3: Implement dataclasses**

Use immutable dataclasses:

```python
@dataclass(frozen=True, slots=True)
class CatalogRow:
    row_number: int
    automation_id: str
    active: str
    publish: str
    featured: str
    order: str
    update_mode: str
    product_url: str
    affiliate_url: str
    partner: str
    name: str
    description: str
    category: str
    subcategory: str
    product_type: str
    current_price: Decimal | None
    previous_price: Decimal | None
    coupon: str
    coupon_expires_at: str
    images: tuple[str, str, str, str]
    button_text: str
    row_hash: str
    acknowledged_hash: str
```

```python
@dataclass(frozen=True, slots=True)
class BackendStatus:
    automation_id: str
    external_id: str
    status: str
    message: str
    discount: str
    last_published_url: str
    data_signature: str
    last_checked_at: str
    last_updated_at: str
```

- [ ] **Step 4: Implement exact column constants**

Use zero-based indexes in `workbook_schema.py`; A=0 through AH=33.

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_models.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add libreoffice_sync tests/libreoffice_sync/test_models.py
git commit -m "feat: define LibreOffice sync models"
```

---

### Task 2: Add canonical row hashing and local validation

**Files:**
- Create: `libreoffice_sync/hashing.py`
- Create: `libreoffice_sync/validation.py`
- Create: `tests/libreoffice_sync/test_hashing.py`
- Create: `tests/libreoffice_sync/test_validation.py`

**Interfaces:**
- Produces:
  - `editable_payload(row: CatalogRow) -> dict[str, object]`
  - `row_hash(row: CatalogRow) -> str`
  - `validate_catalog_row(row: CatalogRow) -> None`
  - `LocalValidationError(ValueError)`

- [ ] **Step 1: Write failing hashing tests**

```python
def test_hash_changes_when_editable_price_changes(valid_row):
    first = row_hash(valid_row)
    second = row_hash(replace(valid_row, current_price=Decimal("190.00")))
    assert first != second


def test_hash_ignores_backend_status_fields(valid_row):
    assert "Status" not in editable_payload(valid_row)
    assert "Mensagem" not in editable_payload(valid_row)
```

- [ ] **Step 2: Write failing validation tests**

```python
@pytest.mark.parametrize("field", ["name", "description", "category", "subcategory", "product_type"])
def test_required_manual_text(field, valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(replace(valid_row, **{field: ""}))


def test_previous_price_must_exceed_current(valid_row):
    with pytest.raises(LocalValidationError):
        validate_catalog_row(
            replace(
                valid_row,
                current_price=Decimal("200.00"),
                previous_price=Decimal("199.00"),
            )
        )
```

- [ ] **Step 3: Run RED**

```bash
python3 -m pytest -q \
  tests/libreoffice_sync/test_hashing.py \
  tests/libreoffice_sync/test_validation.py
```

Expected: import failures.

- [ ] **Step 4: Implement canonical editable payload**

Map to Apps Script transport keys exactly:

```python
def editable_payload(row: CatalogRow) -> dict[str, object]:
    return {
        "ID Automação": row.automation_id,
        "Ativo": row.active,
        "Publicar": row.publish,
        "Destaque": row.featured,
        "Ordem": row.order,
        "Modo de Atualização": row.update_mode,
        "Link do Produto": row.product_url,
        "Link de Afiliado": row.affiliate_url,
        "Plataforma": row.partner,
        "Nome": row.name,
        "Descrição": row.description,
        "Categoria": row.category,
        "Subcategoria": row.subcategory,
        "Tipo": row.product_type,
        "Preço Atual": (
            format(row.current_price, "f") if row.current_price is not None else ""
        ),
        "Preço Anterior": (
            format(row.previous_price, "f") if row.previous_price is not None else ""
        ),
        "Cupom": row.coupon,
        "Validade do Cupom": row.coupon_expires_at,
        "Imagem 1": row.images[0],
        "Imagem 2": row.images[1],
        "Imagem 3": row.images[2],
        "Imagem 4": row.images[3],
        "Texto do Botão": row.button_text,
    }
```

Hash the deterministic JSON:

```python
def row_hash(row: CatalogRow) -> str:
    encoded = json.dumps(
        editable_payload(row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

- [ ] **Step 5: Implement local validation**

Validate `Sim|Não`, update modes `Automático|Manual|Bloqueado`, types `Físico|Digital`, supported initial platforms `Mercado Livre|Shopee|SHEIN`, positive Decimal prices, previous > current, HTTPS product/affiliate/image URLs, and at least one image for `Manual` + `Publicar=Sim`.

Keep errors user-facing and field-specific, for example:

```python
raise LocalValidationError("Preço Atual deve ser maior que zero.")
```

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest -q \
  tests/libreoffice_sync/test_hashing.py \
  tests/libreoffice_sync/test_validation.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add libreoffice_sync/hashing.py libreoffice_sync/validation.py tests/libreoffice_sync
git commit -m "feat: validate and hash Calc catalog rows"
```

---

### Task 3: Implement cross-language HMAC protocol and HTTP client

**Files:**
- Create: `libreoffice_sync/protocol.py`
- Create: `libreoffice_sync/api_client.py`
- Create: `tests/libreoffice_sync/test_protocol.py`
- Create: `tests/libreoffice_sync/test_api_client.py`
- Create: `requirements-libreoffice.txt`

**Interfaces:**
- Produces:
  - `canonical_json(value: object) -> str`
  - `signed_envelope(action: str, payload: dict, secret: str, timestamp: int, nonce: str) -> dict`
  - `OrvaniApiClient.upsert_products(products: Sequence[dict]) -> dict`
  - `OrvaniApiClient.get_status(ids: Sequence[str]) -> tuple[BackendStatus, ...]`
  - `OrvaniApiClient.health() -> dict`

- [ ] **Step 1: Add the shared canonicalization vector**

```python
def test_canonical_json_matches_apps_script_vector():
    value = {"z": 1, "a": {"y": 2, "b": "ç"}, "list": [{"d": 4, "c": 3}]}
    assert canonical_json(value) == (
        '{"a":{"b":"ç","y":2},"list":[{"c":3,"d":4}],"z":1}'
    )
```

- [ ] **Step 2: Add a deterministic signature vector**

```python
def test_signed_envelope_signature_is_stable():
    envelope = signed_envelope(
        "health",
        {},
        secret="0123456789abcdef" * 4,
        timestamp=1788420000,
        nonce="nonce_1234567890abcdef",
    )
    unsigned = {key: envelope[key] for key in (
        "version", "action", "timestamp", "nonce", "payload"
    )}
    expected = hmac.new(
        ("0123456789abcdef" * 4).encode(),
        canonical_json(unsigned).encode(),
        hashlib.sha256,
    ).hexdigest()
    assert envelope["signature"] == expected
```

- [ ] **Step 3: Run RED**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_protocol.py
```

Expected: import failure.

- [ ] **Step 4: Implement protocol**

Use:

```python
def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def signed_envelope(
    action: str,
    payload: dict[str, object],
    *,
    secret: str,
    timestamp: int,
    nonce: str,
) -> dict[str, object]:
    unsigned = {
        "version": "v1",
        "action": action,
        "timestamp": timestamp,
        "nonce": nonce,
        "payload": payload,
    }
    signature = hmac.new(
        secret.encode("utf-8"),
        canonical_json(unsigned).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**unsigned, "signature": signature}
```

- [ ] **Step 5: Add failing API tests with `httpx.MockTransport`**

Test successful `health`, bounded `upsert_products`, status parsing, HTTP 403 as permanent auth error, and 5xx/transport errors as retryable errors.

- [ ] **Step 6: Implement `OrvaniApiClient`**

Constructor:

```python
class OrvaniApiClient:
    def __init__(
        self,
        webapp_url: str,
        secret: str,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], int] | None = None,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        ...
```

Use `timeout=httpx.Timeout(15.0, connect=5.0)` and `follow_redirects=True`. POST JSON envelopes only to the configured HTTPS Web App URL.

- [ ] **Step 7: Pin the local runtime dependency**

`requirements-libreoffice.txt`:

```text
httpx==0.28.1
```

UNO comes from the Linux `python3-uno` system package, not PyPI.

- [ ] **Step 8: Run tests**

```bash
python3 -m pytest -q \
  tests/libreoffice_sync/test_protocol.py \
  tests/libreoffice_sync/test_api_client.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add libreoffice_sync/protocol.py libreoffice_sync/api_client.py \
  tests/libreoffice_sync requirements-libreoffice.txt
git commit -m "feat: add signed Orvani sync client"
```

---

### Task 4: Build the UNO workbook adapter

**Files:**
- Create: `libreoffice_sync/uno_client.py`
- Create: `tests/libreoffice_sync/test_uno_client.py`

**Interfaces:**
- Produces `LibreOfficeWorkbook`:
  - `connect(host="127.0.0.1", port=2002) -> LibreOfficeWorkbook`
  - `attach_expected_document(path: Path) -> bool`
  - `read_catalog_rows() -> tuple[CatalogRow, ...]`
  - `ensure_automation_id(row_number: int) -> str`
  - `write_local_error(row_number: int, message: str) -> None`
  - `write_acknowledged_hash(row_number: int, row_hash: str) -> None`
  - `apply_status(status: BackendStatus) -> bool`
  - `consume_save_event() -> bool`

- [ ] **Step 1: Create fake-UNO tests before importing real `uno`**

The module must import `uno` and `unohelper` lazily inside connection/listener construction so pure unit tests can run on CI without LibreOffice.

Test cell mapping:

```python
def test_read_catalog_row_maps_only_documented_columns(fake_document):
    workbook = LibreOfficeWorkbook.from_document(fake_document, EXPECTED_PATH)
    rows = workbook.read_catalog_rows()
    assert rows[0].name == "Produto teste"
    assert rows[0].current_price == Decimal("189.99")
    assert rows[0].automation_id == "uuid-1"
```

Test status write isolation:

```python
def test_apply_status_never_writes_editable_columns(fake_document):
    workbook = LibreOfficeWorkbook.from_document(fake_document, EXPECTED_PATH)
    before = fake_document.editable_write_count
    workbook.apply_status(sample_status())
    assert fake_document.editable_write_count == before
    assert fake_document.cell(22, 1).String == "PUBLICADO"
```

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_uno_client.py
```

Expected: import failure.

- [ ] **Step 3: Implement document validation**

Require all of:

```python
document.URL == expected_file_url
document.Sheets.hasByName("Catálogo")
```

and exact header strings A1:AH1 for the initialized workbook schema. Refuse arbitrary Calc documents.

- [ ] **Step 4: Implement row reads and technical writes**

Treat row 1 as headers and data as row 2 onward. Stop only after a bounded trailing-empty threshold, not at the first empty row, so gaps are preserved.

Generate missing IDs with:

```python
automation_id = str(uuid.uuid4())
```

and write only AB for that row.

When reading price cells, use numeric `Value` where present and convert through `Decimal(str(value))`; never parse localized currency display text as the primary path.

- [ ] **Step 5: Implement document event listener**

Use `com.sun.star.document.XDocumentEventListener` and mark a thread-safe `threading.Event` when:

```text
EventName == "OnSaveDone"
```

The callback must not perform network or sheet writes; it only signals the service loop.

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_uno_client.py
```

Expected: PASS without LibreOffice installed in the test environment.

- [ ] **Step 7: Commit**

```bash
git add libreoffice_sync/uno_client.py tests/libreoffice_sync/test_uno_client.py
git commit -m "feat: add LibreOffice UNO adapter"
```

---

### Task 5: Create and initialize the `Orvani.ods` workbook schema

**Files:**
- Create: `libreoffice_sync/workbook_init.py`
- Create: `tests/libreoffice_sync/test_workbook_init.py`

**Interfaces:**
- Produces:
  - `initialize_document(document) -> None`
  - visible headers A:AA
  - hidden technical headers AB:AH
  - controlled-value validations and price formatting.

- [ ] **Step 1: Add fake-document initialization tests**

```python
def test_initializer_creates_catalog_headers(fake_blank_document):
    initialize_document(fake_blank_document)
    sheet = fake_blank_document.Sheets.getByName("Catálogo")
    assert sheet.getCellByPosition(0, 0).String == "Ativo"
    assert sheet.getCellByPosition(21, 0).String == "Texto Botão"
    assert sheet.getCellByPosition(22, 0).String == "Status"
    assert sheet.getCellByPosition(27, 0).String == "ID Automação"
    assert sheet.getCellByPosition(33, 0).String == "Hash Confirmado"
```

Add an assertion that columns AB:AH are hidden after initialization.

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_workbook_init.py
```

Expected: import failure.

- [ ] **Step 3: Implement headers and hidden columns**

Create/rename the visible sheet to `Catálogo`, write the fixed headers, freeze the header row, hide AB:AH, and set readable widths for name/description/link columns.

- [ ] **Step 4: Add controlled-value validation**

Apply list validation for a practical initial range, rows 2:2000:

```text
Ativo/Publicar/Destaque: Sim;Não
Modo Atualização: Automático;Manual;Bloqueado
Tipo: Físico;Digital
Plataforma: Mercado Livre;Shopee;SHEIN
```

Use Calc validation APIs through UNO rather than formulas stored in hidden cells.

- [ ] **Step 5: Format prices**

Set N:O as numeric currency-like display while retaining numeric cell values.

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_workbook_init.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add libreoffice_sync/workbook_init.py tests/libreoffice_sync/test_workbook_init.py
git commit -m "feat: initialize Orvani Calc workbook"
```

---

### Task 6: Coordinate save uploads, acknowledgements, and 20-second status polling

**Files:**
- Create: `libreoffice_sync/sync_service.py`
- Create: `tests/libreoffice_sync/test_sync_service.py`

**Interfaces:**
- Produces:
  - `SyncService.run_once(now_monotonic: float) -> None`
  - `SyncService.run_forever() -> None`

- [ ] **Step 1: Write failing save-upload tests with fakes**

```python
def test_save_uploads_only_changed_valid_rows(fake_workbook, fake_api):
    fake_workbook.save_event = True
    fake_workbook.rows = (
        valid_row(row_hash="new", acknowledged_hash="old"),
        valid_row(row_number=3, row_hash="same", acknowledged_hash="same"),
    )
    service = SyncService(fake_workbook, fake_api, poll_seconds=20)

    service.run_once(100.0)

    assert [item["ID Automação"] for item in fake_api.upserts[0]] == ["uuid-1"]
```

Add:

```python
def test_ack_hash_advances_only_after_success(...)
def test_validation_error_is_local_and_not_uploaded(...)
def test_status_poll_updates_only_returned_status_fields(...)
def test_status_poll_runs_after_20_seconds_not_every_tick(...)
```

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_sync_service.py
```

Expected: import failure.

- [ ] **Step 3: Implement save processing**

On save:

1. `read_catalog_rows()`
2. `ensure_automation_id` for non-empty rows missing IDs, then reread that row.
3. compute current hash
4. validate
5. write AG `Hash da Linha`
6. upload only hash != acknowledged hash
7. after accepted response, write AH `Hash Confirmado` and AF `Última Sincronização Local`

Do not acknowledge rows absent from the server success response.

- [ ] **Step 4: Implement status polling**

Every 20 seconds while attached:

```python
ids = [row.automation_id for row in rows if row.automation_id]
statuses = api.get_status(ids)
for status in statuses:
    workbook.apply_status(status)
```

A status update must not trigger an upload because hashing excludes W:AH backend/technical fields.

- [ ] **Step 5: Implement retry classification**

Retry transient `httpx.TransportError`/5xx with bounded exponential delays managed by the service state:

```text
2s, 5s, 15s, 30s, max 60s
```

A permanent auth/validation error writes a local message and waits for configuration/row change rather than tight-loop retrying.

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest -q tests/libreoffice_sync/test_sync_service.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add libreoffice_sync/sync_service.py tests/libreoffice_sync/test_sync_service.py
git commit -m "feat: synchronize Calc saves and status"
```

---

### Task 7: Add configuration and CLI diagnostics

**Files:**
- Create: `libreoffice_sync/config.py`
- Create: `libreoffice_sync/main.py`
- Create: `tests/libreoffice_sync/test_config.py`
- Create: `tests/libreoffice_sync/test_main.py`
- Modify: `.env.example`

**Interfaces:**
- Produces:
  - `LocalSettings.from_env()`
  - CLI commands: `health`, `run`, `init-workbook`.

Required environment:
- `ORVANI_WEBAPP_URL`
- `ORVANI_SYNC_SECRET`
- `ORVANI_WORKBOOK_PATH`
Optional:
- `ORVANI_STATUS_POLL_SECONDS` default `20`
- `ORVANI_UNO_HOST` default `127.0.0.1`
- `ORVANI_UNO_PORT` default `2002`

- [ ] **Step 1: Add failing config tests**

```python
def test_settings_require_https_webapp(monkeypatch):
    monkeypatch.setenv("ORVANI_WEBAPP_URL", "http://example.com")
    monkeypatch.setenv("ORVANI_SYNC_SECRET", "a" * 64)
    monkeypatch.setenv("ORVANI_WORKBOOK_PATH", "/tmp/Orvani.ods")
    with pytest.raises(ConfigurationError):
        LocalSettings.from_env()


def test_poll_default_is_20_seconds(valid_env):
    assert LocalSettings.from_env().poll_seconds == 20
```

- [ ] **Step 2: Run RED**

```bash
python3 -m pytest -q \
  tests/libreoffice_sync/test_config.py \
  tests/libreoffice_sync/test_main.py
```

Expected: import failures.

- [ ] **Step 3: Implement settings**

Require Web App host `script.google.com`, a 64-hex-character secret, absolute workbook path, poll interval 10..300 seconds, and loopback UNO host only in version 1.

- [ ] **Step 4: Implement CLI**

Use `argparse`:

```text
python -m libreoffice_sync.main health
python -m libreoffice_sync.main run
python -m libreoffice_sync.main init-workbook
```

`health` checks API health and UNO connectivity separately and exits non-zero if either fails.

`init-workbook` connects over UNO, creates a new Calc document when needed, applies `initialize_document`, and stores it at `ORVANI_WORKBOOK_PATH`.

- [ ] **Step 5: Update `.env.example` without secrets**

Add only placeholders:

```text
ORVANI_WEBAPP_URL=https://script.google.com/macros/s/DEPLOYMENT_ID/exec
ORVANI_SYNC_SECRET=
ORVANI_WORKBOOK_PATH=/home/user/Documents/Orvani.ods
ORVANI_STATUS_POLL_SECONDS=20
ORVANI_UNO_HOST=127.0.0.1
ORVANI_UNO_PORT=2002
```

- [ ] **Step 6: Run local client suite**

```bash
python3 -m pytest -q tests/libreoffice_sync
```

Expected: PASS.

- [ ] **Step 7: Run repository regressions**

```bash
python3 -m pytest -q \
  tests/libreoffice_sync \
  tests/test_manual_update_mode.py \
  tests/test_security.py \
  tests/test_product_persistence_verification.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add libreoffice_sync tests/libreoffice_sync .env.example
git commit -m "feat: add LibreOffice sync CLI"
```

---

## Plan Completion Gate

This plan is complete when pure client tests pass without UNO installed, a real Linux UNO smoke test can attach to the exact workbook, `Ctrl + S` produces uploads only for changed valid rows, acknowledgements are restart-safe, and backend status appears in W:AA every ~20 seconds without touching A:V.
