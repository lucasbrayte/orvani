# Orvani Affiliate Catalog Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build a safe, review-controlled Python automation that imports and refreshes affiliate products through Google Sheets while preserving the approved static Orvani site and its current public CSV contract.

**Architecture:** A dependency-light Python package separates domain models, SSRF-resistant HTTP, public metadata extraction, store connectors, Google Sheets batching, and synchronization state. The browser continues to read the unchanged 20-column Produtos CSV; focused JavaScript helpers add ordering, coupons, button copy, stable IDs, and TikTok Shop recognition without introducing a frontend toolchain.

**Tech Stack:** Python 3.12; HTTPX 0.28.1; google-api-python-client 2.199.0; google-auth 2.57.0; pytest 9.1.1; standard-library HTMLParser; JavaScript ES2022 with Node.js 24.20.0 native node:test; HTML and CSS.

**Version evidence checked on 2026-08-29:** official PyPI JSON endpoints for httpx, google-api-python-client, google-auth, and pytest; official Node.js distribution index for the current Krypton LTS. README-AUTOMACAO.md must link those primary sources and explain that these are direct pins, while transitive versions remain resolver-managed.

**Spec:** docs/superpowers/specs/2026-08-29-orvani-affiliate-automation-design.md

## Global Constraints

- Preserve index.html, catalogo.html, the approved visual identity, hero, carousel, footer, animations, responsive behavior, and CSP except for a demonstrated requirement.
- Keep the frontend as HTML, CSS, and JavaScript without React, Next.js, TypeScript, npm, bundlers, a visual framework, a server, or a database.
- Keep spreadsheet ID 1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0, products GID 952991100, and the published CSV URL unchanged.
- Preserve the exact 20 Produtos headers and their order; never add a product column or delete a product row.
- Never write to the real spreadsheet until the owner separately authorizes the first write after reviewing validate and both dry runs.
- Never create or use external credentials, change spreadsheet permissions, authorize an unconfirmed store domain, deploy, or publish artifacts containing source pages or spreadsheet data.
- Never use buyer or affiliate login, browser cookies, browser tokens, Selenium, Playwright, CAPTCHA bypass, or antibot circumvention.
- Keep all domain prices as Decimal; convert to a JSON number only at the Google Sheets transport boundary because that API cannot serialize Decimal.
- Keep network tests disabled unless RUN_LIVE_TESTS=1; default suites use sanitized local fixtures and fakes.
- Preserve the original affiliate URL for publication; resolved URLs are identification and fetch inputs only.
- Treat missing SHEIN and TikTok Shop samples as explicit production-validation limitations, not successful live connectors.
- Keep TikTok Shop's production host allowlist empty until the owner supplies an official sample.
- Use TDD for every production behavior: add a focused failing test, observe the expected failure, implement the minimum behavior, and rerun focused and related suites.
- Make thematic commits after each task; do not rewrite checkpoint 0dd7c88d57df2053b67f12720d8df13f573373de.

## File Map

### Python package

- automation/__init__.py: package version only.
- automation/config.py: Sheets headers, settings, partner allowlists, limits, and deterministic category rules.
- automation/models.py: enums, snapshots, row models, updates, reports, and typed errors.
- automation/security.py: HTTPS parsing, host matching, DNS/IP policy, normalization, and sanitized logs.
- automation/http_client.py: manual redirects, bounded responses, content checks, and retry.
- automation/metadata.py: HTML parsing, JSON-LD, Open Graph, Decimal parsing, text cleanup, and images.
- automation/categorizer.py: central category mapping and confidence.
- automation/connectors/base.py: connector protocol, common builder, and registry.
- automation/connectors/mercado_livre.py, shopee.py, shein.py, tiktok_shop.py: isolated partners.
- automation/sheets.py: service-account client, schemas, typed reads, setup, and batches.
- automation/sync.py: queue selection, signatures, state, preservation, adoption, mapping, and orchestration.
- automation/cli.py: required commands and dry-run gates.

### Tests, operations, and frontend

- tests/conftest.py: reusable snapshots, rows, fake DNS/HTTP, and fake Sheets.
- tests/test_*.py and tests/connectors/test_*.py: offline suites.
- tests/fixtures: minimal sanitized HTML, JSON, and current CSV examples.
- tests/live/test_store_smoke.py: opt-in read-only checks.
- tests/js/catalog.test.js: Node-native adapter and presentation tests.
- .env.example, .gitignore, requirements.txt, requirements-dev.txt: environment and dependencies.
- .github/workflows/sync-affiliates.yml: manual and scheduled execution.
- README-AUTOMACAO.md: Brazilian Portuguese operator guide.
- docs/spikes/2026-08-29-store-viability.md: sanitized spike evidence.
- script.js: adapter, ordering, coupon/button helpers, identity, TikTok label, and five-minute refresh.
- style.css: coupon badge and expiry copy only.

---

### Task 1: Read-only store viability spike

**Files:**
- Create: docs/spikes/2026-08-29-store-viability.md
- Inspect without modifying: public Produtos CSV and current Mercado Livre/Shopee URLs

**Interfaces:**
- Consumes: existing CSV URL and host rules in script.js.
- Produces: sanitized per-store status, redirect hosts, terminal HTTP status/content type, size result, and structured-field availability.

- [ ] **Step 1: Confirm Git and CSV baseline**

Run git status --short --branch and git rev-parse HEAD. Then use a standard-library read-only script to download at most 2,000,001 bytes from the fixed CSV with User-Agent Orvani-read-only-spike/1.0, locate the exact 20 headers, and print only header row, byte count, accepted count, and rejected row/platform/name/host.

Expected: header row 4, 11 accepted rows, and the Hotmart domain mismatch preserved.

- [ ] **Step 2: Probe current store links without tracking-data output**

Use a mktemp Python script outside the repository. Disable automatic redirects with a custom HTTPRedirectHandler; allow only mercadolivre.com.br/meli.la or shopee.com.br/s.shopee.com.br; validate every Location; reject every DNS answer whose ipaddress.ip_address(address).is_global is false; stop after five redirects; enforce 5-second connect, 15-second read, and 2 MB body limits.

The only page markers printed are:

~~~python
markers = {
    "json_ld": "application/ld+json" in html.lower(),
    "og_title": 'property="og:title"' in html.lower(),
    "og_image": 'property="og:image"' in html.lower(),
    "structured_price": any(token in html.lower() for token in ('"price"', "product:price:amount")),
}
~~~

Print row, partner, hostname, status, media type, size result, and markers. Never print or save affiliate URLs, queries, fragments, response bodies, paths, or cookies.

- [ ] **Step 3: Write and commit factual findings**

Record UTC time, sample count, sanitized hosts, status/media type, markers, and one outcome per store: VIÁVEL POR API/METADADOS, SEMIAUTOMÁTICO, or BLOQUEADO. State that SHEIN and TikTok Shop lack samples and no write occurred.

~~~bash
git diff --check
git add docs/spikes/2026-08-29-store-viability.md
git commit -m "docs: registrar spike publico das lojas"
~~~

### Task 2: Dependencies, configuration, and domain models

**Files:**
- Create: automation/__init__.py
- Create: automation/config.py
- Create: automation/models.py
- Create: tests/conftest.py
- Create: tests/test_models.py
- Create: requirements.txt
- Create: requirements-dev.txt
- Create: .env.example
- Create: .gitignore

**Interfaces:**
- Consumes: approved constants.
- Produces: Settings.from_env(), PartnerConfig, ImportStatus, UpdateMode, ProductSnapshot, ImportRecord, ProductRow, SheetUpdate, SyncReport, and typed errors.

- [ ] **Step 1: Add pinned dependencies and secret exclusions**

requirements.txt:

~~~text
httpx==0.28.1
google-api-python-client==2.199.0
google-auth==2.57.0
~~~

requirements-dev.txt:

~~~text
-r requirements.txt
pytest==9.1.1
~~~

.env.example contains only a redacted JSON placeholder, the fixed spreadsheet ID, Importações, and Produtos. .gitignore includes .env, .env.*, !.env.example, *service-account*.json, credentials*.json, __pycache__/, .pytest_cache/, .coverage, htmlcov/, and .venv/.

- [ ] **Step 2: Write failing model tests**

~~~python
def test_headers_preserve_contract():
    assert len(PRODUCTS_HEADERS) == 20
    assert PRODUCTS_HEADERS[0] == "Ativo *"
    assert PRODUCTS_HEADERS[-1] == "Destaque"
    assert len(IMPORT_HEADERS) == 32


def test_snapshot_discards_non_discount_previous_price(snapshot_kwargs):
    value = ProductSnapshot(
        **snapshot_kwargs,
        current_price=Decimal("100.00"),
        previous_price=Decimal("90.00"),
    )
    assert value.previous_price is None


def test_snapshot_rejects_zero(snapshot_kwargs):
    with pytest.raises(InvalidProductDataError):
        ProductSnapshot(**snapshot_kwargs, current_price=Decimal("0"))
~~~

Also test all enum values, immutable tuples, four-image maximum, fixed settings, in-memory service-account JSON parsing, and malformed JSON errors without credential text.

- [ ] **Step 3: Observe red state**

Run: python3 -m pytest tests/test_models.py -q

Expected: collection fails because automation is absent.

- [ ] **Step 4: Implement exact domain contracts**

ProductSnapshot is frozen and slotted with partner, external ID, optional catalog ID, source URL, original affiliate URL, name, description, current/previous Decimal, currency, category, subcategory, type, coupon/expiry, four images, availability, and fetched time. Reject nonpositive price; drop previous price not greater than current.

Use exactly:

~~~python
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
    BLOQUEADO = "Bloqueado"
~~~

ImportRecord has all 32 Importações fields plus row_number and link_signature. SheetUpdate has range_name and tuple-of-tuples values. Add ConnectorError, UnsupportedUrlError, ProductNotFoundError, TemporaryFetchError, BlockedByStoreError, InvalidProductDataError, UnsafeUrlError, UnsafeRedirectError, ResponseTooLargeError, UnexpectedContentTypeError, AmbiguousProductMatchError, SheetSchemaError, and ConfigurationError.

ProductRow has row_number plus all 20 current Produtos values and optional reconstructed_external_id/catalog_id fields used only for safe matching. SyncItemResult has row_number, initial_status, final_status, message, and changed booleans. SyncReport has items, planned_import_updates, planned_product_updates, dry_run, and final_status(row_number), which raises KeyError for an unreported row.

When parsing a new Importações row, generate a UUID4 string only if ID Automação is blank, and return that ID as a planned write; never regenerate a nonblank ID. Defaults are Publicar=Não, Destaque=Não, Modo de Atualização=Automático, Status=NOVO, and Tentativas Consecutivas=0.

Set connect/read timeouts 5/15 seconds, redirect limit 5, body limit 2,000,000, retries 2, description limit 4,000, image limit 4. TikTok Shop has allowed_hosts=() and live_verified=False.

- [ ] **Step 5: Verify and commit**

~~~bash
python3 -m pytest tests/test_models.py -q
git add automation requirements.txt requirements-dev.txt .env.example .gitignore tests/conftest.py tests/test_models.py
git commit -m "feat: adicionar modelos e configuracao da automacao"
~~~

### Task 3: URL, DNS, signature, and log security

**Files:**
- Create: automation/security.py
- Create: tests/test_security.py

**Interfaces:**
- Consumes: UnsafeUrlError and UnsafeRedirectError.
- Produces: validate_https_url(), resolve_public_addresses(), normalize_url_for_signature(), sanitize_url_for_log(), and is_allowed_host().

- [ ] **Step 1: Write failing security tests**

~~~python
@pytest.mark.parametrize("url", [
    "http://www.mercadolivre.com.br/item",
    "https://user:secret@www.mercadolivre.com.br/item",
    "https://www.mercadolivre.com.br:444/item",
    "https://www.mercadolivre.com.br\\@evil.example/item",
])
def test_rejects_unsafe_url_shapes(url):
    with pytest.raises(UnsafeUrlError):
        validate_https_url(url, ("mercadolivre.com.br",))


def test_rejects_private_dns_answer():
    resolver = lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))]
    with pytest.raises(UnsafeUrlError):
        resolve_public_addresses("example.com", resolver=resolver)


def test_sanitizes_tracking_url():
    safe = sanitize_url_for_log("https://s.shopee.com.br/AbCd?affiliate_id=secret#fragment")
    assert safe == "https://s.shopee.com.br/[path]"
    assert "secret" not in safe
~~~

Also test valid HTTPS, trailing dots, whitespace, invalid IDNA, loopback/link-local/multicast/reserved IPv4 and IPv6, mixed DNS answers, signature query sorting, and fragment removal.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/test_security.py -q

Expected: import failure for automation.security.

- [ ] **Step 3: Implement strict parsing**

Use urlsplit; reject whitespace/backslash before parsing; require HTTPS, no user/password/port, valid IDNA, and explicit host/suffix matching. Require every resolved ipaddress value to be global. Normalize signatures by lowercasing scheme/host, keeping path, sorting parse_qsl with blank values, rebuilding query, and dropping fragments. Sanitized logs contain host plus root or [path], never userinfo/query/fragment/concrete path.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/test_security.py tests/test_models.py -q
git add automation/security.py tests/test_security.py
git commit -m "feat: proteger urls e resolucao dns"
~~~

### Task 4: Bounded HTTP client with manual redirects

**Files:**
- Create: automation/http_client.py
- Create: tests/test_http_client.py
- Modify: tests/conftest.py

**Interfaces:**
- Consumes: security functions, typed errors, and limits.
- Produces: HttpResponse and SafeHttpClient.get(url, allowed_hosts, expected_content_types).

- [ ] **Step 1: Write failing MockTransport tests**

Cover successful HTML; allowed short redirect; unauthorized redirect; private DNS; 2,000,001-byte body; application/octet-stream; 404; persistent 403 with one call; and 503 then 200 with one backoff call.

~~~python
def test_validates_every_redirect(http_client_factory):
    client = http_client_factory({
        "https://meli.la/a": (302, {"location": "https://evil.example/item"}, b""),
    })
    with pytest.raises(UnsafeRedirectError):
        client.get("https://meli.la/a", ("meli.la", "mercadolivre.com.br"), ("text/html",))


def test_does_not_retry_persistent_403(single_response_client):
    client, calls = single_response_client(403, b"blocked")
    with pytest.raises(BlockedByStoreError):
        client.get("https://example.com/item", ("example.com",), ("text/html",))
    assert calls.count == 1
~~~

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/test_http_client.py -q

Expected: import failure for automation.http_client.

- [ ] **Step 3: Implement bounded fetch**

Use httpx.Client(follow_redirects=False) and stream responses. Validate URL and DNS before every request. Resolve Location with urljoin and revalidate each of 301, 302, 303, 307, 308; reject beyond five. Count chunks and raise before crossing 2 MB. Normalize media type without parameters.

Map 401/403/407 to BlockedByStoreError, 404/410 to ProductNotFoundError, and 408/425/429/500/502/503/504 plus transport timeouts to TemporaryFetchError. Retry temporary failures at most twice with 0.5 and 1.0 second injected sleeps.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/test_security.py tests/test_http_client.py -q
git add automation/http_client.py tests/test_http_client.py tests/conftest.py
git commit -m "feat: adicionar cliente http seguro"
~~~

### Task 5: Public metadata extraction and deterministic categorization

**Files:**
- Create: automation/metadata.py
- Create: automation/categorizer.py
- Create: tests/test_metadata.py
- Create: tests/test_categorizer.py
- Create: tests/fixtures/product-jsonld.html
- Create: tests/fixtures/product-multiple-jsonld.html
- Create: tests/fixtures/product-opengraph.html
- Modify: automation/config.py

**Interfaces:**
- Consumes: bounded HTML and InvalidProductDataError.
- Produces: ExtractedProductData, extract_product_metadata(), parse_decimal(), clean_text(), unique_https_images(), CategoryDecision, and categorize().

- [ ] **Step 1: Add sanitized fixtures and failing tests**

Fixtures include one Product/Offer with 149.90 current, 199.90 previous, BRL, harmless HTML description, duplicate image, and no coupon; multiple JSON-LD blocks with Product after BreadcrumbList; and Open Graph fallback.

~~~python
def test_extracts_jsonld_without_inventing_coupon(load_fixture):
    data = extract_product_metadata(load_fixture("product-jsonld.html"), "https://example.com/item")
    assert data.name == "Produto de teste"
    assert data.current_price == Decimal("149.90")
    assert data.previous_price == Decimal("199.90")
    assert data.images == ("https://images.example.com/item-1.jpg",)
    assert data.coupon is None


def test_known_source_category_wins():
    value = categorize("Eletrônicos > Áudio", "Camisa com fone", "Moda")
    assert value == CategoryDecision("Eletrônicos", "Áudio", True)


def test_unknown_category_requires_review():
    assert categorize(None, "Objeto singular", "Sem classificação") == CategoryDecision("Outros", None, False)
~~~

Also test multiple JSON-LD, Brazilian decimal, previous <= current, script/style removal, Unicode whitespace, 4,000-character limit, HTTPS images, four-image cap, Open Graph, and keyword rules.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/test_metadata.py tests/test_categorizer.py -q

Expected: imports fail.

- [ ] **Step 3: Implement standard-library parsing**

Use HTMLParser to collect every application/ld+json body and public meta name/property. Parse blocks independently, recursively walk lists/dicts/@graph, select Product, and select a valid Offer. Use highPrice or priceSpecification only when greater. A second HTMLParser strips markup and executable content. Deduplicate normalized HTTPS images in first-seen order.

Ignore review and aggregateReview objects when building descriptions. Reject images identified as logos, icons, sprites, tracking pixels, or smaller than 120 by 120 when width and height are supplied; never download or replicate an image merely to discover dimensions.

Keep all category source mappings and keyword tuples in config.py. Normalize Unicode centrally. Precedence is exact source mapping, known first path segment, keyword, then Outros with confident=False.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/test_metadata.py tests/test_categorizer.py -q
git add automation/config.py automation/metadata.py automation/categorizer.py tests/test_metadata.py tests/test_categorizer.py tests/fixtures/product-*.html
git commit -m "feat: extrair e categorizar metadados publicos"
~~~

### Task 6: Common connector contract and registry

**Files:**
- Create: automation/connectors/__init__.py
- Create: automation/connectors/base.py
- Create: tests/connectors/test_base.py

**Interfaces:**
- Consumes: SafeHttpClient, ProductSnapshot, ExtractedProductData, partner settings, and categorizer.
- Produces: ProductConnector protocol, MetadataConnectorBase, ConnectorRegistry.select(), snapshot_from_metadata(), and build_connector_registry().

- [ ] **Step 1: Write failing contract tests**

~~~python
def test_registry_selects_only_supporting_connector():
    mercado = StubConnector("mercado_livre", ("mercadolivre.com.br",))
    shopee = StubConnector("shopee", ("shopee.com.br",))
    registry = ConnectorRegistry((mercado, shopee))
    assert registry.select("https://www.mercadolivre.com.br/MLB-1") is mercado


def test_registry_rejects_unknown_url():
    with pytest.raises(UnsupportedUrlError):
        ConnectorRegistry(()).select("https://unknown.example/item")
~~~

Also verify each stub exposes partner_key, supports(url), and fetch(affiliate_url) returning ProductSnapshot.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/connectors/test_base.py -q

Expected: connector package import fails.

- [ ] **Step 3: Implement common connector behavior**

Define the ProductConnector Protocol with partner_key, supports, and fetch. MetadataConnectorBase.fetch validates support, fetches public HTML, extracts metadata and identifiers through overridable methods, categorizes centrally, preserves affiliate_url, and records terminal response URL as source_url. ConnectorRegistry preserves configured order and raises UnsupportedUrlError on no match or ambiguity.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/connectors/test_base.py tests/test_metadata.py -q
git add automation/connectors tests/connectors/test_base.py
git commit -m "feat: definir contrato comum de conectores"
~~~

### Task 7: Mercado Livre connector

**Files:**
- Create: automation/connectors/mercado_livre.py
- Create: tests/connectors/test_mercado_livre.py
- Create: tests/fixtures/mercado-livre-item.json
- Create: tests/fixtures/mercado-livre-product.html
- Modify: automation/connectors/__init__.py
- Modify: automation/config.py

**Interfaces:**
- Consumes: common connector, safe client, mercadolivre.com.br, meli.la, and api.mercadolibre.com.
- Produces: MercadoLivreConnector, extract_mercado_item_id(), extract_mercado_catalog_id(), public API mapping, and metadata fallback.

- [ ] **Step 1: Add fixtures and failing tests**

The JSON fixture contains id MLB1234567890, catalog_product_id MLB1234, title, BRL current/original prices, four HTTPS pictures, category ID, and active status. HTML contains canonical/JSON-LD data.

~~~python
def test_maps_separate_item_and_catalog_ids(connector, api_fixture):
    value = connector.snapshot_from_api(
        api_fixture,
        "https://meli.la/abc",
        "https://www.mercadolivre.com.br/item",
    )
    assert value.external_id == "MLB1234567890"
    assert value.catalog_id == "MLB1234"
    assert value.current_price == Decimal("149.90")


def test_preserves_affiliate_link_on_metadata_fallback(connector):
    value = connector.fetch("https://www.mercadolivre.com.br/MLB-1234567890-item")
    assert value.affiliate_url.endswith("MLB-1234567890-item")
~~~

Also test supported direct/catalog/short URLs, bounded ID patterns, missing price, unavailable status, safe fallback, and absent coupon.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/connectors/test_mercado_livre.py -q

Expected: module import fails.

- [ ] **Step 3: Implement documented public API first**

Resolve safely; extract only MLB IDs of at least six digits from trusted path/canonical/structured data. When an item ID exists, request https://api.mercadolibre.com/items/{item_id}. If the spike shows auth/blocking, use already fetched public metadata without credentials or undocumented endpoints. Map original_price only when greater, active status to availability, catalog_product_id separately, secure picture URLs uniquely, and category centrally.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/connectors/test_mercado_livre.py tests/connectors/test_base.py -q
git add automation/config.py automation/connectors tests/connectors/test_mercado_livre.py tests/fixtures/mercado-livre-*
git commit -m "feat: adicionar conector mercado livre"
~~~

### Task 8: Shopee connector and manual conversion batches

**Files:**
- Create: automation/connectors/shopee.py
- Create: tests/connectors/test_shopee.py
- Create: tests/fixtures/shopee-product.html
- Modify: automation/connectors/__init__.py

**Interfaces:**
- Consumes: common metadata connector, safe redirects, shopee.com.br, and s.shopee.com.br.
- Produces: ShopeeConnector, extract_shopee_item_id(), and build_conversion_batches(records, batch_size=5).

- [ ] **Step 1: Add fixture and failing tests**

~~~python
def test_short_link_preserves_original_affiliate_url(shopee_connector):
    value = shopee_connector.fetch("https://s.shopee.com.br/AbCd")
    assert value.source_url.startswith("https://shopee.com.br/")
    assert value.affiliate_url == "https://s.shopee.com.br/AbCd"


def test_batches_no_more_than_five(import_rows):
    assert [len(batch) for batch in build_conversion_batches(import_rows[:11])] == [5, 5, 1]
~~~

Also test common-link waiting state, disallowed redirect, item ID extraction, missing price, blocking, and no invented coupon.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/connectors/test_shopee.py -q

Expected: module import fails.

- [ ] **Step 3: Implement metadata-only collection and conversion grouping**

Do not call private/mobile/GraphQL/affiliate endpoints. Resolve short links with SafeHttpClient, parse public metadata, derive item ID only from trusted canonical/path/JSON-LD, and surface persistent blocking. Batch active rows that have Link do Produto, lack Link de Afiliado, and are NOVO or AGUARDANDO CONVERSÃO; keep sheet order.

For each batch, plan Mensagem as Lote Shopee NN — máximo 5 links and keep Status as AGUARDANDO CONVERSÃO. The setup task adds a filter view named Shopee — aguardando conversão over the existing 32 columns, filtered by that status; no extra Importações or Produtos column is introduced.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/connectors/test_shopee.py tests/test_http_client.py -q
git add automation/connectors tests/connectors/test_shopee.py tests/fixtures/shopee-product.html
git commit -m "feat: adicionar conector shopee"
~~~

### Task 9: Fixture-only SHEIN and TikTok Shop connectors

**Files:**
- Create: automation/connectors/shein.py
- Create: automation/connectors/tiktok_shop.py
- Create: tests/connectors/test_shein.py
- Create: tests/connectors/test_tiktok_shop.py
- Create: tests/fixtures/shein-product.html
- Create: tests/fixtures/tiktok-shop-product.html
- Modify: automation/connectors/__init__.py

**Interfaces:**
- Consumes: MetadataConnectorBase and injected partner settings.
- Produces: SheinConnector, TikTokShopConnector, contract fixtures, and live_verified=False capabilities.

- [ ] **Step 1: Write failing fixture contract tests**

~~~python
def test_shein_fixture_contract(shein_connector):
    value = shein_connector.fetch("https://br.shein.com/product-p-123.html")
    assert value.partner == "shein"
    assert value.external_id == "123"
    assert value.current_price == Decimal("79.90")


def test_tiktok_production_has_no_hosts(settings, http_client):
    connector = TikTokShopConnector(http_client, settings.partners["tiktok_shop"])
    assert connector.allowed_hosts == ()
    assert connector.supports("https://www.tiktok.com/shop/item/1") is False


def test_tiktok_fixture_uses_test_only_host(http_client, fixture_partner):
    connector = TikTokShopConnector(http_client, fixture_partner)
    value = connector.fetch("https://shop.tiktok.test/product/123")
    assert value.partner == "tiktok_shop"
~~~

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/connectors/test_shein.py tests/connectors/test_tiktok_shop.py -q

Expected: imports fail.

- [ ] **Step 3: Implement thin metadata connectors**

SHEIN uses only existing explicit project hosts and exposes live_verified=False. TikTok defaults to no hosts; its test injects PartnerConfig with shop.tiktok.test. Both surface incomplete data through typed errors and never claim live verification.

TikTokShopConnector accepts an optional TikTokShopApi protocol dependency whose fetch_product(external_id) method returns public normalized API fields. Production construction passes None in version one. A future environment-backed API client can be injected without changing ProductConnector or Sheets; no speculative endpoint, token variable, or credential is introduced now.

- [ ] **Step 4: Verify and commit each connector**

~~~bash
python3 -m pytest tests/connectors/test_shein.py -q
git add automation/connectors/shein.py automation/connectors/__init__.py tests/connectors/test_shein.py tests/fixtures/shein-product.html
git commit -m "feat: adicionar conector shein por fixtures"
python3 -m pytest tests/connectors/test_tiktok_shop.py -q
git add automation/connectors/tiktok_shop.py automation/connectors/__init__.py tests/connectors/test_tiktok_shop.py tests/fixtures/tiktok-shop-product.html
git commit -m "feat: preparar conector tiktok shop"
~~~

### Task 10: Idempotent Google Sheets schema and batch gateway

**Files:**
- Create: automation/sheets.py
- Create: tests/test_sheets.py
- Modify: tests/conftest.py

**Interfaces:**
- Consumes: Settings, exact headers, SheetUpdate, SheetSchemaError, and service-account JSON.
- Produces: SheetsGateway, GoogleSheetsGateway.from_settings(), validate_headers(), plan_import_sheet_setup(), setup_import_sheet(), read_table(), and batch_write().

- [ ] **Step 1: Extend fake gateway and write failing tests**

The fake records spreadsheet_writes and value_writes separately.

~~~python
def test_setup_creates_missing_sheet_once(fake_sheets):
    result = setup_import_sheet(fake_sheets, "Importações", dry_run=False)
    assert result.created is True
    assert len(fake_sheets.spreadsheet_writes) == 1
    assert any("addSheet" in request for request in fake_sheets.spreadsheet_writes[0])


def test_setup_preserves_existing_rows(fake_sheets_with_imports):
    before = fake_sheets_with_imports.values("Importações!A:AF")
    setup_import_sheet(fake_sheets_with_imports, "Importações", dry_run=False)
    assert fake_sheets_with_imports.values("Importações!A:AF") == before


def test_dry_run_never_writes(fake_sheets):
    setup_import_sheet(fake_sheets, "Importações", dry_run=True)
    assert fake_sheets.spreadsheet_writes == []
    assert fake_sheets.value_writes == []
~~~

Also test exact/mismatched headers, frozen row, filter, Sim/Não, Automático/Bloqueado, status validation, conditional rules, typed numbers/dates, and one batch API call for many ranges.

Add tests that a blank ID Automação is assigned once, an existing ID is preserved, new-row defaults are written in one range update, and the Shopee waiting-conversion filter view is idempotent.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/test_sheets.py -q

Expected: import failure for automation.sheets.

- [ ] **Step 3: Implement in-memory authentication and idempotent setup**

Use service_account.Credentials.from_service_account_info with only spreadsheets scope and build("sheets", "v4", cache_discovery=False). Never stringify credential data. Use spreadsheets.get, values.get, spreadsheets.batchUpdate, and values.batchUpdate. Retry 429/temporary 5xx with bounded backoff.

For a missing sheet, one spreadsheet batch includes addSheet, all 32 header values through updateCells, frozen header, filter, validation, and simple conditional formatting. Existing sheets validate first row and receive idempotent formatting only; never clear/delete/recreate. Dry-run returns the same plan and sends no write.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/test_sheets.py -q
git add automation/sheets.py tests/test_sheets.py tests/conftest.py
git commit -m "feat: integrar google sheets em lote"
~~~

### Task 11: Product mapping, signatures, and safe adoption

**Files:**
- Create: automation/sync.py
- Create: tests/test_sync.py

**Interfaces:**
- Consumes: row models, snapshots, 20 headers, URL normalization, and SheetUpdate.
- Produces: calculate_discount(), data_signature(), link_signature(), map_snapshot_to_product_values(), find_product_match(), and plan_publication().

- [ ] **Step 1: Write failing pure mapping/matching tests**

~~~python
def test_maps_valid_promotion(snapshot, import_record):
    values = map_snapshot_to_product_values(snapshot, import_record, existing=None)
    assert values[7] == 199.90
    assert values[8] == 149.90
    assert calculate_discount(Decimal("149.90"), Decimal("199.90")) == 25


def test_changed_link_matches_last_published(product_rows, import_record):
    import_record.last_published_link = "https://meli.la/old"
    assert find_product_match(import_record, product_rows).row_number == product_rows[0].row_number


def test_ambiguous_match_refuses_overwrite(product_rows, import_record):
    duplicate = (product_rows[0], replace(product_rows[0], row_number=99))
    with pytest.raises(AmbiguousProductMatchError):
        find_product_match(import_record, duplicate)
~~~

Also test nonpromotion mapping, lookup precedence, platform+external ID, stable SHA-256, existing video preservation, original link, four images, default/custom button, typed transport values, and no deletion.

- [ ] **Step 2: Observe red state**

Run: python3 -m pytest tests/test_sync.py -q

Expected: import failure for automation.sync.

- [ ] **Step 3: Implement pure mapping and matching**

Canonical data signatures sort dictionary keys, format Decimal as fixed strings, use UTC ISO timestamps, preserve image order, and return SHA-256. Link signatures hash normalized URLs.

Create exactly 20 output values. Convert Decimal to float only for Sheets JSON. Write previous/current into Preço */Preço Promocional only when previous is greater; otherwise current/blank. Ativo * is Sim only when Ativo and Publicar are Sim. Preserve existing video. Match independently by Último Link Publicado, current affiliate URL, then partner+external ID; raise on multiple rows at any tier before falling through.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/test_sync.py -q -k "mapping or match or signature or discount"
git add automation/sync.py tests/test_sync.py
git commit -m "feat: mapear e adotar produtos sem duplicacao"
~~~

### Task 12: Synchronization state machine and preservation

**Files:**
- Modify: automation/sync.py
- Modify: tests/test_sync.py

**Interfaces:**
- Consumes: connector registry, Sheets gateway, pure sync helpers, typed errors, and current tables.
- Produces: SyncEngine.run(mode, dry_run), pending/full selectors, blocked protection, interruption recovery, and batched updates.

- [ ] **Step 1: Write failing state tests**

~~~python
def test_new_row_moves_to_review(sync_engine, new_import_row):
    report = sync_engine.run("pending", dry_run=False)
    assert report.final_status(new_import_row.row_number) is ImportStatus.REVISAR


def test_blocked_mode_preserves_data(blocked_engine):
    before = blocked_engine.snapshot_tables()
    blocked_engine.run("full", dry_run=False)
    after = blocked_engine.snapshot_tables()
    assert after.product_rows == before.product_rows
    assert after.import_rows[0].name == before.import_rows[0].name


def test_three_temporary_failures_produce_attention(temporary_engine, published_row):
    published_row.consecutive_attempts = 2
    report = temporary_engine.run("full", dry_run=False)
    assert report.final_status(published_row.row_number) is ImportStatus.ATENCAO
~~~

Also test full state transitions, Shopee conversion, disabled rows, stale PROCESSANDO after 30 minutes, unsupported URL, blocked store, invalid data, one/two failures preserving snapshot, signature no-op, full versus pending selection, per-domain concurrency one, dry-run zero writes, and ambiguous publication.

The state assertions are explicit: success without approval ends REVISAR; approved success passes through PRONTO PARA PUBLICAR and ends PUBLICADO; common Shopee link ends AGUARDANDO CONVERSÃO; unsupported URL and invalid data end ERRO; persistent store blocking ends ATENÇÃO; one or two temporary failures retain the prior status/data with an incremented counter; the third ends ATENÇÃO. A confirmed unavailable result ends REVISAR or ATENÇÃO and never changes Ativo * automatically in version one. Missing/expired image output preserves prior images and ends ATENÇÃO.

- [ ] **Step 2: Observe failing behavior**

Run: python3 -m pytest tests/test_sync.py -q -k "state or blocked or temporary or dry_run or pending or full"

Expected: assertions fail because orchestration is absent.

- [ ] **Step 3: Implement deterministic batch orchestration**

Select by sheet row number. Plan PROCESSANDO, fetch, merge old valid fields when new data is absent, sign, then plan terminal status. Do not write metadata when signature is unchanged. Publicar=Sim finds/update-or-appends once, records Último Link Publicado, and ends PUBLICADO. Bloqueado emits only status, message, verification timestamp, and counters. Errors map distinctly and never erase valid product data.

Use ThreadPoolExecutor(max_workers=4), one semaphore per domain, and apply results in row order. Call each batch method at most once per table. Dry-run returns identical SyncReport with no write calls.

- [ ] **Step 4: Verify and commit**

~~~bash
python3 -m pytest tests/test_sync.py tests/test_sheets.py tests/connectors -q
git add automation/sync.py tests/test_sync.py
git commit -m "feat: sincronizar fila com tolerancia a falhas"
~~~

### Task 13: CLI validation and write gates

**Files:**
- Create: automation/cli.py
- Create: tests/test_cli.py
- Modify: automation/__init__.py

**Interfaces:**
- Consumes: settings, gateway, registry, setup, and SyncEngine.
- Produces: build_parser(), validate_environment(), main(), required command modes, and sanitized exit behavior.

- [ ] **Step 1: Write failing CLI tests**

~~~python
@pytest.mark.parametrize("argv", [
    ["setup-sheet", "--dry-run"],
    ["sync", "--mode", "pending", "--dry-run"],
    ["sync", "--mode", "full", "--dry-run"],
    ["validate"],
])
def test_required_commands_parse(argv):
    assert build_parser().parse_args(argv).command == argv[0]


def test_setup_dry_run_never_writes(cli_dependencies):
    assert main(["setup-sheet", "--dry-run"], cli_dependencies) == 0
    assert cli_dependencies.gateway.write_count == 0


def test_validate_never_echoes_secret(cli_dependencies, capsys):
    secret = cli_dependencies.settings.raw_service_account_json
    assert main(["validate"], cli_dependencies) == 0
    assert secret not in capsys.readouterr().out
~~~

Also test missing env exit 2, schema/access error exit 1, partner consistency, both sync modes, and fake-backed non-dry writes.

- [ ] **Step 2: Observe CLI red state**

Run: python3 -m pytest tests/test_cli.py -q

Expected: CLI import fails.

- [ ] **Step 3: Implement argparse and sanitized output**

setup-sheet accepts --dry-run; sync requires pending/full and accepts --dry-run; validate accepts neither. Lazy-load credentials after parsing. Print counts/status only, never row bodies, full URLs, or JSON. Return 0 success, 1 operational validation error, and 2 configuration error.

validate checks credential structure, spreadsheet access, worksheet names, exact 20/32 headers when present, configured partner keys/host rules, TikTok empty-host limitation, duplicate automation IDs, invalid enum values, ambiguous current product matches, and missing required published-product fields. It performs no write.

Run env -u GOOGLE_SERVICE_ACCOUNT_JSON python3 -m automation.cli validate and require exit 2 without secret-bearing traceback.

- [ ] **Step 4: Verify and commit the CLI**

~~~bash
python3 -m pytest tests/test_cli.py tests/test_sheets.py tests/test_sync.py -q
git add automation/cli.py automation/__init__.py tests/test_cli.py
git commit -m "feat: adicionar cli segura da automacao"
~~~

### Task 14: GitHub Actions scheduling

**Files:**
- Create: tests/test_workflow.py
- Create: .github/workflows/sync-affiliates.yml

**Interfaces:**
- Consumes: automation.cli and repository secrets/variables.
- Produces: manual pending/full/validate modes and two daily full schedules within hourly coverage.

- [ ] **Step 1: Write failing workflow contract tests**

~~~python
def test_workflow_schedule_and_permissions():
    text = Path(".github/workflows/sync-affiliates.yml").read_text()
    assert "17 3,15 * * *" in text
    assert "17 0-2,4-14,16-23 * * *" in text
    assert "cancel-in-progress: false" in text
    assert "contents: read" in text
    assert "actions/upload-artifact" not in text


def test_secret_not_job_wide():
    text = Path(".github/workflows/sync-affiliates.yml").read_text()
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in text.split("steps:", 1)[0]
~~~

Also assert manual pending/full/validate choices, Python 3.12, pip cache, timeout, and schedule-string-based mode choice.

- [ ] **Step 2: Observe missing-workflow failure**

Run: python3 -m pytest tests/test_workflow.py -q

Expected: FileNotFoundError for .github/workflows/sync-affiliates.yml.

- [ ] **Step 3: Implement workflow and verify**

Use workflow_dispatch plus two cron entries: 17 3,15 * * * for full and 17 0-2,4-14,16-23 * * * for pending. This preserves hourly minute-17 coverage despite delayed starts. Set contents: read, timeout 20, one concurrency group, cancel-in-progress false, and no artifacts. Put credentials only on the CLI step. Cache from both requirements files.

~~~bash
python3 -m pytest tests/test_workflow.py -q
git diff --check -- .github/workflows/sync-affiliates.yml
git add tests/test_workflow.py .github/workflows/sync-affiliates.yml
git commit -m "ci: agendar sincronizacao de afiliados"
~~~

### Task 15: Frontend adapter, ordering, coupons, and stable identity

**Files:**
- Create: tests/js/catalog.test.js
- Create: tests/fixtures/catalog-current.csv
- Modify: script.js:1-448

**Interfaces:**
- Consumes: exact current 20-column CSV.
- Produces via globalThis.OrvaniCore: CURRENT_SHEET_HEADERS, parseOfferDate(), validCoupon(), normalizeButtonText(), parseOptionalOrder(), sortProductsByOrder(), and stable IDs.

- [ ] **Step 1: Prepare Node 24.20.0 locally if node remains absent**

Do not install globally or use npm. Download the official Linux x64 archive plus SHASUMS256.txt into mktemp -d, verify its exact SHA-256 line, extract there, and set ORVANI_NODE_BIN to its bin/node. Do not add it to Git.

Run: $ORVANI_NODE_BIN --version

Expected: v24.20.0.

- [ ] **Step 2: Add sanitized current CSV and failing native tests**

~~~javascript
const test = require("node:test");
const assert = require("node:assert/strict");
require("../../script.js");
const core = globalThis.OrvaniCore;

test("keeps exact current headers", () => {
  assert.equal(core.CURRENT_SHEET_HEADERS.length, 20);
  assert.equal(core.CURRENT_SHEET_HEADERS[0], "Ativo *");
  assert.equal(core.CURRENT_SHEET_HEADERS[19], "Destaque");
});

test("orders numerically then blanks with stable ties", () => {
  const rows = [{id:"a",order:null},{id:"b",order:2},{id:"c",order:2},{id:"d",order:1}];
  assert.deepEqual(core.sortProductsByOrder(rows).map(({id}) => id), ["d","b","c","a"]);
});

test("hides expired coupons", () => {
  const now = new Date(2026, 7, 29, 12);
  assert.equal(core.validCoupon("", "", now), null);
  assert.equal(core.validCoupon("OFF10", "28/08/2026", now), null);
  assert.equal(core.validCoupon("OFF10", "29/08/2026", now).code, "OFF10");
});
~~~

Also test fixture acceptance, subcategory, empty/invalid date, no-expiry coupon, 48-code-point button limit, literal malicious text, blank/invalid order, promotions, URL protections, TikTok label with empty hosts rejecting broad domains, and stable Mercado/Shopee IDs when tracking query changes.

- [ ] **Step 3: Observe red state**

Run: $ORVANI_NODE_BIN --test tests/js/catalog.test.js

Expected: missing exports/behavior fail while existing parsing loads.

- [ ] **Step 4: Extend only pure adapter behavior**

Set refreshIntervalMs 300000. Add tiktok_shop label with hosts: [] and alias. Map Subcategoria, Cupom, Validade da oferta, Texto do Botão, and Ordem. Parse optional nonnegative integer order; decorate with original index for stable sorting and blanks last. Parse YYYY-MM-DD or DD/MM/YYYY through local end-of-day. A nonempty coupon with no expiry displays; supplied invalid/expired date suppresses. Normalize button whitespace and cap 48 Unicode code points.

Stable ID precedence is bounded Mercado MLB ID, bounded Shopee numeric item ID, then normalized partner+name. Never include query/fragment. Export all pure helpers.

- [ ] **Step 5: Verify and commit**

~~~bash
$ORVANI_NODE_BIN --test tests/js/catalog.test.js
git diff --check -- script.js tests/js/catalog.test.js tests/fixtures/catalog-current.csv
git add script.js tests/js/catalog.test.js tests/fixtures/catalog-current.csv
git commit -m "feat: ampliar adaptador do catalogo"
~~~

### Task 16: Safe coupon and custom-button rendering

**Files:**
- Modify: script.js:605-688
- Modify: style.css:829-950
- Modify: tests/js/catalog.test.js

**Interfaces:**
- Consumes: coupon, expiry, button text, and safe element() helper.
- Produces: offerPresentation(), coupon badge/expiry, custom/default button, and unchanged external link security.

- [ ] **Step 1: Write failing presentation/source tests**

~~~javascript
test("uses store default for empty button", () => {
  const view = core.offerPresentation({partner:"shopee",buttonText:"",coupon:null,couponExpiresAt:null});
  assert.equal(view.buttonText, "Ver oferta na Shopee");
});

test("keeps safe text and external attributes", () => {
  const source = require("node:fs").readFileSync("script.js", "utf8");
  assert.match(source, /sponsored nofollow noopener noreferrer/);
  assert.doesNotMatch(source, /\.innerHTML\s*=|insertAdjacentHTML|document\.write/);
});
~~~

Also test custom copy, malicious literal copy, coupon code/valid-through text, expired suppression, and discount proof.

- [ ] **Step 2: Observe red state**

Run: $ORVANI_NODE_BIN --test tests/js/catalog.test.js

Expected: offerPresentation is missing.

- [ ] **Step 3: Render only through textContent**

offerLink uses custom text or current partner default while retaining target, rel, and product/partner aria-label. couponBlock returns no node without validCoupon; otherwise it builds coupon-badge and optional time using element(), which assigns textContent. Place it above the footer in normal cards and beside price in featured slides; leave hero cards unchanged.

Add only .coupon-offer, .coupon-badge, and .coupon-expiry rules using existing variables, wrapping, and no fixed height. Do not change HTML files or unrelated responsive rules.

- [ ] **Step 4: Verify focused diff and commit**

~~~bash
$ORVANI_NODE_BIN --test tests/js/catalog.test.js
git diff --stat 0dd7c88 -- index.html catalogo.html style.css script.js
git diff --word-diff=plain -- script.js style.css
git add script.js style.css tests/js/catalog.test.js
git commit -m "feat: exibir cupom e botao personalizado"
~~~

Expected: HTML files unchanged and frontend differences limited to requested behavior.

### Task 17: Operational documentation and guarded live tests

**Files:**
- Create: README-AUTOMACAO.md
- Create: tests/live/test_store_smoke.py
- Modify after factual checks: docs/spikes/2026-08-29-store-viability.md

**Interfaces:**
- Consumes: complete CLI, workflow, tests, and spike status.
- Produces: operator instructions and opt-in read-only smoke tests.

- [ ] **Step 1: Add guarded live tests**

At module level:

~~~python
RUN_LIVE_TESTS = os.getenv("RUN_LIVE_TESTS") == "1"
pytestmark = pytest.mark.skipif(not RUN_LIVE_TESTS, reason="RUN_LIVE_TESTS=1 não definido")
~~~

Tests read current Mercado/Shopee samples from public CSV, use SafeHttpClient, assert only contract invariants, sanitize failure text, never log URLs/bodies, never send login/cookies/credentials, and never write.

Run python3 -m pytest tests/live -q and expect all skipped by default.

- [ ] **Step 2: Write README-AUTOMACAO.md in Portuguese**

Include numbered instructions for: free Google Cloud project; only Sheets API; exclusive service account; editor share only to its email; GitHub secret; spreadsheet variables; validate; both setup-sheet commands; pending dry-run; manual workflow; adding links; official Shopee groups of five; Publicar=Sim; pausing through Ativo/Bloqueado/workflow; revocation and secret removal.

Document 03:17/15:17 UTC full runs, scheduler delay, manual refresh, small-catalog quotas, RUN_LIVE_TESTS, semi-automation under blocking, Hotmart mismatch, SHEIN/TikTok limitations, no credentials in chat/repository, and no deployment.

Link the official version sources recorded at the top of this plan and justify the four direct Python pins. State that Node is used only to execute node:test and is not a frontend dependency or package manager.

- [ ] **Step 3: Check and commit documentation**

~~~bash
python3 -m pytest tests/live -q
rg -n "BEGIN PRIVATE KEY|private_key_id|client_email.*gserviceaccount" . --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/*'
git diff --check
git add README-AUTOMACAO.md tests/live/test_store_smoke.py docs/spikes/2026-08-29-store-viability.md
git commit -m "docs: explicar operacao segura da automacao"
~~~

Skip staging the spike file if no factual value changed.

### Task 18: Complete verification and evidence handoff

**Files:**
- Inspect: every tracked and untracked file
- Modify only after a verified defect: the file owned by the failing task and its focused test
- Modify after factual live checks: docs/spikes/2026-08-29-store-viability.md

**Interfaces:**
- Consumes: every implementation task.
- Produces: passing offline gates, explicit live outcomes, current catalog counts, and the required 12-part final report.

- [ ] **Step 1: Run all offline gates**

~~~bash
python3 -m pytest -q
python3 -m compileall -q automation tests
$ORVANI_NODE_BIN --test tests/js/catalog.test.js
$ORVANI_NODE_BIN --check script.js
git diff --check
~~~

Expected: Python/JavaScript suites and syntax pass; live tests are reported separately as skipped.

- [ ] **Step 2: Serve locally without deployment**

Start python3 -m http.server 8765 --bind 127.0.0.1 in a terminal session. Request index.html, catalogo.html, style.css, and script.js from loopback; require HTTP 200 and expected media types; stop the server. If a Chromium-compatible binary already exists, run it headlessly only against loopback with console logging; do not install a browser or visit stores through it.

Confirm search, combined filters, categories, featured carousel source, responsive CSS media queries, institutional dialogs, Google Drive image conversion, error states, target/rel attributes, cupom, validity, order, custom/default button, and TikTok Shop label. Record browser-console status only when a browser command actually ran.

- [ ] **Step 3: Re-read the real CSV through production parser**

Download CSV to mktemp, load script.js in Node, run OrvaniCore.parseCsv and normalizeRows, and print counts plus sanitized rejection fields only.

Expected: 11 accepted; one preserved Hotmart rejection; no write.

- [ ] **Step 4: Run optional live smoke and record exact outcomes**

Run: RUN_LIVE_TESTS=1 python3 -m pytest tests/live/test_store_smoke.py -q -rs

A store either yields a normalized snapshot or its typed blocked/semi-automatic outcome. Never reinterpret blocking as success. Update only factual result rows in the spike report.

- [ ] **Step 5: Secret/prohibited-dependency audit**

~~~bash
rg -n "BEGIN PRIVATE KEY|private_key_id|ghp_|github_pat_|sk-[A-Za-z0-9]|document\.cookie|localStorage|sessionStorage|playwright|selenium" . --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/*'
rg -n "React|Next\.js|typescript|package-lock|node_modules" . --hidden --glob '!.git/**' --glob '!docs/superpowers/plans/*'
git status --short --branch
git log --oneline --decorate 0dd7c88..HEAD
git diff --name-status 0dd7c88..HEAD
~~~

Review every match. Documented prohibitions and variable names are acceptable; credential material and forbidden implementation dependencies are not.

- [ ] **Step 6: Commit factual spike changes and rerun final gates**

~~~bash
git add docs/spikes/2026-08-29-store-viability.md
git commit -m "docs: atualizar resultado real dos conectores"
python3 -m pytest -q
python3 -m compileall -q automation tests
$ORVANI_NODE_BIN --test tests/js/catalog.test.js
$ORVANI_NODE_BIN --check script.js
git diff --check 0dd7c88..HEAD
~~~

Skip this commit if no factual spike value changed.

- [ ] **Step 7: Prepare the exact final handoff**

Report in order: implemented summary; checkpoint 0dd7c88d57df2053b67f12720d8df13f573373de; exact file list; per-store spike; every executed command/result; accepted/rejected counts before/after; limits for all four stores; Google Cloud/GitHub steps; safe setup-sheet commands; first pending dry-run; explicit no-credential confirmation; explicit no-deploy confirmation.

Do not claim a connector, browser check, live check, or real Sheets operation passed unless its command was actually executed and observed.
