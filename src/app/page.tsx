import Link from "next/link";

import { getCatalogRepository } from "@/catalog/get-repository";
import { AffiliateNote } from "@/components/home/affiliate-note";
import { CategoryShortcuts } from "@/components/home/category-shortcuts";
import { FeaturedCarousel } from "@/components/home/featured-carousel";
import { Hero } from "@/components/home/hero";
import { ProductGrid } from "@/components/product/product-grid";

export default async function HomePage() {
  const repository = getCatalogRepository();
  const [featured, newest, offers] = await Promise.all([
    repository.getFeatured(6),
    repository.list({ sort: "recent", page: 1, pageSize: 4 }),
    repository.list({ sort: "discount_desc", page: 1, pageSize: 4 }),
  ]);

  return (
    <div className="home-page">
      <Hero />
      <CategoryShortcuts />
      <FeaturedCarousel products={featured} />
      <section className="content-section" aria-labelledby="new-title">
        <div className="section-heading">
          <div><span className="section-kicker">Chegaram agora</span><h2 id="new-title">Novidades no catálogo</h2></div>
          <Link className="text-link" href="/catalogo?ordem=recent">Ver novidades <span aria-hidden="true">→</span></Link>
        </div>
        <ProductGrid products={newest.items} label="Novidades" />
      </section>
      <AffiliateNote />
      <section className="content-section" aria-labelledby="selected-title">
        <div className="section-heading">
          <div><span className="section-kicker section-kicker--offer">Boa oportunidade</span><h2 id="selected-title">Ofertas selecionadas</h2></div>
          <Link className="text-link" href="/catalogo?ordem=discount_desc">Ver todas <span aria-hidden="true">→</span></Link>
        </div>
        <ProductGrid products={offers.items} label="Ofertas selecionadas" />
      </section>
    </div>
  );
}
