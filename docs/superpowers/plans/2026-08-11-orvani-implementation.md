# Orvani Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a Orvani como um catálogo de afiliados brasileiro completo, acessível, verificável e funcional em modo demo, com integrações server-side opcionais para Supabase e Google Sheets.

**Architecture:** O App Router renderiza páginas no servidor e delega apenas menu, carrossel, filtros progressivos e compartilhamento a Client Components pequenos. O domínio puro é separado dos adapters de Supabase/Google, a sincronização opera por snapshot idempotente, e o redirecionamento busca a URL armazenada antes de aplicar allowlist estrita e registrar uma métrica mínima.

**Tech Stack:** Node.js 24.19.0 disponível; Next.js 16.3.0, React 19.2.8, Tailwind CSS 4.3.3, TypeScript estrito, Zod, Supabase JS, Google APIs, Embla Carousel, Vitest 4.1.10, Playwright 1.62.1 e Axe.

## Global Constraints

- Interface e documentação em português do Brasil; marca Orvani e slogan “Boas escolhas em um só lugar.”
- Cores `#635BFF`, `#0B1020`, `#F7F8FC` e `#FF6B4A`; coral somente para ofertas e destaques.
- Manrope nos títulos e Inter nos textos via `next/font`, com fallbacks de sistema.
- Server Components por padrão; nenhum segredo ou cliente administrativo em módulo com `"use client"`.
- Sem cadastro, carrinho, checkout, pagamento, avaliações, escassez, estoque ou depoimentos inventados.
- Conteúdo editorial renderizado como texto; nenhuma linha da planilha passa por `dangerouslySetInnerHTML`.
- URLs externas exigem HTTPS, parser nativo e allowlist por host exato ou subdomínio delimitado por ponto.
- Nenhum IP bruto, fingerprint, cookie não essencial ou analytics externo.
- WCAG 2.2 AA como objetivo; teclado completo, foco visível, contraste e `prefers-reduced-motion`.
- Nenhum deploy, recurso externo, credencial real ou serviço pago durante a implementação.
- Cada comportamento novo segue RED → GREEN → REFACTOR, com o teste falhando pelo motivo esperado antes do código de produção.
- As versões instaladas serão as versões estáveis consultadas no npm no início da execução e ficarão registradas em `package-lock.json`.

---

## File Map

### Project and configuration

- `package.json`: scripts e dependências.
- `package-lock.json`: resolução reproduzível das versões estáveis instaladas.
- `tsconfig.json`: TypeScript estrito e aliases.
- `eslint.config.mjs`: regras Next, React e TypeScript.
- `postcss.config.mjs`: Tailwind CSS v4.
- `next.config.ts`: imagens remotas validadas e headers estáticos.
- `vitest.config.ts`: testes unitários e de integração em Node.
- `playwright.config.ts`: servidor web e testes E2E.
- `src/proxy.ts`: nonce CSP e headers dependentes do ambiente.
- `.env.example`: nomes, finalidade e valores vazios.

### Domain, persistence, sync and security

- `src/domain/products/model.ts`: tipos públicos e administrativos de produto.
- `src/domain/products/schema.ts`: schemas Zod e enums.
- `src/domain/products/normalizers.ts`: preço, booleano, arrays, slug e desconto.
- `src/domain/products/query.ts`: busca, filtros, ordenação e paginação.
- `src/catalog/repository.ts`: contrato de leitura do catálogo.
- `src/catalog/demo-data.ts`: catálogo fictício.
- `src/catalog/demo-repository.ts`: implementação local.
- `src/catalog/supabase-repository.ts`: consultas públicas server-side.
- `src/catalog/admin-repository.ts`: URL afiliada e snapshot administrativo.
- `src/catalog/get-repository.ts`: seleção fail-closed do adapter.
- `src/config/env.ts`: schemas de ambiente por contexto.
- `src/integrations/supabase/client.ts`: clientes publishable e secret server-only.
- `src/integrations/google/sheets.ts`: leitura privada com escopo readonly.
- `src/sync/sheet-parser.ts`: cabeçalho e linhas independentes.
- `src/sync/catalog-sync.ts`: orquestração e relatório seguro.
- `src/sync/types.ts`: portas injetáveis para leitura/persistência/log.
- `src/security/external-url.ts`: parsing e allowlist de hosts.
- `src/security/secret.ts`: Bearer e comparação em tempo constante.
- `src/security/rate-limit.ts`: janela deslizante global em memória.
- `src/metrics/clicks.ts`: porta e adapter de métricas mínimas.
- `scripts/sync-catalog.ts`: comando administrativo.
- `supabase/migrations/202608110001_orvani_catalog.sql`: schema, RLS, grants, RPC e retenção.

### Application and UI

- `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css`: shell e home.
- `src/app/catalogo/page.tsx`: catálogo com URL como fonte de verdade.
- `src/app/produto/[slug]/page.tsx`: detalhe, JSON-LD e relacionados.
- `src/app/go/[productId]/route.ts`: redirecionamento validado.
- `src/app/api/internal/sync/route.ts`: sincronização autenticada.
- `src/app/{sobre,como-funciona,transparencia,privacidade,termos}/page.tsx`: institucionais.
- `src/app/{loading,error,not-found}.tsx`: estados globais.
- `src/app/catalogo/{loading,error}.tsx`: estados do catálogo.
- `src/app/produto/[slug]/{loading,error}.tsx`: estados do produto.
- `src/app/{robots,sitemap,opengraph-image}.ts(x)`: SEO técnico.
- `src/components/brand/logo.tsx`: símbolo e wordmark SVG.
- `src/components/layout/{site-header,mobile-menu,site-footer}.tsx`: navegação.
- `src/components/product/{product-card,product-grid,price,partner-badge,gallery}.tsx`: produto.
- `src/components/home/{hero,featured-carousel,category-shortcuts,affiliate-note}.tsx`: home.
- `src/components/catalog/{catalog-filters,active-filters,pagination,empty-state}.tsx`: catálogo.
- `src/components/product/share-actions.tsx`: Web Share, WhatsApp e clipboard.
- `src/lib/{format,metadata,structured-data}.ts`: helpers sem infraestrutura.

### Tests, fixtures and docs

- `tests/unit/*.test.ts`: domínio, URLs, secrets e ambiente.
- `tests/integration/*.test.ts`: parser, sincronização e repositórios.
- `tests/e2e/*.spec.ts`: fluxos, teclado, redirect e Axe.
- `tests/fixtures/products.ts`: fábrica tipada de produtos para testes.
- `tests/fixtures/sheets.ts`: linhas de planilha controladas.
- `tests/fixtures/sync-harness.ts`: store transacional in-memory e leitor controlável.
- `tests/fixtures/redirect-harness.ts`: repositório e coletor de métricas controláveis.
- `tests/fixtures/sync-route-harness.ts`: requests, relógio e limiter controláveis.
- `public/images/demo/*.svg`: ilustrações próprias e neutras.
- `public/images/product-fallback.svg`: fallback local.
- `docs/catalog-template.csv`: cabeçalho e uma linha fictícia.
- `README.md`: operação, segurança, credenciais e deploy manual.

---

### Task 1: Foundation, toolchain and application shell

**Files:**
- Delete: `index.html`
- Delete: `script.js`
- Delete: `style.css`
- Create: `package.json`
- Create: `package-lock.json`
- Create: `tsconfig.json`
- Create: `next-env.d.ts`
- Create: `eslint.config.mjs`
- Create: `postcss.config.mjs`
- Create: `next.config.ts`
- Create: `vitest.config.ts`
- Create: `playwright.config.ts`
- Create: `src/app/layout.tsx`
- Create: `src/app/page.tsx`
- Create: `src/app/globals.css`
- Create: `tests/unit/app-shell.test.ts`

**Interfaces:**
- Produces: scripts `dev`, `build`, `start`, `lint`, `typecheck`, `test`, `test:watch`, `test:e2e`, `sync:catalog`.
- Produces: alias `@/* -> ./src/*` and a root layout com idioma `pt-BR`.

- [ ] **Step 1: Confirm the three legacy placeholders are still empty and delete only those exact files**

Run: `Get-Item index.html,script.js,style.css | Select-Object Name,Length`

Expected: all three lengths are `0`; delete them with an `apply_patch` delete operation.

- [ ] **Step 2: Create package and compiler configuration, then install current stable dependencies**

Create scripts with these exact meanings:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "sync:catalog": "tsx scripts/sync-catalog.ts"
  }
}
```

Run:

```powershell
npm install next@16.3.0 react@19.2.8 react-dom@19.2.8 zod@latest @supabase/supabase-js@latest googleapis@latest embla-carousel-react@latest
npm install --save-dev typescript@latest @types/node@latest @types/react@latest @types/react-dom@latest tailwindcss@4.3.3 @tailwindcss/postcss@latest eslint@latest eslint-config-next@16.3.0 vitest@4.1.10 tsx@latest @playwright/test@1.62.1 @axe-core/playwright@latest
```

Expected: `package-lock.json` is created; `npm ls --depth=0` exits `0`.

- [ ] **Step 3: Write the failing shell test**

```ts
import { describe, expect, it } from "vitest";

describe("application shell", () => {
  it("publishes the Orvani name and Brazilian locale", async () => {
    const { siteIdentity } = await import("@/lib/site");
    expect(siteIdentity).toEqual({
      name: "Orvani",
      slogan: "Boas escolhas em um só lugar.",
      locale: "pt-BR",
    });
  });
});
```

- [ ] **Step 4: Run RED**

Run: `npm test -- tests/unit/app-shell.test.ts`

Expected: FAIL because `@/lib/site` does not exist.

- [ ] **Step 5: Implement the minimal shell and design tokens**

Create `src/lib/site.ts` exporting the exact object asserted above. Configure strict TypeScript, Tailwind PostCSS, `next/font` Manrope/Inter variables, metadata base, skip link, semantic `header/main/footer`, and CSS tokens:

```css
@theme inline {
  --color-brand: #635bff;
  --color-ink: #0b1020;
  --color-canvas: #f7f8fc;
  --color-offer: #ff6b4a;
  --font-heading: var(--font-manrope), ui-sans-serif, system-ui, sans-serif;
  --font-body: var(--font-inter), ui-sans-serif, system-ui, sans-serif;
}
```

- [ ] **Step 6: Run GREEN and static checks**

Run: `npm test -- tests/unit/app-shell.test.ts`

Expected: PASS `1` test.

Run: `npm run typecheck`

Expected: exit `0`.

- [ ] **Step 7: Commit**

```powershell
git add package.json package-lock.json tsconfig.json next-env.d.ts eslint.config.mjs postcss.config.mjs next.config.ts vitest.config.ts playwright.config.ts src tests index.html script.js style.css
git -c user.name="Codex" -c user.email="codex@local" commit -m "chore: scaffold Orvani application"
```

---

### Task 2: Product domain and strict normalization

**Files:**
- Create: `src/domain/products/model.ts`
- Create: `src/domain/products/schema.ts`
- Create: `src/domain/products/normalizers.ts`
- Create: `src/security/external-url.ts`
- Create: `tests/unit/product-normalizers.test.ts`
- Create: `tests/unit/external-url.test.ts`

**Interfaces:**
- Produces: `Product`, `PublicProduct`, `Partner`, `ProductType`, `StockStatus`.
- Produces: `parsePrice(value): number | null`, `parseBoolean(value): boolean`, `parseList(value): string[]`, `normalizeSlug(value): string`, `calculateDiscount(current, previous): number | null`.
- Produces: `parseAllowedHosts(csv): string[]`, `validateExternalUrl(raw, allowedHosts): URL`.

- [ ] **Step 1: Write failing normalization tests**

```ts
import { describe, expect, it } from "vitest";
import {
  calculateDiscount,
  normalizeSlug,
  parseBoolean,
  parseList,
  parsePrice,
} from "@/domain/products/normalizers";

describe("product normalizers", () => {
  it.each([
    ["1299.90", 1299.9],
    ["1.299,90", 1299.9],
    ["0,99", 0.99],
  ])("parses unambiguous price %s", (input, expected) => {
    expect(parsePrice(input)).toBe(expected);
  });

  it.each(["1,299.90", "R$ 10,00", "12.345", "-1.00", "0"])(
    "rejects invalid or ambiguous price %s",
    (input) => expect(() => parsePrice(input)).toThrow(),
  );

  it.each([["true", true], ["sim", true], ["1", true], ["false", false], ["não", false], ["0", false]])(
    "normalizes boolean %s",
    (input, expected) => expect(parseBoolean(input)).toBe(expected),
  );

  it("rejects unknown booleans", () => {
    expect(() => parseBoolean("talvez")).toThrow();
  });

  it("accepts JSON or pipe-separated lists", () => {
    expect(parseList('["leve", "digital"]')).toEqual(["leve", "digital"]);
    expect(parseList("leve|digital")).toEqual(["leve", "digital"]);
  });

  it("creates a stable ASCII slug", () => {
    expect(normalizeSlug("  Câmera & Ação  ")).toBe("camera-e-acao");
  });

  it("calculates only a valid rounded discount", () => {
    expect(calculateDiscount(75, 100)).toBe(25);
    expect(calculateDiscount(100, 100)).toBeNull();
    expect(calculateDiscount(120, 100)).toBeNull();
  });
});
```

- [ ] **Step 2: Write failing adversarial URL tests**

```ts
import { describe, expect, it } from "vitest";
import { validateExternalUrl } from "@/security/external-url";

const hosts = ["amazon.com.br", "amzn.to", "shopee.com.br", "mercadolivre.com.br"];

describe("external URL allowlist", () => {
  it.each([
    "https://amazon.com.br/produto",
    "https://www.amazon.com.br/produto",
    "https://s.shopee.com.br/abc",
  ])("allows exact hosts and delimited subdomains: %s", (value) => {
    expect(validateExternalUrl(value, hosts).protocol).toBe("https:");
  });

  it.each([
    "https://amazon.com.br.evil.example/item",
    "https://notamazon.com.br/item",
    "https://evil-amazon.com.br/item",
    "https://user:pass@amazon.com.br/item",
    "http://amazon.com.br/item",
    "https://amazon.com.br:444/item",
    "javascript:alert(1)",
    "data:text/html,hello",
    "https://%65vil.example/item",
    "https://127.0.0.1/item",
  ])("blocks unsafe destination: %s", (value) => {
    expect(() => validateExternalUrl(value, hosts)).toThrow();
  });
});
```

- [ ] **Step 3: Run RED**

Run: `npm test -- tests/unit/product-normalizers.test.ts tests/unit/external-url.test.ts`

Expected: FAIL because both modules are absent.

- [ ] **Step 4: Implement minimal pure functions and schemas**

Use anchored grammars: decimal `^(0|[1-9]\d*)\.\d{2}$`, Brazilian `^(0|[1-9]\d{0,2}(?:\.\d{3})*),\d{2}$`, and host match `hostname === allowed || hostname.endsWith("." + allowed)`. Reject IP literals, trailing-dot ambiguity, non-default ports and URL credentials before returning a normalized `URL`.

- [ ] **Step 5: Run GREEN**

Run: `npm test -- tests/unit/product-normalizers.test.ts tests/unit/external-url.test.ts`

Expected: all cases pass.

Run: `npm run typecheck`

Expected: exit `0`.

- [ ] **Step 6: Commit**

```powershell
git add src/domain src/security tests/unit
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add validated product domain"
```

---

### Task 3: Demo catalog, repository contract and query engine

**Files:**
- Create: `src/catalog/repository.ts`
- Create: `src/catalog/demo-data.ts`
- Create: `src/catalog/demo-repository.ts`
- Create: `src/catalog/get-repository.ts`
- Create: `src/domain/products/query.ts`
- Create: `src/lib/format.ts`
- Create: `public/images/demo/{moda,games,apps,assinaturas,eletronicos,casa}.svg`
- Create: `public/images/product-fallback.svg`
- Create: `tests/unit/product-query.test.ts`
- Create: `tests/integration/demo-repository.test.ts`
- Create: `tests/fixtures/products.ts`

**Interfaces:**
- Produces: `CatalogQuery`, `CatalogPage`, `CatalogRepository.list(query)`, `.getBySlug(slug)`, `.getFeatured(limit)`, `.getRelated(product, limit)`.
- Produces: `getCatalogRepository(): CatalogRepository`, selecting demo only when the complete Supabase read configuration is absent outside production.
- Produces: `makeProduct(overrides?: Partial<Product>): Product` com defaults válidos e determinísticos.

- [ ] **Step 1: Write failing query tests**

```ts
import { describe, expect, it } from "vitest";
import { queryProducts } from "@/domain/products/query";
import { makeProduct } from "../fixtures/products";

const products = [
  makeProduct({ id: "1", name: "Câmera Compacta", category: "Eletrônicos", tags: ["foto"], currentPrice: 300, previousPrice: 400, partner: "amazon" }),
  makeProduct({ id: "2", name: "Curso de Fotografia", category: "Cursos", tags: ["foto"], type: "digital", currentPrice: 80, partner: "mercado_livre" }),
  makeProduct({ id: "3", name: "Fone Essencial", category: "Eletrônicos", currentPrice: 120, partner: "shopee" }),
];

describe("catalog query", () => {
  it("searches name, description and tags without accents", () => {
    expect(queryProducts(products, { search: "camera", page: 1, pageSize: 12 }).items.map((item) => item.id)).toEqual(["1"]);
    expect(queryProducts(products, { search: "foto", page: 1, pageSize: 12 }).total).toBe(2);
  });

  it("combines filters and sorts by price", () => {
    const result = queryProducts(products, {
      category: "Eletrônicos",
      partner: "shopee",
      minPrice: 100,
      maxPrice: 150,
      sort: "price_asc",
      page: 1,
      pageSize: 12,
    });
    expect(result.items.map((item) => item.id)).toEqual(["3"]);
  });

  it("paginates with bounded page size", () => {
    const result = queryProducts(products, { page: 2, pageSize: 1 });
    expect(result.page).toBe(2);
    expect(result.totalPages).toBe(3);
  });
});
```

Add the repository behavior test:

```ts
import { describe, expect, it } from "vitest";
import { DemoCatalogRepository } from "@/catalog/demo-repository";

describe("demo catalog repository", () => {
  it("returns only active products and resolves slug/related queries", async () => {
    const repository = new DemoCatalogRepository();
    const page = await repository.list({ page: 1, pageSize: 12 });
    expect(page.items.length).toBeGreaterThanOrEqual(12);
    expect(page.items.every((product) => product.active)).toBe(true);
    const product = await repository.getBySlug("fone-essencial");
    expect(product?.partner).toBe("shopee");
    expect((await repository.getRelated(product!, 4)).every((item) => item.id !== product!.id)).toBe(true);
  });
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- tests/unit/product-query.test.ts tests/integration/demo-repository.test.ts`

Expected: FAIL because query/repository modules and the product fixture are absent.

- [ ] **Step 3: Implement query, repository and twelve clearly fictitious products**

The data set must cover all six illustration categories, both types, all three partners, valid/absent previous prices, featured and non-featured items, and updated dates. Affiliate demo targets are official marketplace home URLs without affiliate identifiers. Each SVG includes visible text “Imagem ilustrativa” and no third-party logo.

- [ ] **Step 4: Run GREEN**

Run: `npm test -- tests/unit/product-query.test.ts tests/integration/demo-repository.test.ts`

Expected: all query and repository cases pass.

- [ ] **Step 5: Commit**

```powershell
git add src/catalog src/domain src/lib public/images tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add demo catalog repository"
```

---

### Task 4: Environment validation, Supabase schema and repositories

**Files:**
- Create: `src/config/env.ts`
- Create: `src/integrations/supabase/client.ts`
- Create: `src/catalog/supabase-repository.ts`
- Create: `src/catalog/admin-repository.ts`
- Create: `supabase/migrations/202608110001_orvani_catalog.sql`
- Create: `tests/unit/env.test.ts`
- Create: `tests/integration/supabase-mapping.test.ts`
- Create: `tests/integration/migration-security.test.ts`

**Interfaces:**
- Produces: `getPublicEnv()`, `getSupabaseReadEnv()`, `getSupabaseAdminEnv()`, `getSheetsEnv()`, `getAffiliateEnv()` with safe error messages.
- Produces: `SupabaseCatalogRepository` implementing `CatalogRepository`.
- Produces: `AdminCatalogRepository.getActiveAffiliateTarget(id)`, `.beginSync()`, `.failSync()`, `.applySnapshot()`.

- [ ] **Step 1: Write failing environment tests**

```ts
import { describe, expect, it } from "vitest";
import { parseRuntimeEnv } from "@/config/env";

describe("runtime environment", () => {
  it("uses demo with no integration credentials in development", () => {
    expect(parseRuntimeEnv({ NODE_ENV: "development" }).catalogMode).toBe("demo");
  });

  it("rejects a partial Supabase configuration without echoing values", () => {
    const secret = "sb_secret_sensitive";
    expect(() => parseRuntimeEnv({ NODE_ENV: "development", SUPABASE_URL: "https://example.supabase.co", SUPABASE_SECRET_KEY: secret })).toThrowError(/configuração incompleta/i);
    try { parseRuntimeEnv({ NODE_ENV: "development", SUPABASE_SECRET_KEY: secret }); } catch (error) {
      expect(String(error)).not.toContain(secret);
    }
  });

  it("requires production site and database configuration", () => {
    expect(() => parseRuntimeEnv({ NODE_ENV: "production" })).toThrowError(/produção/i);
  });
});
```

- [ ] **Step 2: Write failing migration security test**

```ts
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const sql = readFileSync("supabase/migrations/202608110001_orvani_catalog.sql", "utf8");

describe("catalog migration", () => {
  it.each(["products", "sync_runs", "affiliate_clicks"])("enables RLS on %s", (table) => {
    expect(sql).toMatch(new RegExp(`alter table public\\.${table} enable row level security`, "i"));
  });

  it("does not grant public access to affiliate URLs or metrics", () => {
    expect(sql).toMatch(/revoke all on public\.sync_runs from anon, authenticated/i);
    expect(sql).toMatch(/revoke all on public\.affiliate_clicks from anon, authenticated/i);
    expect(sql).not.toMatch(/grant select \([^)]*affiliate_url[^)]*\) to anon/i);
  });
});
```

Add the database-row mapper test without a network client:

```ts
import { describe, expect, it } from "vitest";
import { mapProductRow } from "@/catalog/supabase-repository";

describe("Supabase product mapping", () => {
  it("maps numeric strings and never requires affiliate_url for public reads", () => {
    const product = mapProductRow({
      id: "db-1", name: "Item", slug: "item", category: "Casa", type: "fisico",
      short_description: "Descrição", description: "Descrição completa",
      current_price: "49.90", previous_price: null, currency: "BRL",
      primary_image: "/images/product-fallback.svg", images: [], partner: "amazon",
      featured: false, active: true, stock_status: "informativo", tags: [],
      updated_at: "2026-08-11T00:00:00.000Z",
    });
    expect(product.currentPrice).toBe(49.9);
    expect(product).not.toHaveProperty("affiliateUrl");
  });
});
```

- [ ] **Step 3: Run RED**

Run: `npm test -- tests/unit/env.test.ts tests/integration/migration-security.test.ts tests/integration/supabase-mapping.test.ts`

Expected: FAIL because env, migration and repository mapping are absent.

- [ ] **Step 4: Implement the migration and adapters**

The migration must create enums, constraints, indexes, update timestamps, RLS, a public-active-products select policy, column-level grants excluding `affiliate_url`, and service-role-only functions:

```sql
create table public.products (..., affiliate_url text not null, active boolean not null default true, ...);
create table public.sync_runs (..., error_summary jsonb not null default '[]'::jsonb, ...);
create table public.affiliate_clicks (..., product_id text references public.products(id) on delete set null, partner text not null, clicked_at timestamptz not null default now());
alter table public.products enable row level security;
alter table public.sync_runs enable row level security;
alter table public.affiliate_clicks enable row level security;
create policy "active products are readable" on public.products for select to anon using (active = true);
revoke all on public.products, public.sync_runs, public.affiliate_clicks from anon, authenticated;
grant select (id, name, slug, category, type, short_description, description, current_price, previous_price, currency, primary_image, images, partner, featured, stock_status, tags, updated_at) on public.products to anon;
```

`apply_catalog_snapshot(jsonb, text[])` must lock synchronization, upsert by `id`, preserve IDs rejected with recognizable identifiers, deactivate only other missing active rows, finalize `sync_runs`, and return inserted/updated/deactivated counts. Revoke execute from `public` and grant it only to `service_role`. Add `aggregate_and_prune_affiliate_clicks(cutoff timestamptz default now() - interval '90 days')` with the same execute restriction.

- [ ] **Step 5: Run GREEN**

Run: `npm test -- tests/unit/env.test.ts tests/integration/migration-security.test.ts tests/integration/supabase-mapping.test.ts`

Expected: all environment, static migration and mapper tests pass without network.

- [ ] **Step 6: Commit**

```powershell
git add src/config src/integrations src/catalog supabase tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add Supabase catalog persistence"
```

---

### Task 5: Private Google Sheets adapter and row parser

**Files:**
- Create: `src/integrations/google/sheets.ts`
- Create: `src/sync/sheet-parser.ts`
- Create: `src/sync/types.ts`
- Create: `tests/fixtures/sheets.ts`
- Create: `tests/integration/sheet-parser.test.ts`

**Interfaces:**
- Produces: `SheetReader.read(): Promise<string[][]>` using `spreadsheets.values.get` and readonly scope.
- Produces: `parseSheet(rows, imageHosts, affiliateHosts): ParsedSheet` where `ParsedSheet = { valid: Product[]; rejected: RowRejection[]; preservedIds: string[]; rowsRead: number }`.

- [ ] **Step 1: Write failing parser tests**

```ts
import { describe, expect, it } from "vitest";
import { parseSheet } from "@/sync/sheet-parser";
import { header, validRow } from "../fixtures/sheets";

describe("private catalog sheet", () => {
  it("parses a valid row and normalizes private-key-independent data", () => {
    const result = parseSheet([header, validRow], ["images.example.com"], ["amazon.com.br"]);
    expect(result.valid).toHaveLength(1);
    expect(result.valid[0]).toMatchObject({ id: "demo-001", type: "fisico", partner: "amazon", currentPrice: 1299.9 });
    expect(result.rejected).toEqual([]);
  });

  it("rejects one invalid row without discarding valid rows", () => {
    const invalid = [...validRow];
    invalid[0] = "preserve-me";
    invalid[10] = "USD";
    const result = parseSheet([header, validRow, invalid], ["images.example.com"], ["amazon.com.br"]);
    expect(result.valid).toHaveLength(1);
    expect(result.rejected).toMatchObject([{ row: 3, id: "preserve-me" }]);
    expect(result.preservedIds).toEqual(["preserve-me"]);
  });

  it("fails the snapshot when required headers are missing or duplicated", () => {
    expect(() => parseSheet([["id", "nome"], validRow], [], [])).toThrowError(/cabeçalho/i);
    expect(() => parseSheet([[...header, "id"], validRow], [], [])).toThrowError(/duplicada/i);
  });

  it("sanitizes row errors", () => {
    const invalid = [...validRow];
    invalid[13] = "https://user:secret@amazon.com.br/item";
    const result = parseSheet([header, invalid], ["images.example.com"], ["amazon.com.br"]);
    expect(JSON.stringify(result.rejected)).not.toContain("secret");
  });
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- tests/integration/sheet-parser.test.ts`

Expected: FAIL because parser and fixtures are absent.

- [ ] **Step 3: Implement reader and parser**

Use `google.auth.JWT` with `https://www.googleapis.com/auth/spreadsheets.readonly`. Convert `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY.replace(/\\n/g, "\n")` only inside the adapter. Validate exact required headers, pad short rows safely, reject extra semantic data beyond column `S`, and report `{ row, id?, code, fields }` without raw values or caught stack traces.

- [ ] **Step 4: Run GREEN**

Run: `npm test -- tests/integration/sheet-parser.test.ts`

Expected: all parser cases pass.

- [ ] **Step 5: Commit**

```powershell
git add src/integrations/google src/sync tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: parse private catalog sheets"
```

---

### Task 6: Idempotent catalog synchronization and CLI

**Files:**
- Create: `src/sync/catalog-sync.ts`
- Create: `scripts/sync-catalog.ts`
- Create: `tests/integration/catalog-sync.test.ts`
- Create: `tests/fixtures/sync-harness.ts`

**Interfaces:**
- Consumes: `SheetReader`, `parseSheet`, `AdminCatalogRepository`.
- Produces: `synchronizeCatalog(deps): Promise<SyncResult>` with statuses `success`, `partial`, `failed`.
- Produces: `createMemorySyncHarness(options?)` exposing `withRows(name)`, `withReadError(error)` and a store with `activeIds()`/`uniqueProductCount()`; named snapshots are fixed in the fixture.

- [ ] **Step 1: Write failing synchronization tests**

```ts
import { describe, expect, it } from "vitest";
import { synchronizeCatalog } from "@/sync/catalog-sync";
import { createMemorySyncHarness } from "../fixtures/sync-harness";

describe("catalog synchronization", () => {
  it("imports valid rows and preserves recognizable rejected IDs", async () => {
    const harness = createMemorySyncHarness({ existingIds: ["valid", "invalid-old", "missing"] });
    const result = await synchronizeCatalog(harness.withRows("one-valid-one-invalid"));
    expect(result.status).toBe("partial");
    expect(result.imported).toBe(1);
    expect(result.rejected).toBe(1);
    expect(harness.store.activeIds()).toContain("invalid-old");
    expect(harness.store.activeIds()).not.toContain("missing");
  });

  it("preserves the full previous catalog after total read failure", async () => {
    const harness = createMemorySyncHarness({ existingIds: ["a", "b"] });
    const result = await synchronizeCatalog(harness.withReadError(new Error("network secret details")));
    expect(result.status).toBe("failed");
    expect(harness.store.activeIds()).toEqual(["a", "b"]);
    expect(JSON.stringify(result)).not.toContain("secret details");
  });

  it("is idempotent for an unchanged snapshot", async () => {
    const harness = createMemorySyncHarness();
    const first = await synchronizeCatalog(harness.withRows("valid-snapshot"));
    const second = await synchronizeCatalog(harness.withRows("valid-snapshot"));
    expect(first.imported).toBeGreaterThan(0);
    expect(second.imported).toBe(0);
    expect(second.updated).toBe(0);
    expect(harness.store.uniqueProductCount()).toBe(first.imported);
  });
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- tests/integration/catalog-sync.test.ts`

Expected: FAIL because sync orchestration and memory harness are absent.

- [ ] **Step 3: Implement orchestration and executable script**

The service begins a run before reading, never calls `applySnapshot` after a global error, classifies a run with rejected rows as `partial`, and logs only counts plus safe codes. The script must set a nonzero exit code for `failed`, print a single JSON summary without credentials, and use the real Google/Admin adapters only after scoped env validation.

- [ ] **Step 4: Run GREEN**

Run: `npm test -- tests/integration/catalog-sync.test.ts`

Expected: partial, total failure, idempotency and preservation cases pass.

- [ ] **Step 5: Verify the credential gate**

Run: `npm run sync:catalog`

Expected: exit nonzero with a safe Portuguese message naming missing variables, without a stack trace or secret value.

- [ ] **Step 6: Commit**

```powershell
git add src/sync scripts tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: synchronize catalog snapshots"
```

---

### Task 7: Secure affiliate redirect and minimal click metrics

**Files:**
- Create: `src/metrics/clicks.ts`
- Create: `src/app/go/[productId]/handler.ts`
- Create: `src/app/go/[productId]/route.ts`
- Create: `tests/integration/affiliate-redirect.test.ts`
- Create: `tests/fixtures/redirect-harness.ts`

**Interfaces:**
- Consumes: `AdminCatalogRepository.getActiveAffiliateTarget(id)` and `validateExternalUrl`.
- Produces: `handleAffiliateRedirect(productId, deps): Promise<Response>` returning `307`, `404` or safe `502`.
- Produces: `ClickMetrics.record({ productId, partner, clickedAt })` with no visitor identifier.
- Produces: `redirectHarness(options)` exposing `dependencies` and minimal recorded `events`.

- [ ] **Step 1: Write failing redirect tests**

```ts
import { describe, expect, it } from "vitest";
import { handleAffiliateRedirect } from "@/app/go/[productId]/handler";
import { redirectHarness } from "../fixtures/redirect-harness";

describe("affiliate redirect", () => {
  it("temporarily redirects an active stored destination and records a minimal click", async () => {
    const harness = redirectHarness({ url: "https://www.amazon.com.br/item", active: true });
    const response = await handleAffiliateRedirect("demo-001", harness.dependencies);
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://www.amazon.com.br/item");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(harness.events).toEqual([{ productId: "demo-001", partner: "amazon" }]);
  });

  it("returns 404 without a redirect for absent or inactive products", async () => {
    const response = await handleAffiliateRedirect("missing", redirectHarness({ target: null }).dependencies);
    expect(response.status).toBe(404);
    expect(response.headers.get("location")).toBeNull();
  });

  it.each([
    "https://amazon.com.br.evil.example/item",
    "https://user:pass@amazon.com.br/item",
    "http://amazon.com.br/item",
    "javascript:alert(1)",
    "data:text/html,hello",
  ])("blocks an unsafe stored destination: %s", async (url) => {
    const response = await handleAffiliateRedirect("demo-001", redirectHarness({ url, active: true }).dependencies);
    expect(response.status).toBe(502);
    expect(response.headers.get("location")).toBeNull();
  });

  it("still redirects if metric storage is unavailable", async () => {
    const response = await handleAffiliateRedirect("demo-001", redirectHarness({ url: "https://amazon.com.br/item", metricsError: true }).dependencies);
    expect(response.status).toBe(307);
  });
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- tests/integration/affiliate-redirect.test.ts`

Expected: FAIL because handler and metric adapter are absent.

- [ ] **Step 3: Implement a testable handler and thin route**

The route obtains `productId` only from the path, never accepts a destination parameter, creates dependencies server-side, and maps internal failures to generic text. Metric insertion catches and records only a fixed error code through `console.error`; it never blocks a valid redirect.

- [ ] **Step 4: Run GREEN**

Run: `npm test -- tests/unit/external-url.test.ts tests/integration/affiliate-redirect.test.ts`

Expected: every benign and adversarial URL case passes.

- [ ] **Step 5: Commit**

```powershell
git add src/metrics src/app/go tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add safe affiliate redirects"
```

---

### Task 8: Authenticated sync endpoint and rate limiting

**Files:**
- Create: `src/security/secret.ts`
- Create: `src/security/rate-limit.ts`
- Create: `src/app/api/internal/sync/handler.ts`
- Create: `src/app/api/internal/sync/route.ts`
- Create: `tests/unit/secret.test.ts`
- Create: `tests/integration/sync-route.test.ts`
- Create: `tests/fixtures/sync-route-harness.ts`

**Interfaces:**
- Produces: `verifyBearerSecret(header, expected): boolean` using `timingSafeEqual` only for equal-length buffers and a dummy comparison otherwise.
- Produces: `SlidingWindowLimiter.check(key, now): { allowed: boolean; retryAfterSeconds: number }`.
- Produces: `handleSyncRequest(request, deps): Promise<Response>`.
- Produces: `createSyncRouteHarness({ secret, max })` with deterministic `request(method, authOptions?)` calls.

- [ ] **Step 1: Write failing authentication and route tests**

```ts
import { describe, expect, it } from "vitest";
import { verifyBearerSecret } from "@/security/secret";

describe("sync secret", () => {
  it.each([null, "", "Basic abc", "Bearer", "Bearer wrong"])("rejects invalid authorization %s", (header) => {
    expect(verifyBearerSecret(header, "a".repeat(48))).toBe(false);
  });

  it("accepts only the exact Bearer secret", () => {
    const secret = "a".repeat(48);
    expect(verifyBearerSecret(`Bearer ${secret}`, secret)).toBe(true);
  });
});
```

```ts
it("allows POST with the exact secret and rejects GET, query secrets and bursts", async () => {
  const harness = createSyncRouteHarness({ secret: "a".repeat(48), max: 2 });
  expect((await harness.request("GET")).status).toBe(405);
  expect((await harness.request("POST", { querySecret: "a".repeat(48) })).status).toBe(401);
  expect((await harness.request("POST", { bearer: "a".repeat(48) })).status).toBe(200);
  expect((await harness.request("POST", { bearer: "a".repeat(48) })).status).toBe(200);
  expect((await harness.request("POST", { bearer: "a".repeat(48) })).status).toBe(429);
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- tests/unit/secret.test.ts tests/integration/sync-route.test.ts`

Expected: FAIL because secret, limiter and handler are absent.

- [ ] **Step 3: Implement security controls**

Use a global per-process key, six authenticated runs per ten minutes in production, `Retry-After`, `Cache-Control: no-store`, method `POST` only and a minimum 32-byte UTF-8 secret. Apply the limiter only after successful authentication so an unauthenticated caller cannot exhaust the administrative budget. Return `{ status, read, imported, updated, rejected, deactivated }` without row contents.

- [ ] **Step 4: Run GREEN**

Run: `npm test -- tests/unit/secret.test.ts tests/integration/sync-route.test.ts`

Expected: authentication, method, query-string rejection and rate-limit cases pass.

- [ ] **Step 5: Commit**

```powershell
git add src/security src/app/api tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: protect catalog sync endpoint"
```

---

### Task 9: Brand system, navigation, cards and home page

**Files:**
- Create: `src/components/brand/logo.tsx`
- Create: `src/components/layout/site-header.tsx`
- Create: `src/components/layout/mobile-menu.tsx`
- Create: `src/components/layout/site-footer.tsx`
- Create: `src/components/product/product-card.tsx`
- Create: `src/components/product/product-grid.tsx`
- Create: `src/components/product/price.tsx`
- Create: `src/components/product/partner-badge.tsx`
- Create: `src/components/home/hero.tsx`
- Create: `src/components/home/featured-carousel.tsx`
- Create: `src/components/home/category-shortcuts.tsx`
- Create: `src/components/home/affiliate-note.tsx`
- Modify: `src/app/layout.tsx`
- Modify: `src/app/page.tsx`
- Modify: `src/app/globals.css`
- Create: `tests/e2e/home.spec.ts`

**Interfaces:**
- Consumes: `CatalogRepository.getFeatured`, `CatalogRepository.list`.
- Produces: semantic home with links to catalog query parameters and CTAs to product pages.

- [ ] **Step 1: Write the failing home E2E test**

```ts
import { expect, test } from "@playwright/test";

test("home explains the service and exposes keyboard-operable highlights", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: /boas escolhas/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /ver catálogo/i })).toBeVisible();
  await expect(page.getByText(/direcionado à loja parceira/i)).toBeVisible();
  const carousel = page.getByRole("region", { name: /ofertas em destaque/i });
  await expect(carousel.getByRole("button", { name: /próxima oferta/i })).toBeVisible();
  await carousel.getByRole("button", { name: /próxima oferta/i }).focus();
  await page.keyboard.press("Enter");
  await expect(carousel).toHaveAttribute("data-index", "1");
});

test("mobile menu keeps focus and closes with Escape", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: /abrir menu/i }).click();
  await expect(page.getByRole("navigation", { name: /menu móvel/i })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation", { name: /menu móvel/i })).toBeHidden();
});
```

- [ ] **Step 2: Run RED**

Run: `npx playwright install chromium`

Run: `npm run test:e2e -- tests/e2e/home.spec.ts`

Expected: FAIL because the designed home and controls are absent.

- [ ] **Step 3: Implement logo, shell, cards and home**

The SVG logo must have a descriptive `<title>`, use `currentColor`, and pair two connected geometric nodes with an interrupted circular path. The header is sticky with a visible skip link. Embla has previous/next buttons, slide status, dots, touch and arrow keys only while the region is focused; no autoplay. Product cards reserve a 4:3 image box, show partner, title, current/previous price only when valid, discount computed by domain code and CTA “Ver oferta”.

- [ ] **Step 4: Run GREEN at desktop and mobile**

Run: `npm run test:e2e -- tests/e2e/home.spec.ts --project=chromium`

Expected: home and mobile keyboard cases pass.

- [ ] **Step 5: Commit**

```powershell
git add src/app src/components tests/e2e
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: build Orvani storefront home"
```

---

### Task 10: URL-driven catalog, filters and complete states

**Files:**
- Create: `src/app/catalogo/page.tsx`
- Create: `src/app/catalogo/loading.tsx`
- Create: `src/app/catalogo/error.tsx`
- Create: `src/components/catalog/catalog-filters.tsx`
- Create: `src/components/catalog/active-filters.tsx`
- Create: `src/components/catalog/pagination.tsx`
- Create: `src/components/catalog/empty-state.tsx`
- Create: `src/domain/products/search-params.ts`
- Create: `tests/unit/catalog-search-params.test.ts`
- Create: `tests/e2e/catalog.spec.ts`

**Interfaces:**
- Produces: `parseCatalogSearchParams(input): CatalogQuery` with bounded page/price and closed enums.
- Consumes: URL keys `q`, `categoria`, `tipo`, `loja`, `min`, `max`, `ordem`, `pagina`.

- [ ] **Step 1: Write failing URL parsing tests**

```ts
import { describe, expect, it } from "vitest";
import { parseCatalogSearchParams } from "@/domain/products/search-params";

describe("catalog search params", () => {
  it("normalizes valid shareable filters", () => {
    expect(parseCatalogSearchParams({ q: "fone", tipo: "fisico", loja: "amazon", min: "10.00", max: "500.00", ordem: "price_asc", pagina: "2" })).toMatchObject({
      search: "fone", type: "fisico", partner: "amazon", minPrice: 10, maxPrice: 500, sort: "price_asc", page: 2,
    });
  });

  it("falls back safely for invalid enums, ranges and pages", () => {
    expect(parseCatalogSearchParams({ tipo: "script", ordem: "random", min: "-1", max: "NaN", pagina: "999999" })).toMatchObject({ page: 1, pageSize: 12 });
  });
});
```

- [ ] **Step 2: Write failing catalog E2E tests**

```ts
test("search and filters persist in URL and browser history", async ({ page }) => {
  await page.goto("/catalogo");
  await page.getByLabel("Buscar produtos").fill("fone");
  await page.getByLabel("Loja parceira").selectOption("shopee");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page).toHaveURL(/q=fone/);
  await expect(page).toHaveURL(/loja=shopee/);
  await expect(page.getByRole("heading", { name: /fone essencial/i })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/catalogo$/);
});

test("catalog announces no results and offers a reset", async ({ page }) => {
  await page.goto("/catalogo?q=produto-que-nao-existe");
  await expect(page.getByRole("status")).toContainText(/nenhuma oferta encontrada/i);
  await page.getByRole("link", { name: /limpar filtros/i }).click();
  await expect(page.getByRole("list", { name: /produtos/i })).toBeVisible();
});
```

- [ ] **Step 3: Run RED**

Run: `npm test -- tests/unit/catalog-search-params.test.ts`

Run: `npm run test:e2e -- tests/e2e/catalog.spec.ts`

Expected: both suites fail because catalog parsing and page are absent.

- [ ] **Step 4: Implement server catalog and progressive filter form**

Use the URL as state, GET form semantics, canonical parameter order, visible filter labels, removable chips, numeric price inputs with `inputMode="decimal"`, result count, pagination links with `aria-current="page"`, and `loading/error/empty/no-results` messages. Client enhancement may call `router.push`, but submission must work without JavaScript.

- [ ] **Step 5: Run GREEN**

Run: `npm test -- tests/unit/catalog-search-params.test.ts`

Run: `npm run test:e2e -- tests/e2e/catalog.spec.ts`

Expected: URL, history, results and empty-state cases pass.

- [ ] **Step 6: Commit**

```powershell
git add src/app/catalogo src/components/catalog src/domain/products tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add searchable catalog"
```

---

### Task 11: Product detail, related products and sharing

**Files:**
- Create: `src/app/produto/[slug]/page.tsx`
- Create: `src/app/produto/[slug]/loading.tsx`
- Create: `src/app/produto/[slug]/error.tsx`
- Create: `src/components/product/gallery.tsx`
- Create: `src/components/product/share-actions.tsx`
- Create: `src/lib/structured-data.ts`
- Create: `tests/unit/structured-data.test.ts`
- Create: `tests/e2e/product.spec.ts`

**Interfaces:**
- Produces: `buildProductJsonLd(product, siteUrl)` with partner as seller and conditional availability.
- Consumes: `/go/[productId]`; share URL comes from canonical site URL, never affiliate URL.

- [ ] **Step 1: Write failing structured-data tests**

```ts
import { describe, expect, it } from "vitest";
import { buildProductJsonLd } from "@/lib/structured-data";
import { makeProduct } from "../fixtures/products";

describe("product structured data", () => {
  it("identifies the partner as seller without invented ratings", () => {
    const json = buildProductJsonLd(makeProduct({ partner: "amazon", stockStatus: "informativo" }), "https://orvani.example");
    expect(json.offers.seller.name).toBe("Amazon");
    expect(json).not.toHaveProperty("aggregateRating");
    expect(json.offers).not.toHaveProperty("availability");
  });

  it("maps only explicit availability", () => {
    const json = buildProductJsonLd(makeProduct({ stockStatus: "disponivel" }), "https://orvani.example");
    expect(json.offers.availability).toBe("https://schema.org/InStock");
  });
});
```

- [ ] **Step 2: Write failing product E2E test**

```ts
test("product page identifies destination and shares its canonical URL", async ({ page }) => {
  await page.goto("/produto/fone-essencial");
  await expect(page.getByRole("heading", { level: 1, name: /fone essencial/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /ver oferta na shopee/i })).toHaveAttribute("href", /\/go\//);
  await expect(page.getByText(/preço e disponibilidade podem mudar/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /produtos relacionados/i })).toBeVisible();
  await page.getByRole("button", { name: /copiar link/i }).click();
  await expect(page.getByRole("status")).toContainText(/link copiado/i);
});
```

- [ ] **Step 3: Run RED**

Run: `npm test -- tests/unit/structured-data.test.ts`

Run: `npm run test:e2e -- tests/e2e/product.spec.ts`

Expected: both fail because detail, sharing and JSON-LD are absent.

- [ ] **Step 4: Implement product detail and inactive handling**

Render gallery thumbnails as buttons, reserved image sizes and fallback; status plus update `<time>`; current/previous price and server discount; destination CTA and notice adjacent; WhatsApp URL with `encodeURIComponent`; Web Share when available; clipboard fallback with live-region feedback. `getBySlug` returning inactive or absent calls `notFound()` without revealing affiliate data.

- [ ] **Step 5: Run GREEN**

Run: `npm test -- tests/unit/structured-data.test.ts`

Run: `npm run test:e2e -- tests/e2e/product.spec.ts`

Expected: JSON-LD, destination notice, related products and share fallback pass.

- [ ] **Step 6: Commit**

```powershell
git add src/app/produto src/components/product src/lib tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add product detail experience"
```

---

### Task 12: Institutional copy, SEO and strict response headers

**Files:**
- Create: `src/app/sobre/page.tsx`
- Create: `src/app/como-funciona/page.tsx`
- Create: `src/app/transparencia/page.tsx`
- Create: `src/app/privacidade/page.tsx`
- Create: `src/app/termos/page.tsx`
- Create: `src/app/not-found.tsx`
- Create: `src/app/loading.tsx`
- Create: `src/app/error.tsx`
- Create: `src/app/robots.ts`
- Create: `src/app/sitemap.ts`
- Create: `src/app/opengraph-image.tsx`
- Create: `src/lib/metadata.ts`
- Create: `src/security/csp.ts`
- Create: `src/proxy.ts`
- Modify: `next.config.ts`
- Create: `tests/unit/csp.test.ts`
- Create: `tests/e2e/institutional-and-security.spec.ts`

**Interfaces:**
- Produces: `buildCsp(nonce, isDevelopment): string`.
- Produces: canonical, Open Graph, robots and sitemap derived from validated site URL.

- [ ] **Step 1: Write failing CSP tests**

```ts
import { describe, expect, it } from "vitest";
import { buildCsp } from "@/security/csp";

describe("content security policy", () => {
  it("uses a nonce without production unsafe script directives", () => {
    const policy = buildCsp("nonce-value", false);
    expect(policy).toContain("script-src 'self' 'nonce-nonce-value' 'strict-dynamic'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).not.toContain("'unsafe-eval'");
    expect(policy).not.toMatch(/script-src[^;]*'unsafe-inline'/);
  });

  it("allows unsafe-eval only for development React diagnostics", () => {
    expect(buildCsp("nonce-value", true)).toMatch(/script-src[^;]*'unsafe-eval'/);
  });
});
```

- [ ] **Step 2: Write failing security/header E2E test**

```ts
test("main pages expose unique metadata and hardened headers", async ({ page, request }) => {
  await page.goto("/transparencia");
  await expect(page).toHaveTitle(/transparência.*orvani/i);
  await expect(page.getByRole("heading", { level: 1, name: /transparência/i })).toBeVisible();
  const response = await request.get("/");
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  expect(response.headers()["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(response.headers()["permissions-policy"]).toContain("camera=()");
  expect(response.headers()["content-security-policy"]).toContain("frame-ancestors 'none'");
});
```

- [ ] **Step 3: Run RED**

Run: `npm test -- tests/unit/csp.test.ts`

Run: `npm run test:e2e -- tests/e2e/institutional-and-security.spec.ts`

Expected: both suites fail because pages, metadata, proxy and headers are absent.

- [ ] **Step 4: Implement pages, SEO and headers**

Create concise Brazilian Portuguese copy that states the Orvani is not seller, payment processor, stock keeper, delivery provider or warranty provider. `src/proxy.ts` generates a cryptographically random nonce, sets it on request/response, and uses `src/security/csp.ts`. Configure `style-src 'self' 'nonce-{value}'`; add `unsafe-inline` only if a real production browser check demonstrates Next-generated styles cannot render with nonce, and record the exact failure and restriction in README. Add HSTS only when `NODE_ENV === "production"`, plus `nosniff`, `strict-origin-when-cross-origin`, restrictive `Permissions-Policy`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'` and `frame-ancestors 'none'`.

- [ ] **Step 5: Run GREEN**

Run: `npm test -- tests/unit/csp.test.ts`

Run: `npm run test:e2e -- tests/e2e/institutional-and-security.spec.ts`

Expected: metadata, copy and security header assertions pass.

- [ ] **Step 6: Commit**

```powershell
git add src/app src/lib src/security src/proxy.ts next.config.ts tests
git -c user.name="Codex" -c user.email="codex@local" commit -m "feat: add trust pages and security headers"
```

---

### Task 13: Automated accessibility and full essential journeys

**Files:**
- Create: `tests/e2e/accessibility.spec.ts`
- Create: `tests/e2e/redirect.spec.ts`
- Modify: `playwright.config.ts`
- Modify: interactive components found by tests

**Interfaces:**
- Verifies: home, catalog, product and institutional pages with Axe and keyboard.
- Verifies: allowed/blocked/absent redirects without following external locations.

- [ ] **Step 1: Write accessibility and redirect tests**

```ts
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const path of ["/", "/catalogo", "/produto/fone-essencial", "/transparencia"]) {
  test(`has no automatically detectable accessibility violations at ${path}`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}

test("keyboard reaches navigation, filters, cards and footer in order", async ({ page }) => {
  await page.goto("/catalogo");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: /pular para o conteúdo/i })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});
```

```ts
test("redirect endpoint emits only validated temporary destinations", async ({ request }) => {
  const allowed = await request.get("/go/demo-001", { maxRedirects: 0 });
  expect(allowed.status()).toBe(307);
  expect(new URL(allowed.headers().location).protocol).toBe("https:");
  const missing = await request.get("/go/does-not-exist", { maxRedirects: 0 });
  expect(missing.status()).toBe(404);
  expect(missing.headers().location).toBeUndefined();
});
```

- [ ] **Step 2: Run RED or expose concrete accessibility regressions**

Run: `npm run test:e2e -- tests/e2e/accessibility.spec.ts tests/e2e/redirect.spec.ts`

Expected: new tests either fail on missing configuration or identify exact WCAG/flow defects; record each failure before editing.

- [ ] **Step 3: Make the smallest fixes required by failing evidence**

Fix only named violations: accessible names, heading order, landmark uniqueness, focus targets, contrast tokens, live-region behavior or invalid ARIA. Add a regression assertion for every bug not already isolated by Axe.

- [ ] **Step 4: Run GREEN across all E2E projects**

Run: `npm run test:e2e`

Expected: home, catalog, product, institutional, redirect and accessibility specs all pass in configured desktop and mobile Chromium projects.

- [ ] **Step 5: Commit**

```powershell
git add tests/e2e playwright.config.ts src
git -c user.name="Codex" -c user.email="codex@local" commit -m "test: verify essential accessible journeys"
```

---

### Task 14: Configuration templates, operations guide and threat model

**Files:**
- Create: `.env.example`
- Create: `docs/catalog-template.csv`
- Create: `README.md`
- Create: `.gitignore`
- Create: `tests/unit/documentation-contract.test.ts`

**Interfaces:**
- Documents: local demo, Supabase, migrations, Google service account, private sharing, allowlists, sync, cron, retention, credential rotation, deployment options and legal review.

- [ ] **Step 1: Write the failing documentation contract test**

```ts
import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("operational documentation", () => {
  it("creates the operational files", () => {
    expect(existsSync("README.md")).toBe(true);
    expect(existsSync(".env.example")).toBe(true);
    expect(existsSync("docs/catalog-template.csv")).toBe(true);
  });

  it.each([
    "Supabase",
    "Google Sheets",
    "AFFILIATE_ALLOWED_HOSTS",
    "sync:catalog",
    "retenção",
    "rotação",
    "threat model",
    "revisão jurídica",
  ])("documents %s", (term) => {
    const readme = readFileSync("README.md", "utf8");
    expect(readme.toLocaleLowerCase("pt-BR")).toContain(term.toLocaleLowerCase("pt-BR"));
  });

  it("lists required variables without example secrets", () => {
    const env = readFileSync(".env.example", "utf8");
    expect(env).toContain("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY=");
    expect(env).toContain("SUPABASE_SECRET_KEY=");
    expect(env).toContain("CATALOG_SYNC_SECRET=");
    expect(env).not.toMatch(/sk[-_][A-Za-z0-9]/);
    expect(env).not.toMatch(/BEGIN PRIVATE KEY/);
  });
});
```

- [ ] **Step 2: Run RED**

Run: `npm test -- tests/unit/documentation-contract.test.ts`

Expected: FAIL because README and environment template are absent.

- [ ] **Step 3: Create exact environment template and CSV**

`.env.example` lists empty values for:

```dotenv
NEXT_PUBLIC_SITE_URL=
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
GOOGLE_SHEETS_SPREADSHEET_ID=
GOOGLE_SHEETS_RANGE=
GOOGLE_SERVICE_ACCOUNT_EMAIL=
GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY=
CATALOG_SYNC_SECRET=
AFFILIATE_ALLOWED_HOSTS=
PRODUCT_IMAGE_ALLOWED_HOSTS=
```

Each name gets a preceding Portuguese comment explaining scope and whether it is server-only. The CSV has the exact 19-column header and one `demo-template-001` row with JSON arrays quoted per CSV, BRL, HTTPS placeholder image host and an official marketplace home URL without affiliate identifiers.

- [ ] **Step 4: Write the complete Portuguese README**

Include Node prerequisite, install/dev/test commands, demo behavior, Supabase project creation and migration command, least-privilege/RLS explanation, Google API enablement and viewer sharing, private-key newline handling, allowlist examples with confirmation warning, CLI and POST cron request, cache behavior, retention SQL, all credential rotation procedures, CSP/style exception status, threat model, residual risks, dependency audit interpretation, deploy options without performing deploy, and mandatory professional legal review.

- [ ] **Step 5: Run GREEN**

Run: `npm test -- tests/unit/documentation-contract.test.ts`

Expected: documentation contract passes.

- [ ] **Step 6: Commit**

```powershell
git add .env.example .gitignore README.md docs/catalog-template.csv tests/unit/documentation-contract.test.ts
git -c user.name="Codex" -c user.email="codex@local" commit -m "docs: add secure operation guide"
```

---

### Task 15: Final verification, dependency audit and diff review

**Files:**
- Modify: only files implicated by fresh verification failures.
- Create: `docs/verification-report.md`

**Interfaces:**
- Produces: evidence with command, timestamp, exit status and summary; no claimed Lighthouse score unless measured.

- [ ] **Step 1: Run formatting-independent repository checks**

Run: `git diff --check HEAD`

Expected: exit `0`, no whitespace errors.

Run: `git status --short`

Expected: only intended report changes before the final report commit.

- [ ] **Step 2: Run lint and type verification fresh**

Run: `npm run lint`

Expected: exit `0`, no warnings promoted by project rules.

Run: `npm run typecheck`

Expected: exit `0`.

- [ ] **Step 3: Run all unit and integration tests fresh**

Run: `npm test`

Expected: exit `0`; record exact test-file and test counts.

- [ ] **Step 4: Run production build fresh**

Run with safe demo/build variables only if build-time site URL is required: `npm run build`

Expected: exit `0`; no credential value in output or client chunks.

- [ ] **Step 5: Run all E2E and accessibility tests fresh**

Run: `npm run test:e2e`

Expected: exit `0`; record exact test count and browser projects.

- [ ] **Step 6: Audit dependencies without blind upgrades**

Run: `npm audit --omit=dev`

Run: `npm audit`

Expected: capture production and full findings separately. For every finding, record package, severity, reachable usage, available fix and decision. Apply only compatible fixes, rerun all affected verification, and leave any residual advisory explicitly documented.

- [ ] **Step 7: Inspect bundle and repository for secret/client leaks**

Run: `rg -n "SUPABASE_SECRET_KEY|GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY|CATALOG_SYNC_SECRET" src --glob "*.tsx" --glob "*.ts"`

Expected: references exist only in server-only env/adapters/routes/scripts; no file containing `"use client"` imports them.

Run: `rg -n "dangerouslySetInnerHTML" src`

Expected: only the audited JSON-LD script serializer may use it; its value comes exclusively from `JSON.stringify` of validated server data with `<` escaped as `\u003c`.

- [ ] **Step 8: Review requirements and final diff**

Compare every section of `docs/superpowers/specs/2026-08-11-orvani-design.md` with implemented files and tests. Inspect `git diff --stat` and `git diff` for accidental changes, generated secrets, copied marketplace assets, debug output and unrelated edits.

- [ ] **Step 9: Write and commit the verification report**

`docs/verification-report.md` must contain environment versions, every command above, actual exit codes/counts, audit analysis, unmeasured Lighthouse status, residual risks, credentials still required and a statement that no deployment occurred.

```powershell
git add docs/verification-report.md
git -c user.name="Codex" -c user.email="codex@local" commit -m "docs: record Orvani verification evidence"
```

- [ ] **Step 10: Run a final post-commit status check**

Run: `git status --short --branch`

Expected: clean branch with no untracked secrets or unintended files.
