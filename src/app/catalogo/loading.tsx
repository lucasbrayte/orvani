export default function CatalogLoading() {
  return (
    <div className="catalog-page catalog-loading" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">Carregando catálogo…</span>
      <div className="skeleton skeleton--title" />
      <div className="catalog-layout">
        <div className="skeleton skeleton--filters" />
        <div className="product-grid">{Array.from({ length: 6 }, (_, index) => <div className="skeleton skeleton--card" key={index} />)}</div>
      </div>
    </div>
  );
}
