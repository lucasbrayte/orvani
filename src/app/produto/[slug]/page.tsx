import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { getCatalogRepository } from "@/catalog/get-repository";
import { ProductGallery } from "@/components/product/gallery";
import { partnerName, PartnerBadge } from "@/components/product/partner-badge";
import { Price } from "@/components/product/price";
import { ProductGrid } from "@/components/product/product-grid";
import { ShareActions } from "@/components/product/share-actions";
import { getRuntimeEnv } from "@/config/env";
import { calculateDiscount } from "@/domain/products/normalizers";
import { formatDate } from "@/lib/format";
import { buildProductJsonLd, serializeJsonLd } from "@/lib/structured-data";

type ProductPageProps = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  const product = await getCatalogRepository().getBySlug((await params).slug);
  if (!product) return { title: "Oferta indisponível", robots: { index: false, follow: false } };
  const siteUrl = getRuntimeEnv().siteUrl;
  return {
    title: product.name,
    description: product.shortDescription,
    alternates: { canonical: new URL(`/produto/${product.slug}`, siteUrl).href },
    openGraph: {
      title: product.name,
      description: product.shortDescription,
      url: new URL(`/produto/${product.slug}`, siteUrl).href,
      images: [{ url: new URL(product.primaryImage, siteUrl).href, alt: product.name }],
    },
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  const repository = getCatalogRepository();
  const product = await repository.getBySlug(slug);
  if (!product) notFound();
  const related = await repository.getRelated(product, 4);
  const siteUrl = getRuntimeEnv().siteUrl;
  const canonical = new URL(`/produto/${product.slug}`, siteUrl).href;
  const discount = calculateDiscount(product.currentPrice, product.previousPrice);
  const jsonLd = buildProductJsonLd(product, siteUrl);
  const images = [product.primaryImage, ...product.images];

  return (
    <div className="product-page">
      <nav className="breadcrumbs" aria-label="Navegação estrutural">
        <Link href="/">Início</Link>
        <span>/</span>
        <Link href="/catalogo">Catálogo</Link>
        <span>/</span>
        <span aria-current="page">{product.name}</span>
      </nav>
      <article className="product-detail">
        <ProductGallery name={product.name} images={images} />
        <div className="product-detail__content">
          <div className="product-detail__labels">
            <PartnerBadge partner={product.partner} />
            <span>{product.type === "digital" ? "Produto digital" : "Produto físico"}</span>
          </div>
          <h1>{product.name}</h1>
          <p className="product-detail__lead">{product.shortDescription}</p>
          <div className="product-detail__price">
            <Price current={product.currentPrice} previous={product.previousPrice} />
            {discount !== null && <span>Economia informativa de {discount}%</span>}
          </div>
          <p className="product-detail__description">{product.description}</p>
          <dl className="product-facts">
            <div>
              <dt>Loja parceira</dt>
              <dd>{partnerName(product.partner)}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>
                {product.stockStatus === "disponivel"
                  ? "Marcado como disponível"
                  : product.stockStatus === "indisponivel"
                    ? "Marcado como indisponível"
                    : "Consulte na loja"}
              </dd>
            </div>
            <div>
              <dt>Atualizado</dt>
              <dd>
                <time dateTime={product.updatedAt}>{formatDate(product.updatedAt)}</time>
              </dd>
            </div>
          </dl>
          <Link className="button product-cta" href={`/go/${product.id}`} prefetch={false}>
            Ver oferta na {partnerName(product.partner)} <span aria-hidden="true">↗</span>
          </Link>
          <p className="redirect-notice">
            Você será direcionado à loja parceira. Preço e disponibilidade podem mudar.
          </p>
          <ShareActions title={product.name} url={canonical} />
        </div>
      </article>
      {related.length > 0 && (
        <section className="related-products" aria-labelledby="related-title">
          <div className="section-heading">
            <div>
              <span className="section-kicker">Continue explorando</span>
              <h2 id="related-title">Produtos relacionados</h2>
            </div>
            <Link
              className="text-link"
              href={`/catalogo?categoria=${encodeURIComponent(product.category)}`}
            >
              Ver categoria →
            </Link>
          </div>
          <ProductGrid products={related} label="Produtos relacionados" />
        </section>
      )}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(jsonLd) }}
      />
    </div>
  );
}
