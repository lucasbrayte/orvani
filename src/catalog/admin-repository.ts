import type { SupabaseClient } from "@supabase/supabase-js";

import type { Partner, Product } from "@/domain/products/model";
import { createSupabaseAdminClient } from "@/integrations/supabase/client";

export type AffiliateTarget = { productId: string; partner: Partner; url: string };
export type SnapshotCounts = { inserted: number; updated: number; deactivated: number };

function toDatabaseProduct(product: Product) {
  return {
    id: product.id,
    name: product.name,
    slug: product.slug,
    category: product.category,
    type: product.type,
    short_description: product.shortDescription,
    description: product.description,
    current_price: product.currentPrice,
    previous_price: product.previousPrice,
    currency: product.currency,
    primary_image: product.primaryImage,
    images: product.images,
    partner: product.partner,
    affiliate_url: product.affiliateUrl,
    featured: product.featured,
    active: product.active,
    stock_status: product.stockStatus,
    tags: product.tags,
    updated_at: product.updatedAt,
  };
}

export class SupabaseAdminCatalogRepository {
  constructor(private readonly client: SupabaseClient = createSupabaseAdminClient()) {}

  async getActiveAffiliateTarget(productId: string): Promise<AffiliateTarget | null> {
    const { data, error } = await this.client
      .from("products")
      .select("id,partner,affiliate_url")
      .eq("id", productId)
      .eq("active", true)
      .maybeSingle();
    if (error) throw new Error("Não foi possível consultar o destino afiliado.");
    if (!data) return null;
    return {
      productId: data.id as string,
      partner: data.partner as Partner,
      url: data.affiliate_url as string,
    };
  }

  async beginSync(): Promise<string> {
    const { data, error } = await this.client
      .from("sync_runs")
      .insert({ status: "running" })
      .select("id")
      .single();
    if (error || !data) throw new Error("Não foi possível iniciar a sincronização.");
    return data.id as string;
  }

  async failSync(runId: string, code: string): Promise<void> {
    const { error } = await this.client
      .from("sync_runs")
      .update({
        status: "failed",
        finished_at: new Date().toISOString(),
        error_summary: [{ code }],
      })
      .eq("id", runId);
    if (error) throw new Error("Não foi possível finalizar a sincronização.");
  }

  async applySnapshot(input: {
    runId: string;
    products: Product[];
    preservedIds: string[];
    rowsRead: number;
    rejected: number;
  }): Promise<SnapshotCounts> {
    const { data, error } = await this.client.rpc("apply_catalog_snapshot", {
      p_run_id: input.runId,
      p_products: input.products.map(toDatabaseProduct),
      p_preserved_ids: input.preservedIds,
      p_rows_read: input.rowsRead,
      p_rejected: input.rejected,
    });
    if (error) throw new Error("Não foi possível aplicar o catálogo validado.");
    const counts = data as Record<string, number>;
    return {
      inserted: counts.inserted ?? 0,
      updated: counts.updated ?? 0,
      deactivated: counts.deactivated ?? 0,
    };
  }
}
