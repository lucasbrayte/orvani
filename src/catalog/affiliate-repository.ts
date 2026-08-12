import type { Partner } from "@/domain/products/model";
import { getRuntimeEnv } from "@/config/env";

import { SupabaseAdminCatalogRepository } from "./admin-repository";
import { demoProducts } from "./demo-data";

export type AffiliateTarget = { productId: string; partner: Partner; url: string };

export interface AffiliateRepository {
  getActiveAffiliateTarget(productId: string): Promise<AffiliateTarget | null>;
}

class DemoAffiliateRepository implements AffiliateRepository {
  async getActiveAffiliateTarget(productId: string): Promise<AffiliateTarget | null> {
    const product = demoProducts.find((candidate) => candidate.active && candidate.id === productId);
    return product
      ? { productId: product.id, partner: product.partner, url: product.affiliateUrl }
      : null;
  }
}

export function getAffiliateRepository(): AffiliateRepository {
  return getRuntimeEnv().catalogMode === "supabase"
    ? new SupabaseAdminCatalogRepository()
    : new DemoAffiliateRepository();
}
