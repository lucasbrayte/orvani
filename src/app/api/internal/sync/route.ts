import { SupabaseAdminCatalogRepository } from "@/catalog/admin-repository";
import { getAffiliateHosts, getImageHosts, getSheetsEnv, getSyncSecret } from "@/config/env";
import { GoogleSheetsReader } from "@/integrations/google/sheets";
import { parseAllowedHosts } from "@/security/external-url";
import { SlidingWindowLimiter } from "@/security/rate-limit";
import { synchronizeCatalog } from "@/sync/catalog-sync";

import { handleSyncRequest } from "./handler";

export const dynamic = "force-dynamic";

const limiter = new SlidingWindowLimiter({ max: 6, windowMs: 10 * 60 * 1_000 });

export async function POST(request: Request): Promise<Response> {
  try {
    const imageHostConfig = getImageHosts();
    if (!imageHostConfig) throw new Error("Configuração de imagens ausente.");

    const reader = new GoogleSheetsReader(getSheetsEnv());
    const repository = new SupabaseAdminCatalogRepository();
    const imageHosts = parseAllowedHosts(imageHostConfig);
    const affiliateHosts = parseAllowedHosts(getAffiliateHosts());

    return handleSyncRequest(request, {
      secret: getSyncSecret(),
      limiter,
      now: () => Date.now(),
      synchronize: () =>
        synchronizeCatalog({
          reader,
          repository,
          imageHosts,
          affiliateHosts,
          logger: {
            info: (event, details) => console.log(JSON.stringify({ event, ...details })),
            error: (event, details) => console.error(JSON.stringify({ event, ...details })),
          },
        }),
      reportError: (code) => console.error(JSON.stringify({ event: code })),
    });
  } catch {
    return new Response(JSON.stringify({ status: "unavailable" }), {
      status: 503,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "application/json; charset=utf-8",
      },
    });
  }
}
