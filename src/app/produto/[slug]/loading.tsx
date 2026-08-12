export default function ProductLoading() {
  return <div className="product-page" role="status" aria-live="polite" aria-busy="true"><span className="sr-only">Carregando produto…</span><div className="product-detail"><div className="skeleton skeleton--gallery" /><div><div className="skeleton skeleton--title" /><div className="skeleton skeleton--copy" /></div></div></div>;
}
