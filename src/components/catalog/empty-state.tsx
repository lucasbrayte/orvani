import Link from "next/link";

export function CatalogEmptyState({ filtered }: { filtered: boolean }) {
  return (
    <div className="catalog-empty" role="status">
      <span aria-hidden="true">⌕</span>
      <h2>{filtered ? "Nenhuma oferta encontrada" : "Catálogo em preparação"}</h2>
      <p>{filtered ? "Tente ampliar a busca ou remover um dos filtros." : "Novas escolhas aparecerão aqui em breve."}</p>
      {filtered && <Link className="button" href="/catalogo">Limpar filtros</Link>}
    </div>
  );
}
