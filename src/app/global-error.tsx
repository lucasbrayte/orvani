"use client";

export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <html lang="pt-BR">
      <body>
        <main className="route-error" role="alert">
          <span>Erro inesperado</span>
          <h1>Não foi possível abrir a Orvani.</h1>
          <p>Tente novamente. Se o problema continuar, aguarde alguns instantes.</p>
          <button type="button" onClick={reset}>
            Tentar novamente
          </button>
        </main>
      </body>
    </html>
  );
}
