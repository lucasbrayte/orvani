import { getCatalogRepository } from "@/catalog/get-repository";
import { ActiveFilters } from "@/components/catalog/active-filters";
import { CatalogEmptyState } from "@/components/catalog/empty-state";
import { CatalogFilters } from "@/components/catalog/catalog-filters";
import { Pagination } from "@/components/catalog/pagination";
import { ProductGrid } from "@/components/product/product-grid";
import { parseCatalogSearchParams, type RawSearchParams } from "@/domain/products/search-params";
import { buildPageMetadata } from "@/lib/page-metadata";

export const metadata = buildPageMetadata({
  title: "Catálogo",
  description: "Pesquise e filtre produtos físicos e digitais selecionados pela Orvani.",
  path: "/catalogo",
});

export default async function CatalogPage({ searchParams }: { searchParams: Promise<RawSearchParams> }) {
  const query = parseCatalogSearchParams(await searchParams);
  const repository = getCatalogRepository();
  const [result, all] = await Promise.all([
    repository.list(query),
    repository.list({ page: 1, pageSize: 48, sort: "relevance" }),
  ]);
  const categories = [...new Set(all.items.map((product) => product.category))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  const filtered = Boolean(query.search || query.category || query.type || query.partner || query.minPrice || query.maxPrice);

  return (
    <div className="catalog-page">
      <header className="catalog-hero">
        <span className="section-kicker">Catálogo Orvani</span>
        <h1>Escolhas para diferentes momentos.</h1>
        <p>Pesquise, compare e abra a oferta diretamente na loja parceira.</p>
      </header>
      <div className="catalog-layout">
        <CatalogFilters query={query} categories={categories} />
        <section className="catalog-results" aria-labelledby="results-title">
          <div className="catalog-results__heading">
            <div><span>{result.total} {result.total === 1 ? "resultado" : "resultados"}</span><h2 id="results-title">Produtos encontrados</h2></div>
          </div>
          <ActiveFilters query={query} />
          {result.items.length > 0 ? (
            <><ProductGrid products={result.items} label="Produtos" /><Pagination result={result} query={query} /></>
          ) : <CatalogEmptyState filtered={filtered} />}
        </section>
      </div>
    </div>
  );
}
