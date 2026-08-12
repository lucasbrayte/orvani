import { describe, expect, it } from "vitest";

import { handleAffiliateRedirect } from "@/app/go/[productId]/handler";

import { redirectHarness } from "../fixtures/redirect-harness";

describe("affiliate redirect", () => {
  it("temporarily redirects an active stored destination and records a minimal click", async () => {
    const harness = redirectHarness({ url: "https://www.amazon.com.br/item", active: true });
    const response = await handleAffiliateRedirect("demo-001", harness.dependencies);

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://www.amazon.com.br/item");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(harness.events).toEqual([{ productId: "demo-001", partner: "amazon" }]);
  });

  it("returns 404 without a redirect for absent or inactive products", async () => {
    const response = await handleAffiliateRedirect(
      "missing",
      redirectHarness({ target: null }).dependencies,
    );

    expect(response.status).toBe(404);
    expect(response.headers.get("location")).toBeNull();
  });

  it.each([
    "https://amazon.com.br.evil.example/item",
    "https://user:pass@amazon.com.br/item",
    "http://amazon.com.br/item",
    "javascript:alert(1)",
    "data:text/html,hello",
  ])("blocks an unsafe stored destination: %s", async (url) => {
    const response = await handleAffiliateRedirect(
      "demo-001",
      redirectHarness({ url, active: true }).dependencies,
    );

    expect(response.status).toBe(502);
    expect(response.headers.get("location")).toBeNull();
  });

  it("still redirects if metric storage is unavailable", async () => {
    const response = await handleAffiliateRedirect(
      "demo-001",
      redirectHarness({ url: "https://amazon.com.br/item", metricsError: true }).dependencies,
    );

    expect(response.status).toBe(307);
  });
});
