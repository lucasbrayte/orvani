import type { SyncRouteDependencies } from "@/app/api/internal/sync/handler";
import { handleSyncRequest } from "@/app/api/internal/sync/handler";
import { SlidingWindowLimiter } from "@/security/rate-limit";

export function createSyncRouteHarness({ secret, max }: { secret: string; max: number }) {
  let now = 1_700_000_000_000;
  const dependencies: SyncRouteDependencies = {
    secret,
    limiter: new SlidingWindowLimiter({ max, windowMs: 600_000 }),
    now: () => now,
    synchronize: async () => ({
      status: "success",
      read: 2,
      imported: 1,
      updated: 1,
      rejected: 0,
      deactivated: 0,
    }),
    reportError: () => undefined,
  };

  return {
    advance(milliseconds: number) {
      now += milliseconds;
    },
    request(
      method: string,
      options: { bearer?: string; querySecret?: string } = {},
    ): Promise<Response> {
      const url = new URL("https://orvani.example/api/internal/sync");
      if (options.querySecret) url.searchParams.set("secret", options.querySecret);
      return handleSyncRequest(
        new Request(url, {
          method,
          headers: options.bearer ? { Authorization: `Bearer ${options.bearer}` } : {},
        }),
        dependencies,
      );
    },
  };
}
