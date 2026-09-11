# Generic Affiliate Query Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable `affiliate_query_merge` strategy so Orvani can combine a product URL with a single affiliate base URL, starting with Contingência Máxima, while preserving the existing `LibreOffice -> Importações -> Produtos -> site` flow.

**Architecture:** Add a small pure URL-composition module for the LibreOffice client, route normalization/validation/hash/payload through a prepared-row function, register Contingência Máxima consistently in LibreOffice, backend automation, and frontend allowlists, and keep existing partner behavior unchanged. The final affiliate URL is composed once before upload; `Importações`, `Produtos`, Divulgação, and the site consume that persisted final URL.

**Tech Stack:** Python 3, pytest, LibreOffice UNO/PyUNO, Google Apps Script JavaScript, Node.js `node:test`, existing Orvani automation modules, Git worktrees.

**Spec:** `docs/superpowers/specs/2026-09-11-generic-affiliate-query-merge-design.md`

## Global Constraints

- Version 1 supports only query-parameter inheritance via `affiliate_query_merge`.
- Do not create cookies, scrape affiliate rules, automate logins, or implement redirect/path-template strategies.
- Both product and affiliate URLs must use HTTPS.
- Product and affiliate URLs must resolve to the same configured partner/domain family.
- Product scheme/host/path/fragment come from the product URL.
- Product-only query parameters are preserved.
- Affiliate query parameters override product parameters with the same key.
- Duplicate values for the same affiliate query key are preserved.
- The affiliate base URL must contain at least one query parameter.
- Fail closed: invalid/incompatible affiliate composition produces `ERRO LOCAL` and must not be uploaded.
- The Calc-entered affiliate base URL must not be overwritten in the workbook.
- `Importações` and `Produtos` keep their existing columns and receive the final composed affiliate URL.
- Existing Mercado Livre, Shopee, SHEIN, and Amazon behavior must not regress.
- The implementation must use TDD: RED before production changes, then GREEN, then regression verification.
- Work must happen in an isolated worktree/branch; do not merge or push until the manual end-to-end test passes.
- If `fix/catalog-close-lifecycle` or another unrelated worktree is still active, do not alter, merge, or delete it as part of this feature.

---

## File Structure

### New files

- `libreoffice_sync/affiliate_urls.py`
  - Pure partner-query composition logic.
  - Defines `AffiliateUrlError`.
  - Defines the local query-merge partner registry.
  - Exposes `compose_affiliate_url(product_url, affiliate_url, partner) -> str`.

- `libreoffice_sync/preparation.py`
  - Converts a raw `CatalogRow` into the effective row used for validation/hash/upload.
  - Calls existing normalization first.
  - Applies `affiliate_query_merge` only to configured partners.
  - Exposes `prepare_catalog_row(row: CatalogRow) -> CatalogRow`.

- `tests/libreoffice_sync/test_affiliate_urls.py`
  - Pure URL-composition behavior and security tests.

- `tests/libreoffice_sync/test_preparation.py`
  - Verifies raw Calc values remain conceptually separate while effective payload uses the composed link.

### Existing files to modify

- `libreoffice_sync/normalization.py`
  - Recognize/canonicalize `Contingência Máxima`.
  - Infer the partner from `contingenciamaxima.com.br`.

- `libreoffice_sync/validation.py`
  - Add `Contingência Máxima` to allowed local partners.
  - Validate the prepared effective row.
  - Convert `AffiliateUrlError` into `LocalValidationError`.

- `libreoffice_sync/hashing.py`
  - Build payload/hash from `prepare_catalog_row(row)` so the hash reflects the effective affiliate URL.

- `libreoffice_sync/sync_service.py`
  - Validate before hashing so an invalid composition becomes `ERRO LOCAL` instead of escaping from `row_hash`.
  - Keep upload metadata/hash tied to the effective row.

- `libreoffice_sync/workbook_init.py`
  - Add `Contingência Máxima` to the Plataforma dropdown.

- `automation/config.py`
  - Register `contingencia_maxima` with display label and allowed host.

- `automation/sync.py`
  - Ensure canonical partner-key handling accepts `Contingência Máxima`.
  - Preserve Manual-mode publication and partner-link validation for the new partner.

- `script.js`
  - Add `contingencia_maxima` to `CONFIG.affiliatePartners` with only `contingenciamaxima.com.br`.

### Existing tests to modify

- `tests/libreoffice_sync/test_validation.py`
- `tests/libreoffice_sync/test_hashing.py`
- `tests/libreoffice_sync/test_sync_service.py`
- `tests/libreoffice_sync/test_workbook_init.py`
- backend automation tests that currently assert the partner registry or supported partner set
- `tests/js/catalog.test.js`

---

### Task 1: Add the pure affiliate query composer

**Files:**
- Create: `libreoffice_sync/affiliate_urls.py`
- Create: `tests/libreoffice_sync/test_affiliate_urls.py`

**Interfaces:**
- Consumes: product URL string, affiliate base URL string, canonical partner display name.
- Produces:
  - `class AffiliateUrlError(ValueError)`
  - `QUERY_MERGE_PARTNERS: Mapping[str, tuple[str, ...]]`
  - `compose_affiliate_url(product_url: str, affiliate_url: str, partner: str) -> str`

- [ ] **Step 1: Write the failing pure-function tests**

Create `tests/libreoffice_sync/test_affiliate_urls.py` with cases equivalent to:

```python
import pytest

from libreoffice_sync.affiliate_urls import (
    AffiliateUrlError,
    compose_affiliate_url,
)


PARTNER = "Contingência Máxima"


def test_query_merge_adds_affiliate_parameter_to_product_path():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result == (
        "https://contingenciamaxima.com.br/produto/123?ref=lukn"
    )


def test_query_merge_preserves_product_only_parameters():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123?cor=azul",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result.endswith("?cor=azul&ref=lukn")


def test_affiliate_parameter_overrides_product_parameter():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123?ref=antigo&cor=azul",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result.endswith("?cor=azul&ref=lukn")


def test_duplicate_affiliate_values_are_preserved():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123",
        "https://contingenciamaxima.com.br?tag=a&tag=b",
        PARTNER,
    )
    assert result.endswith("?tag=a&tag=b")


def test_percent_encoded_values_are_round_tripped_safely():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123?q=fone%20azul",
        "https://contingenciamaxima.com.br?ref=lucas%2Bteste",
        PARTNER,
    )
    assert "q=fone+azul" in result
    assert "ref=lucas%2Bteste" in result


def test_product_fragment_is_preserved():
    result = compose_affiliate_url(
        "https://contingenciamaxima.com.br/produto/123#detalhes",
        "https://contingenciamaxima.com.br?ref=lukn",
        PARTNER,
    )
    assert result.endswith("?ref=lukn#detalhes")


@pytest.mark.parametrize(
    ("product_url", "affiliate_url", "message"),
    [
        (
            "http://contingenciamaxima.com.br/produto/123",
            "https://contingenciamaxima.com.br?ref=lukn",
            "HTTPS",
        ),
        (
            "https://contingenciamaxima.com.br/produto/123",
            "https://outra-loja.example?ref=lukn",
            "incompatíveis",
        ),
        (
            "https://contingenciamaxima.com.br/produto/123",
            "https://contingenciamaxima.com.br",
            "parâmetros",
        ),
    ],
)
def test_query_merge_fails_closed(product_url, affiliate_url, message):
    with pytest.raises(AffiliateUrlError, match=message):
        compose_affiliate_url(product_url, affiliate_url, PARTNER)
```

- [ ] **Step 2: Run the new file and verify RED**

Run:

```bash
/media/lucas/Projetos/Orvani/.venv/bin/python -m pytest -q \
  tests/libreoffice_sync/test_affiliate_urls.py
```

Expected: collection/import failure because `libreoffice_sync.affiliate_urls` does not exist yet.

- [ ] **Step 3: Implement the minimal URL composer**

Create `libreoffice_sync/affiliate_urls.py` using `urllib.parse.urlsplit`, `parse_qsl`, `urlencode`, and `urlunsplit`.

Required shape:

```python
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class AffiliateUrlError(ValueError):
    pass


QUERY_MERGE_PARTNERS = {
    "Contingência Máxima": ("contingenciamaxima.com.br",),
}


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _validated_parts(value: str, field: str):
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError:
        raise AffiliateUrlError(f"{field} é inválido.") from None

    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        raise AffiliateUrlError(f"{field} deve usar HTTPS.")
    return parsed, host


def compose_affiliate_url(
    product_url: str,
    affiliate_url: str,
    partner: str,
) -> str:
    domains = QUERY_MERGE_PARTNERS.get(partner)
    if not domains:
        return str(affiliate_url or "").strip()

    product, product_host = _validated_parts(product_url, "Link Produto")
    affiliate, affiliate_host = _validated_parts(
        affiliate_url,
        "Link Afiliado",
    )

    if not any(
        _host_matches(product_host, domain)
        and _host_matches(affiliate_host, domain)
        for domain in domains
    ):
        raise AffiliateUrlError(
            "Link Produto e Link Afiliado pertencem a domínios incompatíveis."
        )

    affiliate_pairs = parse_qsl(
        affiliate.query,
        keep_blank_values=True,
    )
    if not affiliate_pairs:
        raise AffiliateUrlError(
            "Link Afiliado não possui parâmetros para composição."
        )

    affiliate_keys = {key for key, _ in affiliate_pairs}
    product_pairs = [
        pair
        for pair in parse_qsl(product.query, keep_blank_values=True)
        if pair[0] not in affiliate_keys
    ]
    query = urlencode(
        [*product_pairs, *affiliate_pairs],
        doseq=True,
    )

    return urlunsplit(
        (
            product.scheme,
            product.netloc,
            product.path,
            query,
            product.fragment,
        )
    )
```

Do not fetch URLs or follow redirects.

- [ ] **Step 4: Run the pure-function tests and verify GREEN**

Run the same pytest command.

Expected: all tests in `test_affiliate_urls.py` pass.

- [ ] **Step 5: Commit**

```bash
git add libreoffice_sync/affiliate_urls.py \
  tests/libreoffice_sync/test_affiliate_urls.py
git commit -m "feat: add affiliate query URL composer"
```

---

### Task 2: Prepare effective Calc rows before validation, hash, and upload

**Files:**
- Create: `libreoffice_sync/preparation.py`
- Create: `tests/libreoffice_sync/test_preparation.py`
- Modify: `libreoffice_sync/normalization.py`
- Modify: `libreoffice_sync/validation.py`
- Modify: `libreoffice_sync/hashing.py`
- Modify: `libreoffice_sync/sync_service.py`
- Modify: `tests/libreoffice_sync/test_validation.py`
- Modify: `tests/libreoffice_sync/test_hashing.py`
- Modify: `tests/libreoffice_sync/test_sync_service.py`

**Interfaces:**
- Consumes:
  - `normalize_catalog_row(row: CatalogRow) -> CatalogRow`
  - `compose_affiliate_url(product_url, affiliate_url, partner) -> str`
- Produces:
  - `prepare_catalog_row(row: CatalogRow) -> CatalogRow`
  - `validate_catalog_row(row: CatalogRow) -> CatalogRow` returns the prepared row while remaining compatible with callers that ignore the return value.

- [ ] **Step 1: Write RED tests for partner inference and prepared rows**

Create `tests/libreoffice_sync/test_preparation.py`:

```python
from dataclasses import replace

from libreoffice_sync.preparation import prepare_catalog_row


def test_contingencia_maxima_is_inferred_and_affiliate_link_is_composed(valid_row):
    raw = replace(
        valid_row,
        partner="",
        product_type="Digital",
        product_url=(
            "https://contingenciamaxima.com.br/"
            "produto/9b597da1-2d3a-47e5-86c6-5852f2c68000"
        ),
        affiliate_url="https://contingenciamaxima.com.br?ref=lukn",
    )

    prepared = prepare_catalog_row(raw)

    assert prepared.partner == "Contingência Máxima"
    assert prepared.product_url == raw.product_url
    assert prepared.affiliate_url == (
        raw.product_url + "?ref=lukn"
    )
    assert raw.affiliate_url == (
        "https://contingenciamaxima.com.br?ref=lukn"
    )


def test_existing_partner_link_is_not_rewritten(valid_row):
    prepared = prepare_catalog_row(valid_row)

    assert prepared.affiliate_url == valid_row.affiliate_url
```

Extend `tests/libreoffice_sync/test_hashing.py`:

```python
def test_payload_uses_composed_affiliate_link_for_query_merge_partner(valid_row):
    row = replace(
        valid_row,
        partner="Contingência Máxima",
        product_type="Digital",
        product_url="https://contingenciamaxima.com.br/produto/123",
        affiliate_url="https://contingenciamaxima.com.br?ref=lukn",
    )

    payload = editable_payload(row)

    assert payload["Link do Produto"].endswith("/produto/123")
    assert payload["Link de Afiliado"].endswith(
        "/produto/123?ref=lukn"
    )


def test_hash_changes_when_affiliate_tracking_parameter_changes(valid_row):
    base = replace(
        valid_row,
        partner="Contingência Máxima",
        product_type="Digital",
        product_url="https://contingenciamaxima.com.br/produto/123",
        affiliate_url="https://contingenciamaxima.com.br?ref=lukn",
    )

    assert row_hash(base) != row_hash(
        replace(
            base,
            affiliate_url=(
                "https://contingenciamaxima.com.br?ref=outro"
            ),
        )
    )
```

Extend `tests/libreoffice_sync/test_validation.py`:

```python
def test_query_merge_domain_mismatch_is_local_validation_error(valid_row):
    row = replace(
        valid_row,
        partner="Contingência Máxima",
        product_type="Digital",
        product_url="https://contingenciamaxima.com.br/produto/123",
        affiliate_url="https://outra-loja.example?ref=lukn",
    )

    with pytest.raises(LocalValidationError, match="incompatíveis"):
        validate_catalog_row(row)
```

- [ ] **Step 2: Run these tests and verify RED**

Run:

```bash
/media/lucas/Projetos/Orvani/.venv/bin/python -m pytest -q \
  tests/libreoffice_sync/test_preparation.py \
  tests/libreoffice_sync/test_hashing.py \
  tests/libreoffice_sync/test_validation.py
```

Expected: failures because Contingência Máxima/preparation do not exist.

- [ ] **Step 3: Extend normalization for Contingência Máxima**

In `libreoffice_sync/normalization.py`:

Add host inference:

```python
if _host_matches(host, "contingenciamaxima.com.br"):
    return "Contingência Máxima"
```

Add canonical aliases:

```python
"contingencia maxima": "Contingência Máxima",
```

Extend the allowed local canonical partner set:

```python
allowed_partners = {
    "Mercado Livre",
    "Shopee",
    "SHEIN",
    "Amazon",
    "Contingência Máxima",
}
```

- [ ] **Step 4: Add `prepare_catalog_row`**

Create `libreoffice_sync/preparation.py`:

```python
from __future__ import annotations

from dataclasses import replace

from .affiliate_urls import compose_affiliate_url
from .models import CatalogRow
from .normalization import normalize_catalog_row


def prepare_catalog_row(row: CatalogRow) -> CatalogRow:
    normalized = normalize_catalog_row(row)
    effective_affiliate_url = compose_affiliate_url(
        normalized.product_url,
        normalized.affiliate_url,
        normalized.partner,
    )
    return replace(
        normalized,
        affiliate_url=effective_affiliate_url,
    )
```

Because `compose_affiliate_url` returns the original affiliate URL for partners that do not use the strategy, existing partners remain unchanged.

- [ ] **Step 5: Route validation and hashing through preparation**

In `libreoffice_sync/validation.py`:

```python
from .affiliate_urls import AffiliateUrlError
from .preparation import prepare_catalog_row
```

Extend:

```python
PARTNERS = {
    "Mercado Livre",
    "Shopee",
    "SHEIN",
    "Amazon",
    "Contingência Máxima",
}
```

At the start of `validate_catalog_row`, replace direct normalization with:

```python
def validate_catalog_row(row: CatalogRow) -> CatalogRow:
    try:
        row = prepare_catalog_row(row)
    except AffiliateUrlError as exc:
        raise LocalValidationError(str(exc)) from None
```

Keep all existing field checks and add at the end:

```python
    return row
```

In `libreoffice_sync/hashing.py`, replace the normalization import/call with:

```python
from .preparation import prepare_catalog_row
```

and:

```python
def editable_payload(row: CatalogRow) -> dict[str, object]:
    row = prepare_catalog_row(row)
```

- [ ] **Step 6: Move SyncService validation before hashing**

The current `_prepare_changed()` computes `row_hash(row)` before catching validation errors. Change only this ordering.

Required behavior:

```python
for row in rows:
    try:
        prepared = validate_catalog_row(row)
    except LocalValidationError as exc:
        self.workbook.write_local_error(row.row_number, str(exc))
        continue

    current_hash = row_hash(prepared)
    self.workbook.write_row_hash(row.row_number, current_hash)
    self.workbook.clear_local_error(row.row_number)

    if current_hash != row.acknowledged_hash:
        pending.append(editable_payload(prepared))
        metadata[row.automation_id] = (
            row.row_number,
            current_hash,
        )
```

This prevents malformed composition from escaping before `ERRO LOCAL`.

Add to `tests/libreoffice_sync/test_sync_service.py` a regression such as:

```python
def test_invalid_query_merge_stays_local_and_is_not_uploaded(valid_row):
    row = replace(
        valid_row,
        partner="Contingência Máxima",
        product_type="Digital",
        product_url="https://contingenciamaxima.com.br/produto/123",
        affiliate_url="https://outra-loja.example?ref=lukn",
        acknowledged_hash="old",
    )
    wb = FakeWorkbook([row])
    api = FakeApi()
    service = SyncService(wb, api)
    wb.saved = True

    service.run_once(1.0)

    assert api.upserts == []
    assert "incompatíveis" in wb.errors[2]
```

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```bash
/media/lucas/Projetos/Orvani/.venv/bin/python -m pytest -q \
  tests/libreoffice_sync/test_affiliate_urls.py \
  tests/libreoffice_sync/test_preparation.py \
  tests/libreoffice_sync/test_validation.py \
  tests/libreoffice_sync/test_hashing.py \
  tests/libreoffice_sync/test_sync_service.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add libreoffice_sync/normalization.py \
  libreoffice_sync/preparation.py \
  libreoffice_sync/validation.py \
  libreoffice_sync/hashing.py \
  libreoffice_sync/sync_service.py \
  tests/libreoffice_sync/test_preparation.py \
  tests/libreoffice_sync/test_validation.py \
  tests/libreoffice_sync/test_hashing.py \
  tests/libreoffice_sync/test_sync_service.py
git commit -m "feat: prepare effective affiliate links before sync"
```

---

### Task 3: Add Contingência Máxima to the LibreOffice UI contract

**Files:**
- Modify: `libreoffice_sync/workbook_init.py`
- Modify: `tests/libreoffice_sync/test_workbook_init.py`

**Interfaces:**
- Consumes: existing Calc `Plataforma` validation range.
- Produces: dropdown containing exactly the existing partners plus `Contingência Máxima`.

- [ ] **Step 1: Update the existing dropdown assertion first**

Change the partner assertion in `tests/libreoffice_sync/test_workbook_init.py` to:

```python
assert partner.Formula1 == (
    '"Mercado Livre";"Shopee";"SHEIN";"Amazon";'
    '"Contingência Máxima"'
)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
/media/lucas/Projetos/Orvani/.venv/bin/python -m pytest -q \
  tests/libreoffice_sync/test_workbook_init.py
```

Expected: one dropdown assertion failure.

- [ ] **Step 3: Extend the production dropdown**

In `libreoffice_sync/workbook_init.py`, change only the partner list:

```python
(
    "Mercado Livre",
    "Shopee",
    "SHEIN",
    "Amazon",
    "Contingência Máxima",
),
```

Do not add or reorder workbook columns.

- [ ] **Step 4: Run the test and verify GREEN**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add libreoffice_sync/workbook_init.py \
  tests/libreoffice_sync/test_workbook_init.py
git commit -m "feat: add contingencia maxima to catalog partners"
```

---

### Task 4: Register the new partner in backend publication

**Files:**
- Modify: `automation/config.py`
- Modify: `automation/sync.py` only if the current canonical-key mapping does not derive the key automatically
- Modify/Test: the existing automation partner/config tests discovered during execution
- Add a focused test file if no existing focused home exists: `tests/test_contingencia_maxima_partner.py`

**Interfaces:**
- Consumes: persisted `Importações` row where:
  - `Plataforma = "Contingência Máxima"`
  - `Link de Afiliado = "https://contingenciamaxima.com.br/produto/...?..."`
- Produces:
  - canonical backend key `contingencia_maxima`
  - allowed link host `contingenciamaxima.com.br`
  - Manual-mode publication into `Produtos` using the existing 20-column contract.

- [ ] **Step 1: Write backend RED tests**

Create or extend tests with these exact behavioral checks:

```python
from automation.config import PARTNERS


def test_contingencia_maxima_partner_is_registered():
    partner = PARTNERS["contingencia_maxima"]

    assert partner.display_name == "Contingência Máxima"
    assert partner.allowed_hosts == ("contingenciamaxima.com.br",)
    assert partner.live_verified is False
```

Add a publication-level test using the existing `ImportRecord`/`ProductSnapshot` factories:

```python
def test_manual_contingencia_maxima_product_keeps_final_affiliate_url(...):
    affiliate = (
        "https://contingenciamaxima.com.br/produto/123?ref=lukn"
    )

    # Build a Manual ImportRecord and ProductSnapshot using existing
    # test factories, with partner "Contingência Máxima" and affiliate.
    values = map_snapshot_to_product_values(snapshot, record, None)

    assert values[2] == "Contingência Máxima"
    assert values[11] == affiliate
```

If the backend has an existing canonical-key test, add:

```python
assert _canonical_partner_key("Contingência Máxima") == (
    "contingencia_maxima"
)
```

Prefer testing through a public behavior if `_canonical_partner_key` is intentionally private.

- [ ] **Step 2: Run only the new backend tests and verify RED**

Run the narrowest pytest command for the chosen files.

Expected: missing `contingencia_maxima` registration and/or unsupported canonical partner.

- [ ] **Step 3: Register the partner in `automation/config.py`**

Add:

```python
"contingencia_maxima": PartnerConfig(
    "contingencia_maxima",
    "Contingência Máxima",
    ("contingenciamaxima.com.br",),
    False,
),
```

Do not give the backend an automatic scraper/fetch connector for this partner.

- [ ] **Step 4: Extend canonical partner mapping only if required**

If `_canonical_partner_key()` currently uses an explicit alias table, add:

```python
"contingência máxima": "contingencia_maxima",
"contingencia maxima": "contingencia_maxima",
```

If it already derives the key from `PARTNERS` display names, make no production change to `automation/sync.py`.

Do not add `contingencia_maxima` to any automatic connector dispatch table.

- [ ] **Step 5: Run backend focused tests and verify GREEN**

Run the new partner tests plus existing automation config/publication tests.

Expected: PASS.

- [ ] **Step 6: Run backend regression suite**

Run the project's existing automation-focused pytest suite. At minimum include tests covering:

- partner URL validation;
- Manual mode;
- `plan_publication`;
- Mercado Livre;
- Shopee;
- SHEIN;
- Amazon;
- Divulgação affiliate URL validation.

Expected: PASS with no changed expectations for existing partners.

- [ ] **Step 7: Commit**

```bash
git add automation/config.py automation/sync.py tests/
git commit -m "feat: register contingencia maxima backend partner"
```

Before committing, inspect `git diff --cached --name-only` and unstage unrelated test files.

---

### Task 5: Authorize Contingência Máxima in the public catalog frontend

**Files:**
- Modify: `script.js`
- Modify: `tests/js/catalog.test.js`

**Interfaces:**
- Consumes: `Produtos` CSV row containing `Plataforma = Contingência Máxima` and an HTTPS affiliate URL on `contingenciamaxima.com.br`.
- Produces: normalized product whose external CTA safely links to the final affiliate URL with the existing sponsored/nofollow/noopener/noreferrer attributes.

- [ ] **Step 1: Extend the frontend partner-registry test first**

In `tests/js/catalog.test.js`, update the test that asserts `Object.keys(core.CONFIG.affiliatePartners)` to include:

```javascript
"contingencia_maxima"
```

Add:

```javascript
test("registers Contingência Máxima with only its approved host", () => {
  assert.equal(
    core.partnerLabel("contingencia_maxima"),
    "Contingência Máxima",
  );
  assert.deepEqual(
    core.CONFIG.affiliatePartners.contingencia_maxima.hosts,
    ["contingenciamaxima.com.br"],
  );
});
```

Add a safe external-link check:

```javascript
test("accepts Contingência Máxima final affiliate product URLs", () => {
  const attributes = core.externalLinkAttributes({
    affiliateUrl:
      "https://contingenciamaxima.com.br/produto/123?ref=lukn",
    name: "Produto digital",
    partner: "contingencia_maxima",
  });

  assert.equal(
    attributes.href,
    "https://contingenciamaxima.com.br/produto/123?ref=lukn",
  );
  assert.equal(
    attributes.rel,
    "sponsored nofollow noopener noreferrer",
  );
});
```

- [ ] **Step 2: Run Node tests and verify RED**

Run:

```bash
node --test tests/js/catalog.test.js
```

Expected: failures for missing frontend partner.

- [ ] **Step 3: Add the frontend registry entry**

In `script.js`, add alongside the existing partners:

```javascript
contingencia_maxima: {
  label: "Contingência Máxima",
  hosts: ["contingenciamaxima.com.br"],
},
```

Do not add wildcard hosts or redirect domains.

- [ ] **Step 4: Run frontend tests and verify GREEN**

Run:

```bash
node --test tests/js/catalog.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add script.js tests/js/catalog.test.js
git commit -m "feat: authorize contingencia maxima catalog links"
```

---

### Task 6: Add the approved spec to the repository and run full feature regression

**Files:**
- Create: `docs/superpowers/specs/2026-09-11-generic-affiliate-query-merge-design.md`
- Create: `docs/superpowers/plans/2026-09-11-generic-affiliate-query-merge.md`

**Interfaces:**
- Consumes: approved design and this implementation plan.
- Produces: repository-local documentation that travels with the feature branch.

- [ ] **Step 1: Copy the approved design into the repository**

Source during execution:

```text
/mnt/data/2026-09-11-generic-affiliate-query-merge-design.md
```

Destination:

```text
docs/superpowers/specs/2026-09-11-generic-affiliate-query-merge-design.md
```

Verify byte-for-byte or text equality after copying.

- [ ] **Step 2: Copy this implementation plan into the repository**

Source during execution:

```text
/mnt/data/2026-09-11-generic-affiliate-query-merge.md
```

Destination:

```text
docs/superpowers/plans/2026-09-11-generic-affiliate-query-merge.md
```

- [ ] **Step 3: Run Python feature/regression tests**

Run:

```bash
/media/lucas/Projetos/Orvani/.venv/bin/python -m pytest -q \
  tests/libreoffice_sync \
  tests/test_linux_service_files.py
```

Then run the automation/backend test selection used by the repository for partner/publication behavior.

Do not dismiss pre-existing broad-suite failures without reproducing them on `main`; if a new failure appears on the feature branch and not on `main`, treat it as a regression.

- [ ] **Step 4: Run JavaScript tests**

Run:

```bash
node --test tests/js/catalog.test.js
```

If the repository defines additional JS test files, run the existing full Node test command as well.

- [ ] **Step 5: Run static checks**

Run:

```bash
git diff --check
bash -n scripts/orvani-sync-launcher.sh
bash -n scripts/orvani-catalog-launcher.sh
bash -n scripts/install-orvani-sync.sh
```

No formatting or shell syntax errors are allowed.

- [ ] **Step 6: Commit documentation**

```bash
git add docs/superpowers/specs/2026-09-11-generic-affiliate-query-merge-design.md \
  docs/superpowers/plans/2026-09-11-generic-affiliate-query-merge.md
git commit -m "docs: add affiliate query merge design and plan"
```

---

### Task 7: Install feature branch locally and perform the real end-to-end test

**Files:**
- No new source files unless the runtime installer requires no-code regeneration from the committed branch.
- Runtime uses the feature worktree version.

**Interfaces:**
- Consumes: completed feature branch with all automated tests GREEN.
- Produces: evidence that a real Contingência Máxima product travels from Calc to `Importações` and then `Produtos` with the final affiliate URL.

- [ ] **Step 1: Re-run fresh verification immediately before runtime installation**

Run all focused Python and Node tests from Tasks 1–6 again.

Expected: PASS.

- [ ] **Step 2: Install the feature worktree runtime**

Use the existing supported installer from the feature worktree:

```bash
bash scripts/install-orvani-sync.sh
```

Preserve the existing `ORVANI_SYNC_SECRET`, workbook path, 10-second poll configuration, enabled state, and dedicated LibreOffice profile behavior.

Do not modify unrelated systemd lifecycle work as part of this feature.

- [ ] **Step 3: Start/restart only the Orvani sync user service**

Use:

```bash
systemctl --user restart orvani-sync
systemctl --user is-active orvani-sync
systemctl --user is-enabled orvani-sync
```

Expected:

```text
active
enabled
```

- [ ] **Step 4: Enter one real Contingência Máxima test product in Orvani.ods**

Use:

```text
Tipo:
Digital

Plataforma:
Contingência Máxima

Link Produto:
https://contingenciamaxima.com.br/produto/9b597da1-2d3a-47e5-86c6-5852f2c68000

Link Afiliado:
https://contingenciamaxima.com.br?ref=lukn

Modo Atualização:
Manual
```

Fill the other currently required publication fields using real product data.

- [ ] **Step 5: Save and verify `Importações`**

After `Ctrl+S`, verify the matching `ID Automação` row in `Importações`.

Required evidence:

```text
Link do Produto =
https://contingenciamaxima.com.br/produto/9b597da1-2d3a-47e5-86c6-5852f2c68000

Link de Afiliado =
https://contingenciamaxima.com.br/produto/9b597da1-2d3a-47e5-86c6-5852f2c68000?ref=lukn

Plataforma =
Contingência Máxima
```

The Calc `Link Afiliado` cell itself must still show the original base URL:

```text
https://contingenciamaxima.com.br?ref=lukn
```

- [ ] **Step 6: Verify publication into `Produtos`**

Wait for the existing pending workflow.

Verify the corresponding `Produtos` row contains:

```text
Plataforma = Contingência Máxima
Tipo = Digital
Link de Afiliado =
https://contingenciamaxima.com.br/produto/9b597da1-2d3a-47e5-86c6-5852f2c68000?ref=lukn
```

No extra column may have been created.

- [ ] **Step 7: Verify the site CTA**

Open the product in the local/served Orvani site and inspect/click the CTA.

Required result:

- destination is the exact final product affiliate URL;
- link opens externally using the existing safe attributes;
- no frontend rejection occurs for the partner.

Do not claim commission attribution from this technical test; attribution must still be confirmed through the affiliate platform's own tracking/panel.

- [ ] **Step 8: Verify fail-closed behavior with one temporary invalid row**

Create a temporary non-published test row using:

```text
Link Produto:
https://contingenciamaxima.com.br/produto/123

Link Afiliado:
https://example.com?ref=lukn
```

Save.

Expected in Calc:

```text
Status = ERRO LOCAL
Mensagem contains = domínios incompatíveis
```

Verify no corresponding `Importações` upsert occurs.

Remove/repair the temporary test row afterward.

- [ ] **Step 9: Stop and request user approval before merge**

At this checkpoint report:

- automated test results;
- exact real composed URL observed in `Importações`;
- exact URL observed in `Produtos`;
- frontend CTA result;
- fail-closed test result;
- branch/worktree name and latest commit SHA.

Do not merge or push until the user explicitly approves the tested feature.

---

### Task 8: Finish the feature branch only after manual approval

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes: explicit user approval after Task 7.
- Produces: verified `main`/`origin/main` containing the feature, with only this feature worktree/branch cleaned up.

- [ ] **Step 1: Invoke the finishing-a-development-branch workflow**

Use the repository's standard finishing skill/process.

Verify the feature worktree is clean.

- [ ] **Step 2: Verify local main matches the expected remote base before merge**

Run:

```bash
git fetch origin
git status --short
git rev-parse main
git rev-parse origin/main
```

If `main` and `origin/main` diverged during feature work, stop and reconcile safely; do not force-push.

- [ ] **Step 3: Fast-forward merge**

From the main checkout:

```bash
git merge --ff-only <feature-branch>
```

A non-fast-forward result is a stop condition.

- [ ] **Step 4: Re-run the same fresh automated verification on main**

Run the Python, backend, Node, and static-check commands from Task 6.

Expected: PASS.

- [ ] **Step 5: Push main and verify remote SHA**

Run:

```bash
git push origin main
git ls-remote origin refs/heads/main
git rev-parse main
```

The remote SHA must equal local `main`.

- [ ] **Step 6: Clean only this feature worktree and branch**

Remove only the worktree/branch created for this feature.

Do not touch older worktrees such as unrelated LibreOffice lifecycle or baseline worktrees unless separately verified and explicitly requested.

- [ ] **Step 7: Final runtime verification**

Verify:

```bash
systemctl --user is-active orvani-sync
systemctl --user is-enabled orvani-sync
```

Expected:

```text
active
enabled
```

Open Orvani Catálogo once and verify the Plataforma dropdown still includes `Contingência Máxima`.
