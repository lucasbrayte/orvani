"use client";

export default function CatalogError({ reset }: { reset: () => void }) {
  return (
    <div className="route-error" role="alert">
      <span>Algo saiu do caminho.</span>
      <h1>Não foi possível carregar o catálogo.</h1>
      <p>Tente novamente. O último catálogo válido continua preservado.</p>
      <button className="button" type="button" onClick={reset}>Tentar novamente</button>
    </div>
  );
}
