import type { Partner } from "@/domain/products/model";
import type { AffiliateRedirectDependencies } from "@/app/go/[productId]/handler";

type Options = {
  target?: null;
  url?: string;
  active?: boolean;
  metricsError?: boolean;
};

export function redirectHarness(options: Options = {}) {
  const events: { productId: string; partner: Partner }[] = [];
  const target =
    options.target === null || options.active === false
      ? null
      : {
          productId: "demo-001",
          partner: "amazon" as const,
          url: options.url ?? "https://amazon.com.br/item",
        };

  const dependencies: AffiliateRedirectDependencies = {
    repository: { getActiveAffiliateTarget: async () => target },
    metrics: {
      record: async (event) => {
        if (options.metricsError) throw new Error("metrics unavailable");
        events.push({ productId: event.productId, partner: event.partner });
      },
    },
    allowedHosts: ["amazon.com.br"],
    now: () => new Date("2026-08-11T12:00:00.000Z"),
    reportError: () => undefined,
  };

  return { dependencies, events };
}
