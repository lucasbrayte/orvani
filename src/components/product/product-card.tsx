import Link from "next/link";

import type { PublicProduct } from "@/domain/products/model";

import { PartnerBadge } from "./partner-badge";
import { Price } from "./price";
import { ProductImage } from "./product-image";

export function ProductCard({ product, priority = false }: { product: PublicProduct; priority?: boolean }) {
  return (
    <article className="product-card">
      <Link className="product-card__image" href={`/produto/${product.slug}`} tabIndex={-1} aria-hidden="true">
        <ProductImage src={product.primaryImage} alt="" priority={priority} />
        <span className="product-card__type">{product.type === "digital" ? "Digital" : "Físico"}</span>
      </Link>
      <div className="product-card__body">
        <PartnerBadge partner={product.partner} />
        <h3>
          <Link href={`/produto/${product.slug}`}>{product.name}</Link>
        </h3>
        <p>{product.shortDescription}</p>
        <Price current={product.currentPrice} previous={product.previousPrice} />
        <Link className="card-action" href={`/produto/${product.slug}`}>
          Ver oferta <span aria-hidden="true">↗</span>
        </Link>
      </div>
    </article>
  );
}
