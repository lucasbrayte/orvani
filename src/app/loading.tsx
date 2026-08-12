export default function GlobalLoading() {
  return (
    <div className="route-loading" aria-busy="true" aria-label="Carregando página">
      <div className="skeleton skeleton--heading" />
      <div className="skeleton skeleton--page" />
      <span className="sr-only">Carregando…</span>
    </div>
  );
}
