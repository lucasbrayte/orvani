import { describe, expect, it } from "vitest";

import { createSyncRouteHarness } from "../fixtures/sync-route-harness";

describe("internal sync route", () => {
  it("allows POST with the exact secret and rejects GET and query secrets", async () => {
    const secret = "a".repeat(48);
    const harness = createSyncRouteHarness({ secret, max: 2 });

    expect((await harness.request("GET")).status).toBe(405);
    expect((await harness.request("POST", { querySecret: secret })).status).toBe(401);
    const response = await harness.request("POST", { bearer: secret });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      status: "success",
      read: 2,
      imported: 1,
      updated: 1,
      rejected: 0,
      deactivated: 0,
    });
  });

  it("limits authenticated bursts without letting rejected callers exhaust the budget", async () => {
    const secret = "a".repeat(48);
    const harness = createSyncRouteHarness({ secret, max: 2 });

    for (let index = 0; index < 5; index += 1) {
      expect((await harness.request("POST", { bearer: "wrong" })).status).toBe(401);
    }
    expect((await harness.request("POST", { bearer: secret })).status).toBe(200);
    expect((await harness.request("POST", { bearer: secret })).status).toBe(200);
    const limited = await harness.request("POST", { bearer: secret });
    expect(limited.status).toBe(429);
    expect(limited.headers.get("retry-after")).toBe("600");
  });
});
