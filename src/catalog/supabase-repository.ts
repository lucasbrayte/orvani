import type { SupabaseClient } from "@supabase/supabase-js";

import type { PublicProduct } from "@/domain/products/model";
import { publicProductSchema } from "@/domain/products/schema";
import { queryProducts, type CatalogQuery } from "@/domain/products/query";
import { createSupabaseReadClient } from "@/integrations/supabase/client";

import type { CatalogRepository } from "./repository";

const PUBLIC_COLUMNS =
  "id,name,slug,category,type,short_description,description,current_price,previous_price,currency,primary_image,images,partner,featured,active,stock_status,tags,updated_at";

export type DatabaseProductRow = {
  id: string;
  name: string;
  slug: string;
  category: string;
  type: string;
  short_description: string;
  description: string;
  current_price: string | number;
  previous_price: string | number | null;
  currency: string;
  primary_image: string;
  images: string[];
  partner: string;
  featured: boolean;
  active: boolean;
  stock_status: string;
  tags: string[];
  updated_at: string;
};

export function mapProductRow(row: DatabaseProductRow): PublicProduct {
  return publicProductSchema.parse({
    id: row.id,
    name: row.name,
    slug: row.slug,
    category: row.category,
    type: row.type,
    shortDescription: row.short_description,
    description: row.description,
    currentPrice: Number(row.current_price),
    previousPrice: row.previous_price === null ? null : Number(row.previous_price),
    currency: row.currency,
    primaryImage: row.primary_image,
    images: row.images,
    partner: row.partner,
    featured: row.featured,
    active: row.active,
    stockStatus: row.stock_status,
    tags: row.tags,
    updatedAt: row.updated_at,
  });
}

export class SupabaseCatalogRepository implements CatalogRepository {
  constructor(private readonly client: SupabaseClient = createSupabaseReadClient()) {}

  private async allActive(): Promise<PublicProduct[]> {
    const { data, error } = await this.client
      .from("products")
      .select(PUBLIC_COLUMNS)
      .eq("active", true);
    if (error) throw new Error("Não foi possível consultar o catálogo.");
    return ((data ?? []) as unknown as DatabaseProductRow[]).map(mapProductRow);
  }

  async list(query: CatalogQuery) {
    return queryProducts(await this.allActive(), query);
  }

  async getBySlug(slug: string): Promise<PublicProduct | null> {
    const { data, error } = await this.client
      .from("products")
      .select(PUBLIC_COLUMNS)
      .eq("active", true)
      .eq("slug", slug)
      .maybeSingle();
    if (error) throw new Error("Não foi possível consultar o produto.");
    return data ? mapProductRow(data as unknown as DatabaseProductRow) : null;
  }

  async getFeatured(limit: number): Promise<PublicProduct[]> {
    return (await this.allActive()).filter((product) => product.featured).slice(0, limit);
  }

  async getRelated(product: PublicProduct, limit: number): Promise<PublicProduct[]> {
    return (await this.allActive())
      .filter(
        (candidate) =>
          candidate.id !== product.id &&
          (candidate.category === product.category ||
            candidate.tags.some((tag) => product.tags.includes(tag))),
      )
      .slice(0, limit);
  }
}
