import type { SupabaseClient } from "@supabase/supabase-js";

import type { Partner } from "@/domain/products/model";
import { getRuntimeEnv } from "@/config/env";
import { createSupabaseAdminClient } from "@/integrations/supabase/client";

export type ClickEvent = {
  productId: string;
  partner: Partner;
  clickedAt: Date;
};

export interface ClickMetrics {
  record(event: ClickEvent): Promise<void>;
}

class NoopClickMetrics implements ClickMetrics {
  async record(): Promise<void> {}
}

class SupabaseClickMetrics implements ClickMetrics {
  constructor(private readonly client: SupabaseClient = createSupabaseAdminClient()) {}

  async record(event: ClickEvent): Promise<void> {
    const { error } = await this.client.from("affiliate_clicks").insert({
      product_id: event.productId,
      partner: event.partner,
      clicked_at: event.clickedAt.toISOString(),
    });
    if (error) throw new Error("Não foi possível registrar a métrica.");
  }
}

export function getClickMetrics(): ClickMetrics {
  return getRuntimeEnv().catalogMode === "supabase"
    ? new SupabaseClickMetrics()
    : new NoopClickMetrics();
}
