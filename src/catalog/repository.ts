import type { PublicProduct } from "@/domain/products/model";
import type { CatalogPage, CatalogQuery } from "@/domain/products/query";

export interface CatalogRepository {
  list(query: CatalogQuery): Promise<CatalogPage>;
  getBySlug(slug: string): Promise<PublicProduct | null>;
  getFeatured(limit: number): Promise<PublicProduct[]>;
  getRelated(product: PublicProduct, limit: number): Promise<PublicProduct[]>;
}
