"use client";

export default function ProductError({ reset }: { reset: () => void }) {
  return <div className="route-error" role="alert"><span>Oferta temporariamente indisponível</span><h1>Não foi possível carregar este produto.</h1><p>Tente novamente ou retorne ao catálogo para continuar explorando.</p><button className="button" type="button" onClick={reset}>Tentar novamente</button></div>;
}
