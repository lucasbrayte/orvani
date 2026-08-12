import type { Product } from "@/domain/products/model";

export function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: "product-1",
    name: "Produto Ilustrativo",
    slug: "produto-ilustrativo",
    category: "Casa",
    type: "fisico",
    shortDescription: "Uma descrição curta para testes.",
    description: "Uma descrição completa e inteiramente fictícia para testes.",
    currentPrice: 99.9,
    previousPrice: null,
    currency: "BRL",
    primaryImage: "/images/product-fallback.svg",
    images: [],
    partner: "amazon",
    affiliateUrl: "https://amazon.com.br",
    featured: false,
    active: true,
    stockStatus: "informativo",
    tags: [],
    updatedAt: "2026-08-11T12:00:00.000Z",
    ...overrides,
  };
}
