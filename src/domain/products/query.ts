import type { Partner, ProductType, PublicProduct } from "./model";
import { calculateDiscount } from "./normalizers";

export type CatalogSort = "relevance" | "price_asc" | "discount_desc" | "recent";

export type CatalogQuery = {
  search?: string;
  category?: string;
  type?: ProductType;
  partner?: Partner;
  minPrice?: number;
  maxPrice?: number;
  sort?: CatalogSort;
  page: number;
  pageSize: number;
};

export type CatalogPage = {
  items: PublicProduct[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

function searchable(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
}

function relevance(product: PublicProduct, search: string): number {
  const term = searchable(search);
  const name = searchable(product.name);
  const tags = searchable(product.tags.join(" "));
  const descriptions = searchable(`${product.shortDescription} ${product.description}`);
  return (name.includes(term) ? 3 : 0) + (tags.includes(term) ? 2 : 0) + (descriptions.includes(term) ? 1 : 0);
}

export function queryProducts(products: readonly PublicProduct[], query: CatalogQuery): CatalogPage {
  const search = query.search?.trim() ?? "";
  const pageSize = Math.min(48, Math.max(1, Math.trunc(query.pageSize || 12)));
  const filtered = products.filter((product) => {
    if (!product.active) return false;
    if (search && relevance(product, search) === 0) return false;
    if (query.category && product.category !== query.category) return false;
    if (query.type && product.type !== query.type) return false;
    if (query.partner && product.partner !== query.partner) return false;
    if (query.minPrice !== undefined && product.currentPrice < query.minPrice) return false;
    if (query.maxPrice !== undefined && product.currentPrice > query.maxPrice) return false;
    return true;
  });

  const indexed = filtered.map((product, index) => ({ product, index }));
  indexed.sort((left, right) => {
    switch (query.sort ?? "relevance") {
      case "price_asc":
        return left.product.currentPrice - right.product.currentPrice || left.index - right.index;
      case "discount_desc":
        return (
          (calculateDiscount(right.product.currentPrice, right.product.previousPrice) ?? 0) -
            (calculateDiscount(left.product.currentPrice, left.product.previousPrice) ?? 0) ||
          left.index - right.index
        );
      case "recent":
        return (
          Date.parse(right.product.updatedAt) - Date.parse(left.product.updatedAt) || left.index - right.index
        );
      case "relevance":
      default:
        return (search ? relevance(right.product, search) - relevance(left.product, search) : 0) || left.index - right.index;
    }
  });

  const total = indexed.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const page = Math.min(totalPages, Math.max(1, Math.trunc(query.page || 1)));
  const start = (page - 1) * pageSize;

  return {
    items: indexed.slice(start, start + pageSize).map(({ product }) => product),
    page,
    pageSize,
    total,
    totalPages,
  };
}
