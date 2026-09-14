const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");

require("../../script.js");
const core = globalThis.OrvaniCore;

test("focused catalog hero cycles only active highlighted products", () => {
  assert.equal(typeof core.featuredProducts, "function");
  assert.equal(typeof core.featuredProductAt, "function");

  const products = [
    { id: "a", active: true, featured: true },
    { id: "b", active: true, featured: false },
    { id: "c", active: false, featured: true },
    { id: "d", active: true, featured: true },
    { id: "e", active: true, featured: true },
  ];

  assert.deepEqual(
    [...core.featuredProducts(products)].map((product) => product.id),
    ["a", "d", "e"],
  );

  assert.equal(core.featuredProductAt(products, 0).id, "a");
  assert.equal(core.featuredProductAt(products, 1).id, "d");
  assert.equal(core.featuredProductAt(products, 2).id, "e");
  assert.equal(core.featuredProductAt(products, 3).id, "a");
  assert.equal(core.featuredProductAt(products, -1).id, "e");
});

test("catalog redesign is limited to the hero and removes the large showcase", () => {
  const html = fs.readFileSync(
    path.join(__dirname, "../../catalogo.html"),
    "utf8",
  );
  const css = fs.readFileSync(
    path.join(__dirname, "../../style.css"),
    "utf8",
  );
  const script = fs.readFileSync(
    path.join(__dirname, "../../script.js"),
    "utf8",
  );

  assert.match(html, /id="catalog-hero-showcase"/);
  assert.match(html, /id="catalog-hero-feature"/);
  assert.match(html, /id="catalog-hero-indicators"/);

  assert.doesNotMatch(html, /id="catalog-featured"/);
  assert.doesNotMatch(html, /id="catalog-category-track"/);

  assert.match(css, /Focused catalog hero refinement/);
  assert.match(
    css,
    /body\[data-page="catalogo"\] \.catalog-hero h1\s*\{[^}]*color:\s*#0b1020/s,
  );
  assert.match(
    css,
    /\.catalog-hero-inner\.has-featured-product\s*\{[^}]*grid-template-columns:/s,
  );

  assert.match(script, /function createCatalogHeroSpotlight/);
  assert.match(script, /const intervalMs = 5000;/);
  assert.match(script, /renderCatalogHeroSpotlight\(products\)/);

  assert.doesNotMatch(script, /function createCatalogFeaturedRotator/);
  assert.doesNotMatch(script, /function renderCatalogCategoryStrip/);
});

test("catalog product grid remains on the pre-storefront presentation contract", () => {
  const script = fs.readFileSync(
    path.join(__dirname, "../../script.js"),
    "utf8",
  );
  const css = fs.readFileSync(
    path.join(__dirname, "../../style.css"),
    "utf8",
  );

  assert.doesNotMatch(script, /product-card-featured-badge/);
  assert.doesNotMatch(script, /product-card-discount-badge/);
  assert.doesNotMatch(css, /product-card-featured-badge/);
  assert.doesNotMatch(css, /Professional catalog storefront redesign/);
});
