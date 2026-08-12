import Link from "next/link";

import { partnerName } from "@/components/product/partner-badge";
import type { CatalogQuery } from "@/domain/products/query";
import { catalogHref } from "@/domain/products/search-params";
import { formatCurrency } from "@/lib/format";

export function ActiveFilters({ query }: { query: CatalogQuery }) {
  const filters = [
    query.search ? { label: `Busca: ${query.search}`, remove: { search: undefined } } : null,
    query.category ? { label: query.category, remove: { category: undefined } } : null,
    query.type ? { label: query.type === "fisico" ? "Físico" : "Digital", remove: { type: undefined } } : null,
    query.partner ? { label: partnerName(query.partner), remove: { partner: undefined } } : null,
    query.minPrice !== undefined ? { label: `A partir de ${formatCurrency(query.minPrice)}`, remove: { minPrice: undefined } } : null,
    query.maxPrice !== undefined ? { label: `Até ${formatCurrency(query.maxPrice)}`, remove: { maxPrice: undefined } } : null,
  ].filter(Boolean) as { label: string; remove: Partial<CatalogQuery> }[];

  if (filters.length === 0) return null;
  return (
    <div className="active-filters" aria-label="Filtros ativos">
      {filters.map((filter) => (
        <Link key={filter.label} href={catalogHref(query, { ...filter.remove, page: 1 })} aria-label={`Remover filtro ${filter.label}`}>
          {filter.label} <span aria-hidden="true">×</span>
        </Link>
      ))}
      <Link className="active-filters__clear" href="/catalogo">Limpar tudo</Link>
    </div>
  );
}
