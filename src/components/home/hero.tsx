import Link from "next/link";

export function Hero() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero__content">
        <span className="hero__eyebrow"><i /> Curadoria para a vida real</span>
        <h1 id="hero-title">Boas escolhas em um só lugar.</h1>
        <p>Descubra produtos físicos e digitais com uma seleção simples, versátil e transparente.</p>
        <div className="hero__actions">
          <Link className="button button--light" href="/catalogo">
            Ver catálogo <span aria-hidden="true">↗</span>
          </Link>
          <Link className="text-link text-link--light" href="/como-funciona">
            Como funciona
          </Link>
        </div>
      </div>
      <div className="hero__visual" aria-hidden="true">
        <div className="orbital orbital--one" />
        <div className="orbital orbital--two" />
        <div className="hero__ticket hero__ticket--top">
          <span>Seleção Orvani</span>
          <strong>Escolha com clareza</strong>
        </div>
        <div className="hero__ticket hero__ticket--bottom">
          <span className="hero__ticket-dot" />
          <div><strong>Várias categorias</strong><span>um só catálogo</span></div>
        </div>
      </div>
    </section>
  );
}
