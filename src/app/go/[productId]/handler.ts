import type { AffiliateRepository } from "@/catalog/affiliate-repository";
import type { ClickMetrics } from "@/metrics/clicks";
import { validateExternalUrl } from "@/security/external-url";

export type AffiliateRedirectDependencies = {
  repository: AffiliateRepository;
  metrics: ClickMetrics;
  allowedHosts: readonly string[];
  now: () => Date;
  reportError: (code: string) => void;
};

const noStoreHeaders = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
};

export async function handleAffiliateRedirect(
  productId: string,
  dependencies: AffiliateRedirectDependencies,
): Promise<Response> {
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(productId)) {
    return new Response("Oferta não encontrada.", { status: 404, headers: noStoreHeaders });
  }

  let target;
  try {
    target = await dependencies.repository.getActiveAffiliateTarget(productId);
  } catch {
    dependencies.reportError("AFFILIATE_LOOKUP_FAILED");
    return new Response("Não foi possível abrir a oferta.", { status: 502, headers: noStoreHeaders });
  }

  if (!target) {
    return new Response("Oferta não encontrada.", { status: 404, headers: noStoreHeaders });
  }

  let destination: URL;
  try {
    destination = validateExternalUrl(target.url, dependencies.allowedHosts);
  } catch {
    dependencies.reportError("AFFILIATE_DESTINATION_BLOCKED");
    return new Response("Destino da oferta indisponível.", { status: 502, headers: noStoreHeaders });
  }

  try {
    await dependencies.metrics.record({
      productId: target.productId,
      partner: target.partner,
      clickedAt: dependencies.now(),
    });
  } catch {
    dependencies.reportError("AFFILIATE_METRIC_FAILED");
  }

  return new Response(null, {
    status: 307,
    headers: { ...noStoreHeaders, Location: destination.href },
  });
}
