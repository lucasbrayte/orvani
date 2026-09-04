# Amazon Manual Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Amazon as a supported Orvani partner through the existing LibreOffice → Importações → backend → Produtos flow, using Automatic mode with a safe Calc-data fallback and no Amazon API.

**Architecture:** Register Amazon in the backend allowlist, derive identity only from a direct amazon.com.br product URL using a 10-character ASIN, and convert compatible automatic-fetch failures into a validated ProductSnapshot built from reviewed Calc data. Extend the LibreOffice normalization/validation/dropdown and expose Amazon in the existing public partner footer without changing the catalog architecture.

**Tech Stack:** Python 3, pytest, LibreOffice UNO client, Google Sheets synchronization, vanilla JavaScript/Node test runner, Git worktrees.

**Spec:** `docs/superpowers/specs/2026-09-04-orvani-amazon-manual-fallback-design.md`

## Global Constraints

- Amazon remains `Modo Atualização = Automático` in Calc.
- No Amazon API, scraping, cookies, credentials, tokens, or affiliate-link generation are added.
- Product identity comes only from a direct HTTPS `amazon.com.br` URL containing a valid 10-character ASCII alphanumeric ASIN.
- `amzn.to` is accepted only as an affiliate URL, never as an ASIN source.
- Temporary fetch failures are not silently converted into fallback success.
- Existing Mercado Livre, Shopee, SHEIN, Manual, and Bloqueado behavior must not regress.
- The existing `Orvani.ods` is never recreated or replaced merely to add Amazon.

---

### Task 1: Lock the Amazon contract with failing tests

**Files:**
- Create: `tests/test_amazon_manual_fallback.py`
- Create: `tests/libreoffice_sync/test_amazon_partner.py`
- Modify: `tests/libreoffice_sync/test_workbook_init.py`
- Modify: `tests/js/catalog.test.js`

**Interfaces:**
- Produces test expectations for `PARTNERS["amazon"]`, `_extract_amazon_asin`, `_manual_amazon_snapshot`, retry selection, Calc partner normalization, exact dropdown order, and footer partner exposure.

- [ ] **Step 1: Write the Amazon backend tests**

Cover direct `/dp/`, `/gp/product/`, `/gp/aw/d/` ASIN extraction, malicious/short-link rejection for identity, allowlisted affiliate URLs, fallback publication, validation failures, and retry readiness.

- [ ] **Step 2: Write the Calc and frontend contract tests**

Require `Amazon` in local partner normalization/validation, exact Platform dropdown order `Mercado Livre;Shopee;SHEIN;Amazon`, and footer labels `Mercado Livre`, `SHEIN`, `Shopee`, `Amazon`.

- [ ] **Step 3: Run RED**

```bash
python3 -m pytest -q tests/test_amazon_manual_fallback.py
python3 -m pytest -q tests/libreoffice_sync/test_amazon_partner.py tests/libreoffice_sync/test_workbook_init.py
node --test tests/js/catalog.test.js
```

Expected: each area fails because Amazon is not yet implemented in that layer.

---

### Task 2: Add backend Amazon support and fallback

**Files:**
- Modify: `automation/config.py`
- Modify: `automation/sync.py`

**Interfaces:**
- Produces `PARTNERS["amazon"]`, `_extract_amazon_asin(value) -> str | None`, `_manual_amazon_snapshot(record, fetched_at) -> ProductSnapshot`, and `_manual_amazon_fallback_ready(record) -> bool`.

- [ ] **Step 1: Add the Amazon partner allowlist**

Configure key `amazon`, display name `Amazon`, hosts `amazon.com.br` and `amzn.to`, with `live_verified=False`.

- [ ] **Step 2: Implement ASIN extraction**

Accept only HTTPS/direct Amazon-host path identity through `/dp/<ASIN>`, `/gp/product/<ASIN>`, or `/gp/aw/d/<ASIN>`, requiring exactly 10 ASCII alphanumeric characters.

- [ ] **Step 3: Implement the Calc-data fallback**

Validate direct product URL, affiliate URL, ASIN, name, prices, and at least one HTTPS image. Build a ProductSnapshot with `partner="amazon"`, preserve reviewed values, and use safe defaults only for optional catalog text.

- [ ] **Step 4: Route compatible automatic failures and retry persisted errors**

Convert only `UnsupportedUrlError` and `InvalidProductDataError` for canonical Amazon records when fallback validation succeeds. Preserve temporary failure semantics. Set the successful operational message to `Produto publicado via fallback manual da Amazon.`.

- [ ] **Step 5: Run backend GREEN**

```bash
python3 -m pytest -q tests/test_amazon_manual_fallback.py
```

Expected: PASS.

---

### Task 3: Extend LibreOffice and existing workbook validation

**Files:**
- Modify: `libreoffice_sync/normalization.py`
- Modify: `libreoffice_sync/validation.py`
- Modify: `libreoffice_sync/workbook_init.py`
- Modify only if required by the current baseline: `libreoffice_sync/main.py`

**Interfaces:**
- Produces canonical/inferred `Amazon` partner values, local validation acceptance, and idempotent Platform validation on rows 2:2000.

- [ ] **Step 1: Add normalization and safe host inference**

Use exact-domain/subdomain matching for `amazon.com.br` and `amzn.to` and map `amazon` to `Amazon`.

- [ ] **Step 2: Add Amazon to local validation and dropdown**

Set the Platform list to exactly `("Mercado Livre", "Shopee", "SHEIN", "Amazon")`.

- [ ] **Step 3: Preserve the existing workbook**

Reuse `initialize_document()` on the attached workbook; never create a replacement just to update validation.

- [ ] **Step 4: Run LibreOffice GREEN**

```bash
python3 -m pytest -q tests/libreoffice_sync
```

Expected: PASS.

---

### Task 4: Expose Amazon publicly and verify/deploy the complete change

**Files:**
- Modify: `script.js`
- Modify: `tests/js/catalog.test.js`

**Interfaces:**
- Produces `footerPartnerLabels()` returning `Mercado Livre`, `SHEIN`, `Shopee`, `Amazon`; existing frontend Amazon URL hosts remain unchanged.

- [ ] **Step 1: Add Amazon to the curated footer partner keys**

Append `amazon` after `shopee`; do not alter other frontend partner configuration.

- [ ] **Step 2: Run JavaScript GREEN**

```bash
node --check script.js
node --test tests/js/catalog.test.js
```

Expected: PASS.

- [ ] **Step 3: Run regression suites in separate pytest processes**

```bash
python3 -m pytest -q tests/libreoffice_sync
python3 -m pytest -q tests/test_amazon_manual_fallback.py tests/test_manual_update_mode.py tests/test_mercado_livre_manual_fallback.py tests/test_shein_manual_fallback.py tests/test_shopee_automatic_fallback.py tests/test_sync.py tests/test_security.py
python3 -m pytest -q tests/test_product_persistence_verification.py
node --check script.js
node --test tests/js/catalog.test.js
git diff --check
```

Expected: all commands PASS.

- [ ] **Step 4: Commit, fast-forward main, verify again, reinstall the local client, and push**

```bash
git add automation/config.py automation/sync.py libreoffice_sync/normalization.py libreoffice_sync/validation.py libreoffice_sync/workbook_init.py script.js tests/test_amazon_manual_fallback.py tests/libreoffice_sync/test_amazon_partner.py tests/libreoffice_sync/test_workbook_init.py tests/js/catalog.test.js docs/superpowers/specs/2026-09-04-orvani-amazon-manual-fallback-design.md docs/superpowers/plans/2026-09-04-orvani-amazon-manual-fallback.md
git commit -m "feat: add Amazon catalog fallback"
git -C /media/lucas/Projetos/Orvani merge --ff-only feat/amazon-manual-fallback
bash scripts/install-orvani-sync.sh
systemctl --user restart orvani-sync
systemctl --user is-active orvani-sync
git push origin main
```

Expected: local main contains the verified commit, the user service is active, and `origin/main` receives the same commit.
