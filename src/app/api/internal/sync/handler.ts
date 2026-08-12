import type { SlidingWindowLimiter } from "@/security/rate-limit";
import { verifyBearerSecret } from "@/security/secret";
import type { SyncResult } from "@/sync/types";

export type SyncRouteDependencies = {
  secret: string;
  limiter: SlidingWindowLimiter;
  now: () => number;
  synchronize: () => Promise<SyncResult>;
  reportError: (code: string) => void;
};

const baseHeaders: Record<string, string> = {
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
};

function json(
  body: Record<string, number | string>,
  status: number,
  headers: HeadersInit = baseHeaders,
): Response {
  return new Response(JSON.stringify(body), { status, headers });
}

export async function handleSyncRequest(
  request: Request,
  dependencies: SyncRouteDependencies,
): Promise<Response> {
  if (request.method !== "POST") {
    return json({ status: "method_not_allowed" }, 405, { ...baseHeaders, Allow: "POST" });
  }

  if (!verifyBearerSecret(request.headers.get("authorization"), dependencies.secret)) {
    return json({ status: "unauthorized" }, 401);
  }

  const limit = dependencies.limiter.check("catalog-sync", dependencies.now());
  if (!limit.allowed) {
    return json(
      { status: "rate_limited" },
      429,
      { ...baseHeaders, "Retry-After": String(limit.retryAfterSeconds) },
    );
  }

  try {
    const result = await dependencies.synchronize();
    const response = {
      status: result.status,
      read: result.read,
      imported: result.imported,
      updated: result.updated,
      rejected: result.rejected,
      deactivated: result.deactivated,
    };
    return json(response, result.status === "failed" ? 503 : 200);
  } catch {
    dependencies.reportError("SYNC_ROUTE_FAILED");
    return json({ status: "failed" }, 503);
  }
}
