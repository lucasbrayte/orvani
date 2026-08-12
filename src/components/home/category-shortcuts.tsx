import Link from "next/link";

const categories = [
  ["Eletrônicos", "01", "Tecnologia útil"],
  ["Moda", "02", "Para o seu estilo"],
  ["Jogos", "03", "Diversão em foco"],
  ["Aplicativos", "04", "Soluções digitais"],
  ["Casa", "05", "Bem-estar diário"],
  ["Assinaturas", "06", "Serviços recorrentes"],
] as const;

export function CategoryShortcuts() {
  return (
    <section className="content-section category-section" aria-labelledby="category-title">
      <div className="section-heading">
        <div><span className="section-kicker">Explore</span><h2 id="category-title">Encontre seu próximo favorito</h2></div>
        <Link className="text-link" href="/catalogo">Todas as categorias <span aria-hidden="true">→</span></Link>
      </div>
      <div className="category-grid">
        {categories.map(([name, number, description]) => (
          <Link key={name} href={`/catalogo?categoria=${encodeURIComponent(name)}`}>
            <span className="category-grid__number">{number}</span>
            <span><strong>{name}</strong><small>{description}</small></span>
            <span className="category-grid__arrow" aria-hidden="true">↗</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
