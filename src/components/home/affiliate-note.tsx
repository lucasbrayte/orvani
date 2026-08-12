import Link from "next/link";

export function AffiliateNote() {
  return (
    <aside className="affiliate-note" aria-labelledby="affiliate-note-title">
      <div className="affiliate-note__mark" aria-hidden="true">↗</div>
      <div>
        <span className="section-kicker">Compra transparente</span>
        <h2 id="affiliate-note-title">Você escolhe aqui. A compra acontece na loja.</h2>
      </div>
      <p>Ao selecionar uma oferta, você será direcionado à loja parceira. A Orvani não vende, não cobra e não realiza a entrega.</p>
      <Link className="text-link text-link--light" href="/transparencia">Entenda nossa transparência</Link>
    </aside>
  );
}
