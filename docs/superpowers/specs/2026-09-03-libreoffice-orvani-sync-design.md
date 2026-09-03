# Orvani LibreOffice Sync — Design

Date: 2026-09-03
Status: Approved design

## Goal

Make LibreOffice Calc the primary product-management interface for Orvani while preserving the existing Google Sheets → GitHub Actions → Produtos → site publication pipeline.

The operator should normally do only this:

1. Open `Orvani.ods` in LibreOffice Calc.
2. Add or edit products.
3. Press `Ctrl + S`.
4. Continue working while status and backend messages return automatically to the open Calc document.

The local computer is required only while using LibreOffice and synchronizing local changes. Once a change has reached Google Sheets, the remaining pending/publication flow continues in the cloud.

## Architectural Decisions

- LibreOffice Calc is the source of truth for editable catalog fields.
- Google Sheets remains the operational backend used by the existing automation.
- A local Python service on Linux observes the open Calc document and communicates with it through LibreOffice UNO.
- The local service starts automatically with a `systemd --user` service.
- The local service sends changes to a Google Apps Script Web App over HTTPS.
- Apps Script writes only allowed input fields to `Importações` and dispatches the existing GitHub Actions `pending` workflow.
- Status, message, discount, last-check time, and last-update time flow back from Google Sheets through Apps Script to the local Python service and into the open Calc document via UNO.
- The GitHub token remains only in Apps Script Script Properties; it is never stored in LibreOffice or the local sync process.
- Client/server authentication uses HMAC-SHA256 with timestamp and nonce replay protection.
- A new official `Manual` update mode is added to Orvani. In Manual mode, the pending workflow validates and publishes the catalog data supplied by Calc instead of replacing those fields with public-store metadata.

## High-Level Data Flow

```text
LibreOffice Calc (Orvani.ods)
        ↕ UNO
Local Python sync service
        ↓ HTTPS + HMAC
Apps Script Web App
        ↓
Google Sheets / Importações
        ↓
GitHub Actions pending
        ↓
Produtos
        ↓
Orvani site

Google Sheets status fields
        ↑
Apps Script Web App
        ↑
Local Python sync service
        ↑ UNO
LibreOffice Calc
```

## Calc Workbook Design

The main visible sheet is `Catálogo`.

### User-editable columns

| Column | Field |
| --- | --- |
| A | Ativo |
| B | Publicar |
| C | Destaque |
| D | Ordem |
| E | Modo Atualização |
| F | Link Produto |
| G | Link Afiliado |
| H | Plataforma |
| I | Nome |
| J | Descrição |
| K | Categoria |
| L | Subcategoria |
| M | Tipo |
| N | Preço Atual |
| O | Preço Anterior |
| P | Cupom |
| Q | Validade Cupom |
| R | Imagem 1 |
| S | Imagem 2 |
| T | Imagem 3 |
| U | Imagem 4 |
| V | Texto Botão |

### Backend-returned columns

| Column | Field |
| --- | --- |
| W | Status |
| X | Mensagem |
| Y | Desconto |
| Z | Última Verificação |
| AA | Última Atualização |

The local service must never overwrite user-editable cells when applying backend status updates.

### Hidden technical fields

The workbook also stores technical identity/synchronization values in hidden columns or a hidden technical range:

- ID Automação
- ID Externo
- Último Link Publicado
- Assinatura
- Última Sincronização Local
- Hash da Linha
- Hash Confirmado

These fields are not part of the operator workflow.

### Data validation

Calc should provide controlled values where appropriate:

- Ativo: `Sim` / `Não`
- Publicar: `Sim` / `Não`
- Destaque: `Sim` / `Não`
- Modo Atualização: `Automático` / `Manual` / `Bloqueado`
- Tipo: `Físico` / `Digital`
- Plataforma: values supported by the Orvani backend

Price columns use BRL-friendly numeric formatting, but transport uses a canonical decimal representation rather than localized display text.

## Product Identity and Duplicate Prevention

`ID Automação` is the canonical synchronization key between one Calc row and one `Importações` row.

Rules:

- If a local row has no ID, the local service generates a UUID before the first upload attempt and writes it to the hidden technical field.
- Apps Script searches `Importações` by `ID Automação`.
- If the ID does not exist, Apps Script creates one new import row.
- If the ID exists exactly once, Apps Script updates that existing row.
- If the same ID exists more than once in `Importações`, the request is rejected as a data-integrity error; the service must not guess which row to update.
- Repeated saves with unchanged content never create a second product.

A local deterministic hash covers only user-editable product fields. If the current hash equals the last successfully acknowledged hash, the row is not uploaded again.

Generating the UUID before the upload attempt is intentional: if the network request succeeds but the response is lost, retrying with the same UUID is idempotent and updates the same `Importações` row rather than creating a duplicate.

## Save-to-Sync Behavior

`Ctrl + S` is the user action that commits local edits for synchronization.

The local service observes the open Calc document through UNO and reacts to LibreOffice document-save events rather than editing the `.ods` file externally.

For each changed row:

1. Read current user-editable values from Calc.
2. Ensure the row has an `ID Automação`.
3. Validate the local row.
4. If validation fails, update only the local Status/Mensagem fields with a local validation state and do not call Apps Script.
5. Compare the row hash to the last acknowledged hash.
6. If unchanged, do nothing.
7. If changed, send an authenticated `upsert_products` request.
8. Only after Apps Script acknowledges the upsert does the client record the new hash as acknowledged.

This ordering prevents failed uploads from being mistaken for synchronized rows.

## Local Validation

The local client performs fast validation before upload so obvious incomplete rows do not pollute `Importações` or trigger unnecessary pending runs.

Validation includes, as applicable:

- required textual fields
- positive current price
- valid previous-price relationship when supplied
- recognized update mode
- recognized product type
- recognized platform
- URL shape for product, affiliate, and images
- maximum of four images
- fields required by partner-specific manual publication rules

A local validation failure produces a local-only state such as `ERRO LOCAL` with a useful message. `ERRO LOCAL` is never sent as the backend `Status` field.

## New Manual Update Mode

The current Orvani domain is extended from:

- `Automático`
- `Bloqueado`

to:

- `Automático`
- `Manual`
- `Bloqueado`

### Automatic mode

Existing connector behavior remains the default: Orvani may obtain public store metadata and merge it according to current backend rules.

### Manual mode

Calc is authoritative for catalog content.

The pending workflow must use the reviewed values from `Importações` for:

- name
- description
- category
- subcategory
- product type
- current price
- previous price
- coupon
- coupon validity when supported
- images
- product URL
- affiliate URL
- button text
- order
- featured flag

The backend remains authoritative for operational/internal fields including:

- ID Externo when derived/validated by backend rules
- Desconto Calculado
- Status
- Mensagem
- Tentativas Consecutivas
- Último Link Publicado
- Assinatura dos Dados
- Última Verificação
- Última Atualização

Manual mode still performs server-side validation and product matching before publication. It is not a bypass around safety, partner allowlists, price checks, identity checks, or `Produtos` persistence verification.

### Blocked mode

Existing blocked-mode preservation behavior remains unchanged.

## Apps Script Web App Contract

Apps Script exposes one HTTPS Web App entry point, `doPost(e)`, with authenticated actions.

Initial actions:

- `upsert_products`
- `get_status`
- `health`

No separate public endpoint is required for each operation.

### `upsert_products`

Input contains one bounded batch of product records using the Calc transport schema.

Apps Script:

1. Authenticates the request.
2. Validates request size, action, schema, field types, and batch count.
3. Rejects client attempts to write backend-controlled fields.
4. Resolves each record by `ID Automação`.
5. Creates or updates only the allowed `Importações` input fields.
6. Resets backend processing state only for records whose editable payload actually changed.
7. Dispatches the existing GitHub Actions workflow in `pending` mode after the sheet write succeeds.

For a changed/new row, the Web App sets backend state to a reprocessable state (`NOVO`) and clears stale backend outcome fields that must not prevent processing, while preserving backend ownership of those fields.

The Apps Script implementation coalesces one accepted batch into at most one pending dispatch instead of dispatching once per row.

If an accepted request is retried with the same `ID Automação` and identical editable payload, it is idempotent: it does not duplicate the import row and should not cause unnecessary state resets.

### `get_status`

Input is a bounded set of `ID Automação` values.

Output returns only the status fields needed by Calc:

- ID Automação
- ID Externo when useful to the client
- Status
- Mensagem
- Desconto Calculado
- Último Link Publicado
- Assinatura dos Dados when needed for synchronization bookkeeping
- Última Verificação
- Última Atualização

The endpoint never returns GitHub credentials or unrelated sheet data.

### `health`

Returns only a minimal authenticated service-health response suitable for installation diagnostics.

## Apps Script Field Ownership

The Calc client may write only the approved import-input fields:

- ID Automação
- Ativo
- Publicar
- Destaque
- Ordem
- Modo de Atualização
- Link do Produto
- Link de Afiliado
- Plataforma
- Nome
- Descrição
- Categoria
- Subcategoria
- Tipo
- Preço Atual
- Preço Anterior
- Cupom
- Validade do Cupom
- Imagem 1-4
- Texto do Botão

The client may not directly write:

- backend Status
- backend Mensagem
- Tentativas Consecutivas
- Último Link Publicado
- Assinatura dos Dados
- Última Verificação
- Última Atualização
- Desconto Calculado

`ID Externo` is backend-controlled by default. If a future workflow requires user-supplied external identity, that must be designed explicitly rather than silently added to the client write allowlist.

## Authentication and Credential Separation

Transport uses HTTPS plus HMAC-SHA256.

### Shared secret

A random 256-bit `ORVANI_SYNC_SECRET` exists in exactly these two locations:

- local Linux config, e.g. `~/.config/orvani-sync/orvani.env`
- Apps Script Script Properties

The local file is permission-restricted to the user (`0600`).

The secret is not stored in:

- `Orvani.ods`
- repository source
- GitHub Actions logs
- request logs

### Signed request

Each request includes:

- protocol version
- action
- timestamp
- nonce
- canonical payload
- HMAC signature

The HMAC is calculated over a deterministic canonical representation of the protocol version, action, timestamp, nonce, and request body.

Both sides must use the same canonicalization algorithm. The raw shared secret is never transmitted.

### Replay protection

Apps Script accepts a timestamp only within a narrow window, initially ±2 minutes.

A nonce is single-use within the replay window. Recently accepted nonces are stored with bounded lifetime using Apps Script caching suitable for replay prevention.

Duplicate nonce or stale timestamp requests are rejected.

### GitHub credential

`GITHUB_TOKEN` remains in Apps Script Script Properties. It is never exposed to the local Python service or LibreOffice.

## Local Python Service

The new code is isolated under a dedicated package rather than being folded into the existing sync engine.

Proposed structure:

```text
libreoffice_sync/
├── models.py
├── validation.py
├── hashing.py
├── uno_client.py
├── api_client.py
├── sync_service.py
└── main.py

systemd/
└── orvani-sync.service
```

### Responsibilities

`models.py`
: Transport/domain models for local Calc rows and status responses.

`validation.py`
: Local preflight validation only. Backend validation remains authoritative.

`hashing.py`
: Canonical row hashing over user-editable fields.

`uno_client.py`
: Discovery of the open `Orvani.ods`, reading/writing cells, save-event observation, and safe status-cell updates through UNO.

`api_client.py`
: HTTPS transport, canonical request creation, HMAC signing, bounded retries, and response validation.

`sync_service.py`
: Coordinates save-triggered uploads and periodic status refresh.

`main.py`
: Process entry point and lifecycle.

## LibreOffice / UNO Safety

The local service does not open and rewrite the `.ods` package behind LibreOffice's back while the document is open.

All live document interaction occurs through UNO.

Rules:

- User-editable cells are only read by the service during synchronization.
- Automatic status cells and hidden technical fields are the only cells the service writes.
- Backend status polling must not automatically save the workbook on every 20-second refresh; it updates the live document state, and normal user saves persist those changes.
- The service must detect the intended workbook by document URL/path and expected sheet structure, not merely the existence of any Calc window.
- If `Orvani.ods` is not open, the service remains idle rather than manipulating the file directly.

## Status Polling

While `Orvani.ods` is open, the local service requests backend status approximately every 20 seconds.

The poll is bounded to IDs present in the workbook and updates only when returned values differ from currently displayed values.

This permits visible transitions such as:

```text
NOVO → PROCESSANDO → PUBLICADO
```

without closing Calc.

The interval is configuration data, with 20 seconds as the initial default.

## Offline and Retry Behavior

No local database or complex durable queue is introduced in version 1.

The workbook itself plus acknowledged row hashes provide restart-safe state:

- A changed row whose new hash was never acknowledged remains different from its last acknowledged hash and is retried later.
- A successful upsert updates the acknowledged hash locally.
- Network failure does not advance the acknowledged hash.

For transient network/server errors, the client uses bounded exponential backoff with jitter.

Permanent validation/authentication errors are surfaced in Calc and are not retried in a tight loop.

If the computer is shut down after Google Sheets accepted the write, the cloud pending workflow remains independent and continues normally.

## Linux Service

A `systemd --user` unit starts the local process when the user logs in.

Expected lifecycle:

```text
Linux user login
→ orvani-sync.service starts
→ service waits for LibreOffice/Orvani.ods
→ document appears
→ service attaches through UNO
→ save events trigger uploads
→ 20-second status polling runs while attached
```

The service should restart on unexpected process failure with a conservative delay, but not spin indefinitely on permanent configuration errors.

## Installation Configuration

Local configuration contains only local integration settings such as:

- Apps Script Web App URL
- `ORVANI_SYNC_SECRET`
- optional polling interval
- expected workbook path/name

No Google password, service-account JSON, or GitHub token is required locally.

The installation process must include a diagnostic command/health check so configuration can be verified before enabling automatic startup.

## Error Handling

### Local validation error

- Do not upload.
- Show a local error state/message in Calc.
- Retry only after the row changes or the user saves after correction.

### Offline/network failure

- Preserve unsynchronized row state.
- Retry with bounded backoff while the document remains open.
- Retry after reconnect/restart because the acknowledged hash is still old.

### Apps Script authentication failure

- Do not write to Sheets.
- Show a configuration/authentication error locally.
- Avoid rapid retries.

### Duplicate ID Automação in Sheets

- Reject the affected record.
- Do not update an arbitrary row.
- Surface a data-integrity error requiring correction.

### Pending/backend publication error

- Let the existing backend write its Status/Mensagem.
- `get_status` returns those values.
- Calc displays them without converting them to a client-side success state.

### LibreOffice closed

- Service stays idle.
- No direct `.ods` mutation.

## Compatibility with Existing Automation

The existing `Importações` and `Produtos` schemas remain in place.

Current `Importações` already provides the separation needed between input columns and backend state columns. The new Web App maps the Calc schema into that existing structure rather than introducing a second publication table.

The existing workflow file, Google service-account access, partner connectors, `pending` execution, publication planning, persistence verification, Google Sheets `Produtos` writes, and frontend catalog reading remain the publication backbone.

Existing SHEIN and Mercado Livre manual fallback behavior is preserved. The new general Manual update mode is a first-class backend behavior, not a replacement for partner-specific safety checks.

## Testing Strategy

Implementation follows TDD for new behavior.

### Local pure-unit tests

Cover:

- row canonicalization and hashing
- decimal normalization
- UUID/identity handling
- editable vs backend-owned fields
- validation rules
- HMAC canonicalization/signing
- response parsing
- retry classification

### Backend Manual-mode tests

Cover:

- `UpdateMode.MANUAL` parsing
- manual snapshot/publication behavior
- public connector metadata does not overwrite Calc-authoritative catalog fields in Manual mode
- backend validation remains active
- product identity/matching remains deterministic
- existing Automatic and Blocked behavior does not regress
- existing SHEIN/Mercado Livre fallback tests remain green

### Apps Script contract tests

Use pure functions where possible for:

- canonical signature verification
- request schema validation
- client-write allowlist
- upsert by `ID Automação`
- create vs update behavior
- duplicate-ID rejection
- backend-owned-field rejection
- idempotent retry behavior
- batching and one-dispatch-per-accepted-batch semantics
- status response projection

### UNO adapter tests

Keep UNO-specific code thin and isolate it behind an interface. Unit-test mapping against fakes, then run an integration smoke test with a real LibreOffice instance on Linux.

### Integration stages

1. Local unit suites.
2. Backend regression suites.
3. Apps Script dry integration without GitHub dispatch/publication.
4. Calc → Apps Script → `Importações` with one test row.
5. Full one-product test: Calc → Importações → pending → Produtos → site.
6. Status-return verification in the open Calc document.
7. Restart/reconnect verification for the `systemd --user` service.

## Operational Success Criteria

The feature is complete when all of the following are true:

- The user can manage catalog products primarily from `Orvani.ods`.
- Saving the workbook uploads only changed valid rows.
- Saving unchanged content does not create duplicate rows or unnecessary pending dispatches.
- One Calc row maps to exactly one `Importações` row through `ID Automação`.
- Manual mode preserves Calc-authored product metadata through pending publication.
- A successful upload can continue to publication after the local computer is turned off.
- While the workbook is open, backend status changes appear in Calc automatically without external file rewriting.
- Secrets are absent from the workbook and repository.
- The local machine never needs the GitHub PAT or Google service-account credential.
- Existing Automatic/Blocked modes and current partner flows retain their tested behavior.

## Explicit Non-Goals for Version 1

To keep the first implementation maintainable, version 1 does not include:

- bidirectional editing of product metadata from Google Sheets back into Calc
- multi-user conflict resolution
- a local SQL database
- a general-purpose offline queue independent of the workbook
- arbitrary spreadsheet selection
- Windows/macOS autostart packaging
- direct Google Sheets API credentials on the local computer
- direct GitHub API access from the local computer

Only backend-owned status/operational fields flow from Google Sheets back to Calc. Product metadata edits originate in Calc.
