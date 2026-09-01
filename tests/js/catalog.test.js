const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

require("../../script.js");
const core = globalThis.OrvaniCore;

const currentHeaders = [
  "Ativo *", "Tipo", "Plataforma", "Categoria", "Subcategoria", "Nome", "Descrição",
  "Preço *", "Preço Promocional", "Cupom", "Validade da oferta", "Link de Afiliado",
  "Texto do Botão", "Vídeo (URL YouTube)", "Imagem 1 *", "Imagem 2", "Imagem 3",
  "Imagem 4", "Ordem", "Destaque",
];

test("keeps the exact current twenty-column headers", () => {
  assert.deepEqual(core.CURRENT_SHEET_HEADERS, currentHeaders);
});

test("accepts the sanitized current fixture and maps sheet-only offer fields", () => {
  const fixture = fs.readFileSync(path.join(__dirname, "../fixtures/catalog-current.csv"), "utf8");
  const result = core.normalizeRows(core.parseCsv(fixture));

  assert.equal(result.rejected.length, 0);
  assert.equal(result.products.length, 2);
  assert.deepEqual(result.products.map((product) => product.name), ["Organizador de teste", "Fone de teste"]);
  assert.deepEqual(result.products.map((product) => product.subcategory), ["Organização", "Áudio"]);
  assert.deepEqual(result.products.map((product) => product.order), [1, 2]);
  const fone = result.products.find((product) => product.name === "Fone de teste");
  assert.deepEqual(fone.coupon, { code: "OFF10", expiresAt: new Date(9999, 11, 31, 23, 59, 59, 999) });
  assert.equal(fone.buttonText, "Comprar agora");
  assert.equal(fone.currentPrice, 149.9);
  assert.equal(fone.previousPrice, 199.9);
  assert.equal(fone.featured, true);
});

test("orders numerically then blanks with stable ties without mutating input", () => {
  const rows = [{ id: "a", order: null }, { id: "b", order: 2 }, { id: "c", order: 2 }, { id: "d", order: 1 }];
  const original = rows.slice();

  assert.deepEqual(core.sortProductsByOrder(rows).map(({ id }) => id), ["d", "b", "c", "a"]);
  assert.deepEqual(rows, original);
});

test("parses only blank or nonnegative integer orders", () => {
  assert.equal(core.parseOptionalOrder(""), null);
  assert.equal(core.parseOptionalOrder(" 0 "), 0);
  for (const raw of ["-1", "1.0", "1e2", "2x"]) {
    assert.throws(() => core.parseOptionalOrder(raw), /Linha inválida/);
  }
});

test("the production row adapter accepts only backend-safe integer orders", () => {
  const fixture = fs.readFileSync(path.join(__dirname, "../fixtures/catalog-current.csv"), "utf8");
  const [, source] = core.parseCsv(fixture);
  const safeIntegerRow = source.slice();
  safeIntegerRow[18] = "9007199254740991";
  const fractionalRow = source.slice();
  fractionalRow[18] = "1.5";

  const accepted = core.normalizeRows([currentHeaders, safeIntegerRow]);
  const rejected = core.normalizeRows([currentHeaders, fractionalRow]);

  assert.equal(accepted.products[0].order, Number.MAX_SAFE_INTEGER);
  assert.equal(accepted.rejected.length, 0);
  assert.equal(rejected.products.length, 0);
  assert.deepEqual(rejected.rejected[0].fields, ["ordem"]);
});

test("parses strict real offer dates at local end of day", () => {
  const iso = core.parseOfferDate("2026-08-29");
  const brazilian = core.parseOfferDate("29/08/2026");

  for (const value of [iso, brazilian]) {
    assert.equal(value.getFullYear(), 2026);
    assert.equal(value.getMonth(), 7);
    assert.equal(value.getDate(), 29);
    assert.equal(value.getHours(), 23);
    assert.equal(value.getMinutes(), 59);
    assert.equal(value.getSeconds(), 59);
    assert.equal(value.getMilliseconds(), 999);
  }
  for (const raw of ["", "2026-02-29", "31/04/2026", "2026-8-29", "29/8/2026", "2026-08-29T00:00:00"]) {
    assert.equal(core.parseOfferDate(raw), null);
  }
});

test("hides expired, malformed, and blank coupons while retaining valid no-expiry coupons", () => {
  const now = new Date(2026, 7, 29, 12, 0, 0, 0);

  assert.equal(core.validCoupon("", "", now), null);
  assert.equal(core.validCoupon("OFF10", "28/08/2026", now), null);
  assert.equal(core.validCoupon("OFF10", "31/04/2026", now), null);
  assert.deepEqual(core.validCoupon("OFF10", "", now), { code: "OFF10", expiresAt: null });
  assert.equal(core.validCoupon("OFF10", "29/08/2026", now).code, "OFF10");
});

test("normalizes custom buttons by whitespace and Unicode code points without interpreting data", () => {
  assert.equal(core.normalizeButtonText("  Comprar\n  agora "), "Comprar agora");
  assert.equal(core.normalizeButtonText(" <img src=x onerror=alert(1)> "), "<img src=x onerror=alert(1)>");
  const capped = core.normalizeButtonText("🙂".repeat(49));
  assert.equal(Array.from(capped).length, 48);
  assert.equal(capped, "🙂".repeat(48));
});

test("uses the partner default button when the custom button is empty", () => {
  const view = core.offerPresentation({ partner: "shopee", buttonText: "", coupon: null, couponExpiresAt: null });

  assert.equal(view.buttonText, "Ver oferta na Shopee");
});

test("preserves normalized custom button copy as literal text", () => {
  const view = core.offerPresentation({
    partner: "amazon",
    buttonText: "  <img src=x onerror=alert(1)>  ",
    coupon: null,
    couponExpiresAt: null,
  });

  assert.equal(view.buttonText, "<img src=x onerror=alert(1)>");
});

test("returns the exact safe external-link attributes from a normalized product", () => {
  const attributes = core.externalLinkAttributes({
    affiliateUrl: "https://shopee.com.br/product/1/1?affiliate=abc",
    name: "Fone <teste>",
    partner: "shopee",
  });

  assert.deepEqual(attributes, {
    href: "https://shopee.com.br/product/1/1?affiliate=abc",
    target: "_blank",
    rel: "sponsored nofollow noopener noreferrer",
    ariaLabel: "Ver oferta de Fone <teste> na Shopee",
  });
});

test("assigns malicious-looking content to a fake node only as literal text", () => {
  const node = { textContent: "antes" };
  const result = core.setNodeText(node, "<img src=x onerror=alert(1)>");

  assert.equal(result, node);
  assert.equal(node.textContent, "<img src=x onerror=alert(1)>");
  assert.equal(Object.hasOwn(node, "innerHTML"), false);
});

test("presents valid coupon code and localized expiry without mutating the product", () => {
  const expiresAt = new Date(2026, 7, 31, 23, 59, 59, 999);
  const product = {
    partner: "amazon",
    buttonText: "Comprar agora",
    coupon: { code: " OFF10 ", expiresAt },
    couponExpiresAt: expiresAt,
    currentPrice: 80,
    previousPrice: 100,
  };
  const snapshot = {
    ...product,
    coupon: { ...product.coupon },
    couponExpiresAt: product.couponExpiresAt,
  };

  const view = core.offerPresentation(product, new Date(2026, 7, 30, 12));

  assert.equal(view.buttonText, "Comprar agora");
  assert.equal(view.couponCode, "OFF10");
  assert.equal(view.couponExpiryText, "Válido até 31/08/2026");
  assert.equal(view.discount, 20);
  assert.deepEqual(product, snapshot);
  assert.equal(product.coupon.expiresAt, expiresAt);
});

test("presents coupons without an expiry and suppresses invalid or expired stored coupons at render time", () => {
  const now = new Date(2026, 7, 31, 12);
  const noExpiry = core.offerPresentation({
    partner: "amazon",
    buttonText: "",
    coupon: { code: "FRETE", expiresAt: null },
    couponExpiresAt: null,
  }, now);
  const expired = core.offerPresentation({
    partner: "amazon",
    buttonText: "",
    coupon: { code: "OFF10", expiresAt: new Date(2026, 7, 30, 23, 59, 59, 999) },
    couponExpiresAt: new Date(2026, 7, 30, 23, 59, 59, 999),
  }, now);
  const invalid = core.offerPresentation({
    partner: "amazon",
    buttonText: "",
    coupon: { code: "OFF10", expiresAt: new Date("invalid") },
    couponExpiresAt: new Date("invalid"),
  }, now);

  assert.equal(noExpiry.couponCode, "FRETE");
  assert.equal(noExpiry.couponExpiryText, null);
  assert.equal(expired.couponCode, null);
  assert.equal(expired.couponExpiryText, null);
  assert.equal(invalid.couponCode, null);
  assert.equal(invalid.couponExpiryText, null);
});

test("retains strict URL protections and names but does not authorize TikTok Shop broadly", () => {
  assert.equal(core.validatePartnerUrl("https://amazon.com.br.evil.example/item", "amazon"), null);
  assert.equal(core.validatePartnerUrl("http://amazon.com.br/item", "amazon"), null);
  assert.equal(core.validatePartnerUrl("https://shop.tiktok.com/item", "tiktok_shop"), null);
  assert.equal(core.partnerLabel("tiktok_shop"), "TikTok Shop");
  assert.deepEqual(core.CONFIG.affiliatePartners.tiktok_shop.hosts, []);
});

test("recognizes the TikTok Shop sheet alias but rejects its unconfigured URL", () => {
  const cells = [
    "Sim", "Físico", "TikTok Shop", "Eletrônicos", "Áudio", "Produto teste", "Descrição teste",
    "19.90", "", "", "", "https://shop.tiktok.com/item/123", "", "",
    "https://images.example.invalid/item.jpg", "", "", "", "", "Não",
  ];
  const result = core.normalizeRows([currentHeaders, cells]);

  assert.equal(result.products.length, 0);
  assert.deepEqual(result.rejected, [{
    row: 2,
    id: "sheet-tiktok-shop-produto-teste",
    code: "INVALID_ROW",
    fields: ["link_afiliado"],
  }]);
});

test("uses bounded Mercado and Shopee path identities independent of tracking query and fragment", () => {
  const mercadoA = core.stableSheetId(
    "Produto teste",
    "https://www.mercadolivre.com.br/produto-de-teste/p/MLB123456789?utm_source=one#details",
    "mercado_livre",
  );
  const mercadoB = core.stableSheetId(
    "Produto teste",
    "https://www.mercadolivre.com.br/produto-de-teste/p/MLB123456789?utm_source=two#reviews",
    "mercado_livre",
  );
  const shopeeA = core.stableSheetId(
    "Produto teste",
    "https://shopee.com.br/product/12345678/87654321?campaign=one#item",
    "shopee",
  );
  const shopeeB = core.stableSheetId(
    "Produto teste",
    "https://shopee.com.br/product/12345678/87654321?campaign=two#item",
    "shopee",
  );

  assert.equal(mercadoA, "sheet-mlb123456789");
  assert.equal(mercadoB, mercadoA);
  assert.equal(shopeeA, "sheet-shopee-87654321");
  assert.equal(shopeeB, shopeeA);
});

test("does not promote arbitrary numeric or query tokens into stable identities", () => {
  assert.equal(
    core.stableSheetId("Produto Teste", "https://shopee.com.br/collection/123?itemid=87654321", "shopee"),
    "sheet-shopee-produto-teste",
  );
  assert.equal(
    core.stableSheetId("Produto Teste", "https://www.mercadolivre.com.br/item?sku=MLB123456789", "mercado_livre"),
    "sheet-mercado-livre-produto-teste",
  );
});

test("accepts only Mercado Livre IDs with six through fifteen ASCII digits", () => {
  const fallback = "sheet-mercado-livre-produto-teste";
  const cases = [
    ["MLB123456", "sheet-mlb123456"],
    ["MLB123456789012345", "sheet-mlb123456789012345"],
    ["MLB12345", fallback],
    ["MLB1234567890123456", fallback],
  ];

  for (const [itemId, expected] of cases) {
    assert.equal(
      core.stableSheetId(
        "Produto Teste",
        `https://www.mercadolivre.com.br/produto-de-teste/p/${itemId}`,
        "mercado_livre",
      ),
      expected,
    );
  }
});

test("accepts only positive one-through-fifteen-digit Shopee path components", () => {
  const fallback = "sheet-shopee-produto-teste";
  const cases = [
    ["1", "1", "sheet-shopee-1"],
    ["123456789012345", "987654321098765", "sheet-shopee-987654321098765"],
    ["0", "1", fallback],
    ["01", "1", fallback],
    ["1", "0", fallback],
    ["1", "01", fallback],
    ["1234567890123456", "1", fallback],
    ["1", "1234567890123456", fallback],
  ];

  for (const [shopId, itemId, expected] of cases) {
    assert.equal(
      core.stableSheetId(
        "Produto Teste",
        `https://shopee.com.br/product/${shopId}/${itemId}`,
        "shopee",
      ),
      expected,
    );
  }
});

test("falls back for a trailing slash after a bounded Shopee product path", () => {
  assert.equal(
    core.stableSheetId(
      "Produto Teste",
      "https://shopee.com.br/product/1/1/",
      "shopee",
    ),
    "sheet-shopee-produto-teste",
  );
});

test("falls back to a bounded ID for adversarially long stable-path tokens", () => {
  const huge = "9".repeat(10000);
  const fallback = "sheet-mercado-livre-produto-teste";
  const result = core.stableSheetId(
    "Produto Teste",
    `https://www.mercadolivre.com.br/produto-de-teste/p/MLB${huge}`,
    "mercado_livre",
  );

  assert.equal(result, fallback);
  assert.equal(result.length, fallback.length);
});
