import type { PublicProduct } from "@/domain/products/model";
import { partnerName } from "@/components/product/partner-badge";

export type ProductJsonLd = {
  "@context": "https://schema.org";
  "@type": "Product";
  name: string;
  description: string;
  image: string[];
  category: string;
  offers: {
    "@type": "Offer";
    priceCurrency: "BRL";
    price: string;
    url: string;
    seller: { "@type": "Organization"; name: string };
    availability?: "https://schema.org/InStock" | "https://schema.org/OutOfStock";
  };
};

export function buildProductJsonLd(product: PublicProduct, siteUrl: string): ProductJsonLd {
  const availability =
    product.stockStatus === "disponivel"
      ? "https://schema.org/InStock"
      : product.stockStatus === "indisponivel"
        ? "https://schema.org/OutOfStock"
        : undefined;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.shortDescription,
    image: [product.primaryImage, ...product.images].map((image) => new URL(image, siteUrl).href),
    category: product.category,
    offers: {
      "@type": "Offer",
      priceCurrency: "BRL",
      price: product.currentPrice.toFixed(2),
      url: new URL(`/go/${encodeURIComponent(product.id)}`, siteUrl).href,
      seller: { "@type": "Organization", name: partnerName(product.partner) },
      ...(availability ? { availability } : {}),
    },
  };
}

export function serializeJsonLd(value: unknown): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}
