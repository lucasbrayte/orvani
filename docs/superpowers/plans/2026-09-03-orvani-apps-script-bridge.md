# Orvani Apps Script Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a versioned Google Apps Script Web App bridge that securely upserts Calc-authored products into `Importações`, returns backend status, and dispatches one existing `pending` workflow per changed batch.

**Architecture:** Keep Apps Script-specific I/O thin and place deterministic protocol, validation, upsert planning, and status projection in testable functions. `doPost(e)` parses one signed JSON envelope, verifies HMAC/timestamp/nonce, executes one allowlisted action, writes only approved `Importações` input fields, and calls the already-installed `dispatchPendingWorkflow_()` function only when editable data actually changes.

**Tech Stack:** Google Apps Script V8 JavaScript, Node.js built-in `node:test` for repository tests, Google Sheets/Cache/Properties/Utilities services at runtime.

**Spec:** `docs/superpowers/specs/2026-09-03-libreoffice-orvani-sync-design.md`

## Global Constraints

- Endpoint is `doPost(e)` with actions `upsert_products`, `get_status`, and `health`.
- Transport is HTTPS plus HMAC-SHA256.
- Signed envelope fields are `version`, `action`, `timestamp`, `nonce`, `payload`, and `signature`.
- Timestamp acceptance window is ±120 seconds.
- Nonces are single-use inside the replay window.
- `ORVANI_SYNC_SECRET` and `GITHUB_TOKEN` stay in Apps Script Script Properties.
- Calc cannot write backend status/message/attempt/signature/timestamp fields.
- `ID Externo` remains backend-controlled.
- One accepted changed batch causes at most one `pending` dispatch.
- Existing `dispatchPendingWorkflow_()` is consumed, not replaced.

---

### Task 1: Add deterministic request canonicalization and HMAC verification

**Files:**
- Create: `apps_script/orvani_sync_webapp.gs`
- Create: `tests/js/apps_script_sync.test.js`

**Interfaces:**
- Produces:
  - `orvaniCanonicalJson_(value) -> string`
  - `orvaniUnsignedEnvelope_(envelope) -> object`
  - `orvaniVerifyEnvelopeCore_(envelope, secret, nowSeconds, hmacHexFn, nonceAcceptFn) -> object`
  - runtime wrapper `orvaniHmacHex_(secret, canonicalText) -> string`

- [ ] **Step 1: Write failing canonicalization tests**

Create `tests/js/apps_script_sync.test.js` loading the `.gs` file with `vm.runInContext(...)`. Add:

```javascript
test("canonical JSON sorts object keys recursively", () => {
  const value = { z: 1, a: { y: 2, b: "ç" }, list: [{ d: 4, c: 3 }] };
  assert.equal(
    core.orvaniCanonicalJson_(value),
    '{"a":{"b":"ç","y":2},"list":[{"c":3,"d":4}],"z":1}'
  );
});

test("verification rejects stale timestamps", () => {
  const envelope = signedEnvelope({ timestamp: 1000 });
  assert.throws(
    () => core.orvaniVerifyEnvelopeCore_(
      envelope, "secret", 1121, fakeHmacHex, () => true
    ),
    /timestamp/i
  );
});

test("verification rejects a reused nonce", () => {
  const envelope = signedEnvelope({ nonce: "nonce-1" });
  assert.throws(
    () => core.orvaniVerifyEnvelopeCore_(
      envelope, "secret", envelope.timestamp, fakeHmacHex, () => false
    ),
    /nonce/i
  );
});
```

The test harness should expose `.gs` functions by appending:

```javascript
globalThis.OrvaniAppsScriptCore = {
  orvaniCanonicalJson_,
  orvaniVerifyEnvelopeCore_,
};
```

to the VM source before evaluation.

- [ ] **Step 2: Run tests and verify RED**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: FAIL because the `.gs` functions do not exist.

- [ ] **Step 3: Implement canonical JSON**

Use:

```javascript
function orvaniCanonicalJson_(value) {
  if (value === null) return "null";
  if (Array.isArray(value)) {
    return "[" + value.map(orvaniCanonicalJson_).join(",") + "]";
  }
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map(
      (key) => JSON.stringify(key) + ":" + orvaniCanonicalJson_(value[key])
    ).join(",") + "}";
  }
  if (typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return JSON.stringify(value);
  }
  throw new Error("Valor não canônico.");
}
```

- [ ] **Step 4: Implement signature verification core**

Use an unsigned envelope that excludes `signature`:

```javascript
function orvaniUnsignedEnvelope_(envelope) {
  return {
    version: envelope.version,
    action: envelope.action,
    timestamp: envelope.timestamp,
    nonce: envelope.nonce,
    payload: envelope.payload,
  };
}

function orvaniVerifyEnvelopeCore_(
  envelope,
  secret,
  nowSeconds,
  hmacHexFn,
  nonceAcceptFn
) {
  if (!envelope || envelope.version !== "v1") {
    throw new Error("Versão de protocolo inválida.");
  }
  if (!Number.isInteger(envelope.timestamp)) {
    throw new Error("Timestamp inválido.");
  }
  if (Math.abs(nowSeconds - envelope.timestamp) > 120) {
    throw new Error("Timestamp fora da janela.");
  }
  if (typeof envelope.nonce !== "string" || !/^[A-Za-z0-9_-]{16,128}$/.test(envelope.nonce)) {
    throw new Error("Nonce inválido.");
  }
  if (typeof envelope.signature !== "string" || !/^[0-9a-f]{64}$/.test(envelope.signature)) {
    throw new Error("Assinatura inválida.");
  }

  const canonical = orvaniCanonicalJson_(orvaniUnsignedEnvelope_(envelope));
  const expected = hmacHexFn(secret, canonical);
  if (!orvaniConstantTimeEqual_(expected, envelope.signature)) {
    throw new Error("Assinatura inválida.");
  }
  if (!nonceAcceptFn(envelope.nonce)) {
    throw new Error("Nonce já utilizado.");
  }
  return envelope;
}
```

Implement `orvaniConstantTimeEqual_` by comparing same-length strings character-by-character without early return.

- [ ] **Step 5: Add the Apps Script HMAC adapter**

```javascript
function orvaniHmacHex_(secret, text) {
  const bytes = Utilities.computeHmacSha256Signature(
    text,
    secret,
    Utilities.Charset.UTF_8
  );
  return bytes.map((value) => {
    const byte = value < 0 ? value + 256 : value;
    return byte.toString(16).padStart(2, "0");
  }).join("");
}
```

- [ ] **Step 6: Run tests**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps_script/orvani_sync_webapp.gs tests/js/apps_script_sync.test.js
git commit -m "feat: add signed Apps Script protocol"
```

---

### Task 2: Enforce action schema and client field ownership

**Files:**
- Modify: `apps_script/orvani_sync_webapp.gs`
- Modify: `tests/js/apps_script_sync.test.js`

**Interfaces:**
- Produces:
  - `ORVANI_CLIENT_FIELDS_`
  - `orvaniValidateUpsertProduct_(value) -> object`
  - `orvaniValidateActionPayload_(action, payload) -> object`

- [ ] **Step 1: Add failing allowlist tests**

```javascript
test("upsert rejects backend-owned fields", () => {
  const product = validProduct();
  product.Status = "PUBLICADO";
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(product),
    /campo/i
  );
});

test("upsert accepts only the documented editable fields", () => {
  const result = core.orvaniValidateUpsertProduct_(validProduct());
  assert.equal(result["ID Automação"], "local-uuid");
  assert.equal(result["Modo de Atualização"], "Manual");
});
```

`validProduct()` should contain exact transport keys matching the `Importações` headers, excluding backend-owned fields.

- [ ] **Step 2: Run RED**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: FAIL because validation functions do not exist.

- [ ] **Step 3: Implement the write allowlist**

Define:

```javascript
const ORVANI_CLIENT_FIELDS_ = Object.freeze([
  "ID Automação",
  "Ativo",
  "Publicar",
  "Destaque",
  "Ordem",
  "Modo de Atualização",
  "Link do Produto",
  "Link de Afiliado",
  "Plataforma",
  "Nome",
  "Descrição",
  "Categoria",
  "Subcategoria",
  "Tipo",
  "Preço Atual",
  "Preço Anterior",
  "Cupom",
  "Validade do Cupom",
  "Imagem 1",
  "Imagem 2",
  "Imagem 3",
  "Imagem 4",
  "Texto do Botão",
]);
```

Reject any input key outside this set. Require a non-empty `ID Automação`, `Ativo`/`Publicar`/`Destaque` in `Sim|Não`, `Modo de Atualização` in `Automático|Manual|Bloqueado`, bounded text, finite positive current price when provided, and no more than four image values.

- [ ] **Step 4: Implement action payload validation**

`upsert_products` accepts:

```javascript
{ products: [/* 1..50 validated records */] }
```

`get_status` accepts:

```javascript
{ ids: ["uuid-1", "uuid-2"] }
```

with 1..100 unique IDs.

`health` accepts exactly:

```javascript
{}
```

Reject unknown actions and extra top-level payload keys.

- [ ] **Step 5: Run tests**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps_script/orvani_sync_webapp.gs tests/js/apps_script_sync.test.js
git commit -m "feat: validate Apps Script sync payloads"
```

---

### Task 3: Plan idempotent `Importações` upserts by `ID Automação`

**Files:**
- Modify: `apps_script/orvani_sync_webapp.gs`
- Modify: `tests/js/apps_script_sync.test.js`

**Interfaces:**
- Produces:
  - `orvaniPlanUpserts_(sheetRows, products) -> { mutations, changedIds }`
  - each mutation: `{ rowNumber, create, valuesByHeader }`

- [ ] **Step 1: Add failing create/update/duplicate tests**

```javascript
test("new ID plans one create", () => {
  const plan = core.orvaniPlanUpserts_([], [validProduct()]);
  assert.equal(plan.mutations.length, 1);
  assert.equal(plan.mutations[0].create, true);
  assert.deepEqual(plan.changedIds, ["local-uuid"]);
});

test("same ID and same editable data is idempotent", () => {
  const rows = [sheetRowFromProduct(validProduct(), 2)];
  const plan = core.orvaniPlanUpserts_(rows, [validProduct()]);
  assert.equal(plan.mutations.length, 0);
  assert.deepEqual(plan.changedIds, []);
});

test("duplicate ID in sheet is rejected", () => {
  const rows = [
    sheetRowFromProduct(validProduct(), 2),
    sheetRowFromProduct(validProduct(), 3),
  ];
  assert.throws(
    () => core.orvaniPlanUpserts_(rows, [validProduct()]),
    /duplicad/i
  );
});
```

- [ ] **Step 2: Run RED**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: FAIL because `orvaniPlanUpserts_` does not exist.

- [ ] **Step 3: Implement deterministic row comparison**

Build a header-index map from the existing 32 `Importações` headers. Compare only `ORVANI_CLIENT_FIELDS_`. Normalize `null`/`undefined` to `""`, numeric price values to numbers, and strings without rewriting backend-controlled columns.

For a changed/new mutation, include backend state reset values:

```javascript
{
  "Status": "NOVO",
  "Mensagem": "",
  "Tentativas Consecutivas": 0,
  "Assinatura dos Dados": "",
  "Última Verificação": "",
  "Última Atualização": "",
}
```

Do not accept these fields from the client; they are generated by the server-side mutation planner.

- [ ] **Step 4: Run tests**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps_script/orvani_sync_webapp.gs tests/js/apps_script_sync.test.js
git commit -m "feat: plan idempotent import upserts"
```

---

### Task 4: Add Sheets adapters and status projection

**Files:**
- Modify: `apps_script/orvani_sync_webapp.gs`
- Modify: `tests/js/apps_script_sync.test.js`

**Interfaces:**
- Produces:
  - `orvaniApplyUpsertPlan_(sheet, headers, plan) -> void`
  - `orvaniProjectStatusRows_(sheetRows, requestedIds) -> object[]`
  - `orvaniGetImportSheet_() -> GoogleAppsScript.Spreadsheet.Sheet`

- [ ] **Step 1: Add failing status projection tests**

```javascript
test("status projection returns only backend status fields", () => {
  const rows = [statusSheetRow()];
  const result = core.orvaniProjectStatusRows_(rows, ["local-uuid"]);
  assert.deepEqual(Object.keys(result[0]).sort(), [
    "Assinatura dos Dados",
    "Desconto Calculado",
    "ID Automação",
    "ID Externo",
    "Mensagem",
    "Status",
    "Última Atualização",
    "Última Verificação",
    "Último Link Publicado",
  ].sort());
});
```

- [ ] **Step 2: Run RED**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: FAIL because projection is missing.

- [ ] **Step 3: Implement projection and sheet access**

Use the spreadsheet ID already fixed by Orvani:

```javascript
const ORVANI_SPREADSHEET_ID_ = "1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0";
const ORVANI_IMPORT_SHEET_ = "Importações";
```

`orvaniGetImportSheet_()` opens by ID and requires the exact sheet name.

Projection must never return unrelated product rows, GitHub data, or Script Properties.

- [ ] **Step 4: Implement writes as bounded range updates**

For existing rows, write only changed cells/ranges. For new rows, append one complete 32-column row with server-owned defaults filled by the mutation planner. Hold a script lock around read-plan-write:

```javascript
const lock = LockService.getScriptLock();
lock.waitLock(10000);
try {
  // read current rows, plan, apply
} finally {
  lock.releaseLock();
}
```

This prevents two Web App requests from racing to create the same ID.

- [ ] **Step 5: Run tests**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps_script/orvani_sync_webapp.gs tests/js/apps_script_sync.test.js
git commit -m "feat: add Apps Script sheet adapters"
```

---

### Task 5: Implement `doPost(e)` and one-dispatch-per-batch behavior

**Files:**
- Modify: `apps_script/orvani_sync_webapp.gs`
- Modify: `tests/js/apps_script_sync.test.js`

**Interfaces:**
- Consumes: existing Apps Script function `dispatchPendingWorkflow_()`.
- Produces:
  - `doPost(e)`
  - `orvaniHandleAction_(action, payload)`
  - JSON response `{ ok, action, ... }`.

- [ ] **Step 1: Add failing dispatch test**

With fake action dependencies:

```javascript
test("changed upsert batch requests exactly one pending dispatch", () => {
  let dispatches = 0;
  const result = core.orvaniHandleUpsertCore_(
    [validProduct(), validProduct({ "ID Automação": "uuid-2" })],
    fakeSheetState(),
    () => { dispatches += 1; }
  );
  assert.equal(result.changed, 2);
  assert.equal(dispatches, 1);
});
```

Add a second test where the exact same rows already exist and assert `dispatches === 0`.

- [ ] **Step 2: Run RED**

```bash
node --test tests/js/apps_script_sync.test.js
```

Expected: FAIL because the handler is missing.

- [ ] **Step 3: Implement runtime authentication**

`doPost(e)` must:

1. Require JSON body and a bounded `contentLength`.
2. Parse the envelope.
3. Read `ORVANI_SYNC_SECRET` from `PropertiesService.getScriptProperties()`.
4. Verify signature with `orvaniVerifyEnvelopeCore_`.
5. Use `CacheService.getScriptCache()` for nonce acceptance:

```javascript
function orvaniAcceptNonce_(nonce) {
  const cache = CacheService.getScriptCache();
  const key = "nonce:" + nonce;
  if (cache.get(key) !== null) return false;
  cache.put(key, "1", 180);
  return true;
}
```

6. Validate the action payload.
7. Execute the action.
8. Return `ContentService.createTextOutput(JSON.stringify(response)).setMimeType(ContentService.MimeType.JSON)`.

Never include the secret, signature, full raw request, or GitHub token in errors.

- [ ] **Step 4: Implement action dispatch**

For changed `upsert_products`, call the existing:

```javascript
dispatchPendingWorkflow_();
```

exactly once after the sheet write succeeds.

For `get_status`, return status projection.

For `health`, return:

```javascript
{ ok: true, action: "health", service: "orvani-sync", version: "v1" }
```

- [ ] **Step 5: Run all JS tests**

```bash
node --test tests/js/catalog.test.js tests/js/apps_script_sync.test.js
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps_script/orvani_sync_webapp.gs tests/js/apps_script_sync.test.js
git commit -m "feat: expose authenticated Apps Script web app"
```

---

### Task 6: Add deployment and Script Properties documentation

**Files:**
- Create: `apps_script/README.md`
- Modify: `README-AUTOMACAO.md`

**Interfaces:**
- Documents the manual installation into the existing Apps Script project where `dispatchPendingWorkflow_()` and `GITHUB_TOKEN` already exist.

- [ ] **Step 1: Write exact deployment instructions**

Document:

```text
1. Open the existing Apps Script project bound to the Orvani spreadsheet.
2. Add a new script file and paste apps_script/orvani_sync_webapp.gs.
3. Script Properties:
   ORVANI_SYNC_SECRET=<64 hex chars>
   GITHUB_TOKEN=<existing value; do not change>
4. Deploy > New deployment > Web app.
5. Execute as: Me.
6. Who has access: Anyone.
7. Copy the /exec URL into the local ORVANI_WEBAPP_URL.
8. Do not use the /dev URL in the systemd service.
```

Also document that HMAC is the authorization layer for the public Web App URL.

- [ ] **Step 2: Add a verification checklist**

Include:

```text
- Existing onImportacoesEdit trigger remains installed.
- Existing testGitHubDispatch remains a manual diagnostic only.
- ORVANI_SYNC_SECRET is not committed.
- Web App health request succeeds only with a valid signature.
- Reusing the same signed envelope fails because the nonce is consumed.
```

- [ ] **Step 3: Run formatting/tests**

```bash
node --test tests/js/catalog.test.js tests/js/apps_script_sync.test.js
git diff --check
```

Expected: PASS and no whitespace errors.

- [ ] **Step 4: Commit**

```bash
git add apps_script/README.md README-AUTOMACAO.md
git commit -m "docs: document Apps Script sync bridge"
```

---

## Plan Completion Gate

This plan is complete when the versioned `.gs` file passes Node tests, the deployed Web App authenticates signed requests, changed batches create/update exactly one import row per automation ID, unchanged retries are idempotent, backend fields cannot be client-written, status can be read by IDs, and a changed batch dispatches one existing `pending` workflow.
