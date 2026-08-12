import { partners, productTypes } from "./model";
import { parsePrice } from "./normalizers";
import type { CatalogQuery, CatalogSort } from "./query";

export type RawSearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return (Array.isArray(value) ? value[0] : value)?.trim() || undefined;
}

function price(value: string | undefined): number | undefined {
  if (!value) return undefined;
  try {
    return parsePrice(value) ?? undefined;
  } catch {
    return undefined;
  }
}

function category(value: string | undefined): string | undefined {
  return value && /^[\p{L}\p{N} .&/-]{1,80}$/u.test(value) ? value : undefined;
}

const sorts: CatalogSort[] = ["relevance", "price_asc", "discount_desc", "recent"];

export function parseCatalogSearchParams(input: RawSearchParams): CatalogQuery {
  const type = first(input.tipo);
  const partner = first(input.loja);
  const sort = first(input.ordem);
  const rawPage = first(input.pagina);
  const parsedPage = rawPage && /^\d{1,3}$/.test(rawPage) ? Number(rawPage) : 1;
  let minPrice = price(first(input.min));
  let maxPrice = price(first(input.max));
  if (minPrice !== undefined && maxPrice !== undefined && minPrice > maxPrice) {
    minPrice = undefined;
    maxPrice = undefined;
  }

  const search = first(input.q)?.slice(0, 120);
  return {
    ...(search ? { search } : {}),
    ...(category(first(input.categoria)) ? { category: category(first(input.categoria)) } : {}),
    ...(productTypes.includes(type as (typeof productTypes)[number])
      ? { type: type as (typeof productTypes)[number] }
      : {}),
    ...(partners.includes(partner as (typeof partners)[number])
      ? { partner: partner as (typeof partners)[number] }
      : {}),
    ...(minPrice !== undefined ? { minPrice } : {}),
    ...(maxPrice !== undefined ? { maxPrice } : {}),
    sort: sorts.includes(sort as CatalogSort) ? (sort as CatalogSort) : "relevance",
    page: parsedPage >= 1 ? parsedPage : 1,
    pageSize: 12,
  };
}

export function catalogQueryParams(
  query: CatalogQuery,
  overrides: Partial<CatalogQuery> = {},
): URLSearchParams {
  const value = { ...query, ...overrides };
  const params = new URLSearchParams();
  if (value.search) params.set("q", value.search);
  if (value.category) params.set("categoria", value.category);
  if (value.type) params.set("tipo", value.type);
  if (value.partner) params.set("loja", value.partner);
  if (value.minPrice !== undefined) params.set("min", value.minPrice.toFixed(2));
  if (value.maxPrice !== undefined) params.set("max", value.maxPrice.toFixed(2));
  if (value.sort && value.sort !== "relevance") params.set("ordem", value.sort);
  if (value.page > 1) params.set("pagina", String(value.page));
  return params;
}

export function catalogHref(query: CatalogQuery, overrides: Partial<CatalogQuery> = {}): string {
  const params = catalogQueryParams(query, overrides);
  const value = params.toString();
  return value ? `/catalogo?${value}` : "/catalogo";
}
