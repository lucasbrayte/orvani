import Link from "next/link";

import type { CatalogPage, CatalogQuery } from "@/domain/products/query";
import { catalogHref } from "@/domain/products/search-params";

export function Pagination({ result, query }: { result: CatalogPage; query: CatalogQuery }) {
  if (result.totalPages <= 1) return null;
  const pages = Array.from({ length: result.totalPages }, (_, index) => index + 1).filter(
    (page) => page === 1 || page === result.totalPages || Math.abs(page - result.page) <= 1,
  );

  return (
    <nav className="pagination" aria-label="Paginação do catálogo">
      {result.page > 1 && <Link href={catalogHref(query, { page: result.page - 1 })}>← Anterior</Link>}
      <div>
        {pages.map((page, index) => (
          <span key={page}>
            {index > 0 && page - pages[index - 1] > 1 && <i aria-hidden="true">…</i>}
            <Link href={catalogHref(query, { page })} aria-current={page === result.page ? "page" : undefined}>{page}</Link>
          </span>
        ))}
      </div>
      {result.page < result.totalPages && <Link href={catalogHref(query, { page: result.page + 1 })}>Próxima →</Link>}
    </nav>
  );
}
