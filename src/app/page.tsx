import { siteIdentity } from "@/lib/site";

export default function HomePage() {
  return (
    <section className="placeholder-page">
      <p className="eyebrow">Curadoria independente</p>
      <h1>{siteIdentity.slogan}</h1>
      <p>Uma vitrine simples para descobrir ofertas em lojas parceiras.</p>
    </section>
  );
}
