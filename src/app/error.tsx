"use client";

export default function RootError({ reset }: { reset: () => void }) {
  return (
    <div className="route-error" role="alert">
      <span>Não foi possível concluir.</span>
      <h1>Algo saiu do caminho.</h1>
      <p>Tente novamente em instantes. Nenhum detalhe interno foi exposto.</p>
      <button className="button" type="button" onClick={reset}>
        Tentar novamente
      </button>
    </div>
  );
}
