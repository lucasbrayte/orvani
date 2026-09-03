const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");

const gsPath = path.resolve(__dirname, "../../apps_script/orvani_sync_webapp.gs");
const source = fs.readFileSync(gsPath, "utf8") + `
globalThis.OrvaniAppsScriptCore = {
  orvaniCanonicalJson_: typeof orvaniCanonicalJson_ === "function"
    ? orvaniCanonicalJson_
    : undefined,
  orvaniVerifyEnvelopeCore_: typeof orvaniVerifyEnvelopeCore_ === "function"
    ? orvaniVerifyEnvelopeCore_
    : undefined,
  orvaniValidateUpsertProduct_: typeof orvaniValidateUpsertProduct_ === "function"
    ? orvaniValidateUpsertProduct_
    : undefined,
  orvaniValidateActionPayload_: typeof orvaniValidateActionPayload_ === "function"
    ? orvaniValidateActionPayload_
    : undefined,
  orvaniPlanUpserts_: typeof orvaniPlanUpserts_ === "function"
    ? orvaniPlanUpserts_
    : undefined,
};
`;

const context = vm.createContext({
  console,
});
vm.runInContext(source, context, { filename: gsPath });
const core = context.OrvaniAppsScriptCore;

function fakeHmacHex() {
  return "a".repeat(64);
}

function signedEnvelope(overrides = {}) {
  return {
    version: "v1",
    action: "health",
    timestamp: 1000,
    nonce: "nonce_123456789012",
    payload: {},
    signature: "a".repeat(64),
    ...overrides,
  };
}

function validProduct(overrides = {}) {
  return {
    "ID Automação": "local-uuid",
    "Ativo": "Sim",
    "Publicar": "Sim",
    "Destaque": "Não",
    "Ordem": 10,
    "Modo de Atualização": "Manual",
    "Link do Produto": "https://www.mercadolivre.com.br/produto/p/MLB62276281?pdp_filters=item_id%3AMLB4431628133",
    "Link de Afiliado": "https://meli.la/abc123",
    "Plataforma": "Mercado Livre",
    "Nome": "Produto revisado",
    "Descrição": "Descrição revisada no Calc.",
    "Categoria": "Casa",
    "Subcategoria": "Cozinha",
    "Tipo": "Físico",
    "Preço Atual": 189.99,
    "Preço Anterior": 331.42,
    "Cupom": "ORVANI10",
    "Validade do Cupom": "2026-09-30",
    "Imagem 1": "https://http2.mlstatic.com/test.jpg",
    "Imagem 2": "",
    "Imagem 3": "",
    "Imagem 4": "",
    "Texto do Botão": "Ver oferta",
    ...overrides,
  };
}

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
  const envelope = signedEnvelope({ nonce: "nonce_123456789012" });
  assert.throws(
    () => core.orvaniVerifyEnvelopeCore_(
      envelope, "secret", envelope.timestamp, fakeHmacHex, () => false
    ),
    /nonce/i
  );
});

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

test("upsert rejects blank automation id", () => {
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(
      validProduct({ "ID Automação": "   " })
    ),
    /id automa/i
  );
});

test("upsert rejects invalid yes-no fields", () => {
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(
      validProduct({ "Publicar": "Talvez" })
    ),
    /publicar/i
  );
});

test("upsert rejects invalid update mode", () => {
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(
      validProduct({ "Modo de Atualização": "Qualquer" })
    ),
    /modo/i
  );
});

test("upsert rejects non-positive current price", () => {
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(
      validProduct({ "Preço Atual": 0 })
    ),
    /preço atual/i
  );
});

test("upsert_products accepts one validated product", () => {
  const result = core.orvaniValidateActionPayload_(
    "upsert_products",
    { products: [validProduct()] }
  );
  assert.equal(result.products.length, 1);
  assert.equal(result.products[0]["ID Automação"], "local-uuid");
});

test("get_status rejects duplicate ids", () => {
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "get_status",
      { ids: ["local-uuid", "local-uuid"] }
    ),
    /duplic/i
  );
});

test("health accepts only an empty payload", () => {
  assert.deepEqual(
    core.orvaniValidateActionPayload_("health", {}),
    {}
  );
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "health",
      { extra: true }
    ),
    /campo|payload/i
  );
});

test("unknown action is rejected", () => {
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "delete_products",
      {}
    ),
    /ação não suportada/i
  );
});

test("upsert_products rejects an empty batch", () => {
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "upsert_products",
      { products: [] }
    ),
    /1.*50|produt/i
  );
});

test("upsert_products rejects more than 50 products", () => {
  const products = Array.from({ length: 51 }, (_, index) =>
    validProduct({ "ID Automação": "local-" + index })
  );
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "upsert_products",
      { products }
    ),
    /50|produt/i
  );
});

test("get_status rejects an empty id list", () => {
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "get_status",
      { ids: [] }
    ),
    /entre 1 e 100 ids/i
  );
});

test("action payload rejects extra top-level fields", () => {
  assert.throws(
    () => core.orvaniValidateActionPayload_(
      "upsert_products",
      { products: [validProduct()], extra: true }
    ),
    /campo de payload não permitido/i
  );
});

test("upsert rejects text fields above the size limit", () => {
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(
      validProduct({ "Descrição": "x".repeat(10001) })
    ),
    /tamanho|10\.000|10000/i
  );
});

test("upsert rejects non-string text fields", () => {
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(
      validProduct({ "Nome": 123 })
    ),
    /nome.*texto|texto.*nome|nome.*string/i
  );
});

test("upsert rejects a fifth image field", () => {
  const product = validProduct();
  product["Imagem 5"] = "https://example.com/5.jpg";
  assert.throws(
    () => core.orvaniValidateUpsertProduct_(product),
    /campo não permitido/i
  );
});

const IMPORT_HEADERS = [
  "ID Automação", "Ativo", "Publicar", "Destaque", "Ordem", "Modo de Atualização",
  "Link do Produto", "Link de Afiliado", "Plataforma", "ID Externo", "Nome",
  "Descrição", "Categoria", "Subcategoria", "Tipo", "Preço Atual", "Preço Anterior",
  "Desconto Calculado", "Cupom", "Validade do Cupom", "Imagem 1", "Imagem 2",
  "Imagem 3", "Imagem 4", "Texto do Botão", "Status", "Mensagem",
  "Tentativas Consecutivas", "Último Link Publicado", "Assinatura dos Dados",
  "Última Verificação", "Última Atualização"
];

function sheetRowFromProduct(product, rowNumber, backendOverrides = {}) {
  const valuesByHeader = {
    ...product,
    "ID Externo": "MLB4431628133",
    "Desconto Calculado": 43,
    "Status": "PUBLICADO",
    "Mensagem": "",
    "Tentativas Consecutivas": 0,
    "Último Link Publicado": product["Link de Afiliado"] || "",
    "Assinatura dos Dados": "stored-signature",
    "Última Verificação": "2026-09-03T12:00:00Z",
    "Última Atualização": "2026-09-03T12:00:00Z",
    ...backendOverrides,
  };

  return {
    rowNumber,
    values: IMPORT_HEADERS.map((header) =>
      Object.prototype.hasOwnProperty.call(valuesByHeader, header)
        ? valuesByHeader[header]
        : ""
    ),
  };
}

test("new ID plans one create", () => {
  const plan = core.orvaniPlanUpserts_([], [validProduct()]);
  assert.equal(plan.mutations.length, 1);
  assert.equal(plan.mutations[0].create, true);
  assert.deepEqual(Array.from(plan.changedIds), ["local-uuid"]);
});

test("same ID and same editable data is idempotent", () => {
  const rows = [sheetRowFromProduct(validProduct(), 2)];
  const plan = core.orvaniPlanUpserts_(rows, [validProduct()]);
  assert.equal(plan.mutations.length, 0);
  assert.deepEqual(Array.from(plan.changedIds), []);
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

test("changed existing row plans server-owned reset values", () => {
  const existing = validProduct({ "Preço Atual": 189.99 });
  const incoming = validProduct({ "Preço Atual": 179.99 });
  const rows = [
    sheetRowFromProduct(existing, 7, {
      "Status": "PUBLICADO",
      "Mensagem": "ok",
      "Tentativas Consecutivas": 3,
      "Assinatura dos Dados": "old-signature",
      "Última Verificação": "2026-09-03T12:00:00Z",
      "Última Atualização": "2026-09-03T12:00:00Z",
    }),
  ];

  const plan = core.orvaniPlanUpserts_(rows, [incoming]);
  assert.equal(plan.mutations.length, 1);
  assert.equal(plan.mutations[0].create, false);
  assert.equal(plan.mutations[0].rowNumber, 7);
  assert.equal(plan.mutations[0].valuesByHeader["Preço Atual"], 179.99);
  assert.equal(plan.mutations[0].valuesByHeader.Status, "NOVO");
  assert.equal(plan.mutations[0].valuesByHeader.Mensagem, "");
  assert.equal(plan.mutations[0].valuesByHeader["Tentativas Consecutivas"], 0);
  assert.equal(plan.mutations[0].valuesByHeader["Assinatura dos Dados"], "");
  assert.equal(plan.mutations[0].valuesByHeader["Última Verificação"], "");
  assert.equal(plan.mutations[0].valuesByHeader["Última Atualização"], "");
});

test("new row mutation also includes backend reset values", () => {
  const plan = core.orvaniPlanUpserts_([], [validProduct()]);
  const mutation = plan.mutations[0];

  assert.equal(mutation.valuesByHeader.Status, "NOVO");
  assert.equal(mutation.valuesByHeader.Mensagem, "");
  assert.equal(mutation.valuesByHeader["Tentativas Consecutivas"], 0);
  assert.equal(mutation.valuesByHeader["Assinatura dos Dados"], "");
  assert.equal(mutation.valuesByHeader["Última Verificação"], "");
  assert.equal(mutation.valuesByHeader["Última Atualização"], "");
});

test("numeric sheet prices compare equal to numeric client prices", () => {
  const product = validProduct({
    "Preço Atual": 189.99,
    "Preço Anterior": 331.42,
  });
  const row = sheetRowFromProduct(product, 2);

  const priceIndex = IMPORT_HEADERS.indexOf("Preço Atual");
  const previousIndex = IMPORT_HEADERS.indexOf("Preço Anterior");
  row.values[priceIndex] = "189.99";
  row.values[previousIndex] = "331.42";

  const plan = core.orvaniPlanUpserts_([row], [product]);
  assert.equal(plan.mutations.length, 0);
  assert.deepEqual(Array.from(plan.changedIds), []);
});
