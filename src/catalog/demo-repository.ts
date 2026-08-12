import type { PublicProduct } from "@/domain/products/model";
import { toPublicProduct } from "@/domain/products/model";
import { queryProducts, type CatalogQuery } from "@/domain/products/query";

import { demoProducts } from "./demo-data";
import type { CatalogRepository } from "./repository";

export class DemoCatalogRepository implements CatalogRepository {
  private readonly products = demoProducts.map(toPublicProduct);

  async list(query: CatalogQuery) {
    return queryProducts(this.products, query);
  }

  async getBySlug(slug: string): Promise<PublicProduct | null> {
    return this.products.find((product) => product.active && product.slug === slug) ?? null;
  }

  async getFeatured(limit: number): Promise<PublicProduct[]> {
    return this.products.filter((product) => product.active && product.featured).slice(0, limit);
  }

  async getRelated(product: PublicProduct, limit: number): Promise<PublicProduct[]> {
    return this.products
      .filter(
        (candidate) =>
          candidate.active &&
          candidate.id !== product.id &&
          (candidate.category === product.category ||
            candidate.tags.some((tag) => product.tags.includes(tag))),
      )
      .slice(0, limit);
  }
}
