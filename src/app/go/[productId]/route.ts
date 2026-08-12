import { getAffiliateRepository } from "@/catalog/affiliate-repository";
import { getAffiliateHosts } from "@/config/env";
import { getClickMetrics } from "@/metrics/clicks";
import { parseAllowedHosts } from "@/security/external-url";

import { handleAffiliateRedirect } from "./handler";

export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ productId: string }> },
): Promise<Response> {
  const { productId } = await params;
  return handleAffiliateRedirect(productId, {
    repository: getAffiliateRepository(),
    metrics: getClickMetrics(),
    allowedHosts: parseAllowedHosts(getAffiliateHosts()),
    now: () => new Date(),
    reportError: (code) => console.error(JSON.stringify({ event: code })),
  });
}
