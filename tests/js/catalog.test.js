const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");

require("../../script.js");
const core = globalThis.OrvaniCore;

const currentHeaders = [
  "Ativo *", "Tipo", "Plataforma", "Categoria", "Subcategoria", "Nome", "Descrição",
  "Preço *", "Preço Promocional", "Cupom", "Validade da oferta", "Link de Afiliado",
  "Texto do Botão", "Vídeo (URL YouTube)", "Imagem 1 *", "Imagem 2", "Imagem 3",
  "Imagem 4", "Ordem", "Destaque",
];

class FakeNode {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.attributes = {};
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.hidden = false;
    this.replaceCount = 0;
    this.style = {};
    this.classList = {
      add() {},
      remove() {},
      toggle() {},
    };
  }

  addEventListener() {}

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.replaceCount += 1;
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
}

function loadBrowserApp() {
  const nodes = {
    hero: new FakeNode(),
    featuredSection: new FakeNode("section"),
    track: new FakeNode(),
    controls: new FakeNode(),
    indicators: new FakeNode(),
    categories: new FakeNode(),
  };
  const selectors = new Map([
    ["#hero-product-stack", nodes.hero],
    ["#destaques", nodes.featuredSection],
    ["#carousel-track", nodes.track],
    ["#carousel-controls", nodes.controls],
    ["#carousel-indicators", nodes.indicators],
    ["#category-list", nodes.categories],
  ]);
  const document = {
    body: { dataset: { page: "home" }, classList: { add() {} } },
    hidden: false,
    readyState: "loading",
    addEventListener() {},
    createElement: (tagName) => new FakeNode(tagName),
    querySelector: (selector) => selectors.get(selector) ?? null,
  };
  const context = {
    console,
    document,
    location: { hash: "", pathname: "/", search: "" },
    matchMedia: () => ({ matches: true, addEventListener() {}, removeEventListener() {} }),
    requestAnimationFrame: (callback) => callback(),
    setTimeout,
    clearTimeout,
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(__dirname, "../../script.js"), "utf8"),
    context,
  );
  return { app: context.OrvaniApp, core: context.OrvaniCore, nodes };
}

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

test("accepts Google Sheets numeric price exports with zero, one, or two decimal places", () => {
  const fixture = fs.readFileSync(path.join(__dirname, "../fixtures/catalog-current.csv"), "utf8");
  const [, source] = core.parseCsv(fixture);

  const cases = [
    ["39", 39],
    ["39.7", 39.7],
    ["39,7", 39.7],
    ["39.70", 39.7],
    ["39,70", 39.7],
  ];

  for (const [rawPrice, expectedPrice] of cases) {
    const row = source.slice();
    row[7] = rawPrice;
    row[8] = "";

    const result = core.normalizeRows([currentHeaders, row]);

    assert.equal(result.rejected.length, 0, `preco ${rawPrice} foi rejeitado`);
    assert.equal(result.products.length, 1);
    assert.equal(result.products[0].currentPrice, expectedPrice);
  }
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

test("home catalog rendering never replaces the institutional hero artwork", () => {
  const { app, nodes } = loadBrowserApp();

  app.renderHome([]);

  assert.equal(nodes.hero.replaceCount, 0);
});

test("rendered catalog images explicitly preserve the whole image inside their frame", () => {
  const { app, core: browserCore } = loadBrowserApp();
  const css = fs.readFileSync(path.join(__dirname, "../../style.css"), "utf8");

  const card = app.createProductCard(browserCore.DEMO_PRODUCTS[0], 0);
  const catalogImage = card.children[0].children[0];

  assert.equal(catalogImage.tagName, "IMG");
  assert.equal(catalogImage.style.objectFit, "contain");
  assert.equal(catalogImage.style.objectPosition, "center");

  assert.match(
    css,
    /\.featured-primary-media img\s*\{[^}]*width:\s*auto\s*!important;[^}]*height:\s*auto\s*!important;[^}]*max-width:\s*100%\s*!important;[^}]*max-height:\s*100%\s*!important;[^}]*object-fit:\s*contain\s*!important;/s,
  );
  assert.match(
    css,
    /\.featured-secondary-media img\s*\{[^}]*width:\s*auto\s*!important;[^}]*height:\s*auto\s*!important;[^}]*max-width:\s*100%\s*!important;[^}]*max-height:\s*100%\s*!important;[^}]*object-fit:\s*contain\s*!important;/s,
  );
});

test("selects semantic Bootstrap Icons from normalized category names", () => {
  const cases = [
    ["  ELETRÔNICOS ", "bi bi-laptop"],
    ["Eletrodomésticos", "bi bi-house-gear"],
    ["Esporte e Lazer", "bi bi-bicycle"],
    ["Beleza e Maquiagem", "bi bi-stars"],
    ["Brinquedos", "bi bi-balloon"],
    ["Moda", "bi bi-handbag"],
    ["Casacos", "bi bi-handbag"],
    ["Perfumaria", "bi bi-droplet"],
    ["Instrumentos Musicais", "bi bi-music-note-beamed"],
    ["Jogo de cama", "bi bi-house-heart"],
    ["Bem Estar", "bi bi-heart-pulse"],
  ];

  assert.deepEqual(
    cases.map(([category]) => core.categoryIconClass?.(category)),
    cases.map(([, icon]) => icon),
  );
});

test("gives every unmatched new category a generic Bootstrap Icon", () => {
  assert.equal(core.categoryIconClass?.("Categoria completamente inédita"), "bi bi-grid");
  assert.equal(core.categoryIconClass?.(""), "bi bi-grid");
});

test("renders category cards with their semantic icon hidden from assistive text", () => {
  const { app, core: browserCore, nodes } = loadBrowserApp();

  app.renderHome([browserCore.DEMO_PRODUCTS[0]]);
  const icon = nodes.categories.children[0].children[0];

  assert.deepEqual(
    { tagName: icon.tagName, className: icon.className, ariaHidden: icon.attributes["aria-hidden"] },
    { tagName: "I", className: "category-chip-icon bi bi-laptop", ariaHidden: "true" },
  );
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


test("product detail presentation prefers the full description and unique images", () => {
  assert.equal(typeof core.productDetailsPresentation, "function");

  const product = {
    ...core.DEMO_PRODUCTS[0],
    shortDescription: "Resumo curto.",
    description: "Descrição completa do produto sem qualquer corte.",
    primaryImage: "https://images.example/primary.jpg",
    images: Object.freeze([
      "https://images.example/second.jpg",
      "https://images.example/primary.jpg",
    ]),
    subcategory: "Liquidificadores",
  };

  const details = core.productDetailsPresentation(product);

  assert.equal(details.description, "Descrição completa do produto sem qualquer corte.");
  assert.equal(details.category, product.category);
  assert.equal(details.subcategory, "Liquidificadores");
  assert.equal(details.partner, "Amazon");
  assert.deepEqual(
    [...details.images],
    [
      "https://images.example/primary.jpg",
      "https://images.example/second.jpg",
    ],
  );
});

test("catalog cards expose a separate details action instead of a direct store link", () => {
  const { app, core: browserCore } = loadBrowserApp();
  assert.equal(typeof app.createProductCard, "function");

  const card = app.createProductCard(browserCore.DEMO_PRODUCTS[0], 0);
  const body = card.children[1];
  const footer = body.children[body.children.length - 1];
  const detailsButton = footer.children[footer.children.length - 1];

  assert.equal(detailsButton.tagName, "BUTTON");
  assert.equal(detailsButton.className.includes("product-details-button"), true);
  assert.equal(detailsButton.textContent, "Ver detalhes");
  assert.equal(footer.children.some((node) => node.tagName === "A"), false);
});

test("responsive catalog contract keeps two phone columns, static featured showcase, original logo and a product dialog", () => {
  const css = fs.readFileSync(path.join(__dirname, "../../style.css"), "utf8");
  const catalogHtml = fs.readFileSync(path.join(__dirname, "../../catalogo.html"), "utf8");
  const homeHtml = fs.readFileSync(path.join(__dirname, "../../index.html"), "utf8");

  assert.match(css, /Responsive catalog, compact carousel and product details/);
  assert.match(
    css,
    /\.product-grid\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
  );
  assert.match(css, /\.brand-logo\s*\{[^}]*color-scheme:\s*only light/s);
  assert.match(css, /\.product-dialog\s*\{/);

  assert.match(homeHtml, /id="featured-showcase"/);
  assert.match(homeHtml, /id="featured-primary"/);
  assert.match(homeHtml, /id="featured-secondary"/);
  assert.doesNotMatch(homeHtml, /id="featured-carousel"/);

  assert.match(catalogHtml, /<dialog class="product-dialog" id="product-dialog"/);
  assert.match(catalogHtml, /id="product-dialog-description"/);
  assert.match(catalogHtml, /id="product-dialog-image"/);
  assert.match(catalogHtml, /id="product-dialog-offer"/);
});

test("image polish keeps featured showcase and detail images fully visible and details CTA branded", () => {
  const css = fs.readFileSync(path.join(__dirname, "../../style.css"), "utf8");

  assert.match(css, /Product image polish: full visibility and branded details CTA/);
  assert.match(css, /Static featured showcase: complete product images/);

  assert.match(
    css,
    /\.featured-primary-media img\s*\{[^}]*width:\s*auto\s*!important;[^}]*height:\s*auto\s*!important;[^}]*max-width:\s*100%\s*!important;[^}]*max-height:\s*100%\s*!important;[^}]*object-fit:\s*contain\s*!important;/s,
  );
  assert.match(
    css,
    /\.featured-secondary-media img\s*\{[^}]*width:\s*auto\s*!important;[^}]*height:\s*auto\s*!important;[^}]*max-width:\s*100%\s*!important;[^}]*max-height:\s*100%\s*!important;[^}]*object-fit:\s*contain\s*!important;/s,
  );
  assert.match(
    css,
    /\.product-dialog-image-wrap img\s*\{[^}]*width:\s*auto[^}]*height:\s*auto[^}]*max-width:\s*100%[^}]*max-height:\s*100%[^}]*object-fit:\s*contain\s*!important/s,
  );
  assert.match(
    css,
    /\.product-details-button\s*\{[^}]*background:\s*var\(--brand\)[^}]*color:\s*#fff/s,
  );
  assert.match(
    css,
    /\.product-details-button:hover\s*\{[^}]*background:\s*var\(--brand-strong\)/s,
  );
});

test("footer exposes only the current public partner set without removing internal partner config", () => {
  assert.equal(typeof core.footerPartnerLabels, "function");
  assert.deepEqual(
    [...core.footerPartnerLabels()],
    ["Mercado Livre", "SHEIN", "Shopee"],
  );

  assert.deepEqual(
    Object.keys(core.CONFIG.affiliatePartners),
    [
      "amazon",
      "shopee",
      "mercado_livre",
      "aliexpress",
      "shein",
      "magalu",
      "natura",
      "hotmart",
      "tiktok_shop",
    ],
  );
});

test("home categories use a compact two-column phone layout with a very-narrow fallback", () => {
  const css = fs.readFileSync(path.join(__dirname, "../../style.css"), "utf8");

  assert.match(
    css,
    /Mobile categories: two-column access and curated footer partners/,
  );
  assert.match(
    css,
    /\.category-list\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
  );
  assert.match(
    css,
    /@media \(max-width:\s*37\.99rem\)\s*\{[\s\S]*?\.category-chip\s*\{[\s\S]*?min-height:\s*6\.6rem;[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto;/,
  );
  assert.match(
    css,
    /@media \(max-width:\s*22rem\)\s*\{[\s\S]*?\.category-list\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\);/,
  );
  assert.match(
    css,
    /@media \(min-width:\s*72rem\)\s*\{[\s\S]*?\.category-list\s*\{\s*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\);/,
  );
});

test("home featured products use a static showcase with complete images and no carousel runtime", () => {
  const html = fs.readFileSync(path.join(__dirname, "../../index.html"), "utf8");
  const script = fs.readFileSync(path.join(__dirname, "../../script.js"), "utf8");
  const css = fs.readFileSync(path.join(__dirname, "../../style.css"), "utf8");

  assert.match(html, /id="featured-showcase"/);
  assert.match(html, /id="featured-primary"/);
  assert.match(html, /id="featured-secondary"/);
  assert.match(html, /<dialog class="product-dialog" id="product-dialog"/);
  assert.doesNotMatch(html, /id="featured-carousel"/);
  assert.doesNotMatch(html, /id="carousel-track"/);
  assert.doesNotMatch(html, /id="carousel-controls"/);

  assert.match(script, /function createFeaturedPrimaryCard/);
  assert.match(script, /function createFeaturedSecondaryCard/);
  assert.match(script, /featured\.slice\(0,\s*5\)/);
  assert.doesNotMatch(script, /function createCarousel/);
  assert.doesNotMatch(script, /carouselController/);

  assert.match(css, /Static featured showcase: complete product images/);
  assert.match(
    css,
    /\.featured-primary-media img\s*\{[^}]*width:\s*auto\s*!important;[^}]*height:\s*auto\s*!important;[^}]*max-width:\s*100%\s*!important;[^}]*max-height:\s*100%\s*!important;[^}]*object-fit:\s*contain\s*!important;/s,
  );
  assert.match(
    css,
    /\.featured-secondary-media img\s*\{[^}]*width:\s*auto\s*!important;[^}]*height:\s*auto\s*!important;[^}]*max-width:\s*100%\s*!important;[^}]*max-height:\s*100%\s*!important;[^}]*object-fit:\s*contain\s*!important;/s,
  );
});
