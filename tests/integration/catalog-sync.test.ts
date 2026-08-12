import { describe, expect, it } from "vitest";

import { synchronizeCatalog } from "@/sync/catalog-sync";

import { createMemorySyncHarness } from "../fixtures/sync-harness";

describe("catalog synchronization", () => {
  it("imports valid rows, preserves rejected IDs and deactivates truly absent products", async () => {
    const harness = createMemorySyncHarness({ existingIds: ["invalid-old", "missing"] });
    const result = await synchronizeCatalog(harness.withRows("one-valid-one-invalid"));

    expect(result.status).toBe("partial");
    expect(result.imported).toBe(1);
    expect(result.rejected).toBe(1);
    expect(harness.store.activeIds()).toContain("invalid-old");
    expect(harness.store.activeIds()).not.toContain("missing");
  });

  it("preserves the full previous catalog after total read failure", async () => {
    const harness = createMemorySyncHarness({ existingIds: ["a", "b"] });
    const result = await synchronizeCatalog(
      harness.withReadError(new Error("network secret details")),
    );

    expect(result.status).toBe("failed");
    expect(harness.store.activeIds()).toEqual(["a", "b"]);
    expect(JSON.stringify(result)).not.toContain("secret details");
  });

  it("is idempotent for an unchanged snapshot", async () => {
    const harness = createMemorySyncHarness();
    const first = await synchronizeCatalog(harness.withRows("valid-snapshot"));
    const second = await synchronizeCatalog(harness.withRows("valid-snapshot"));

    expect(first.imported).toBe(2);
    expect(second.imported).toBe(0);
    expect(second.updated).toBe(0);
    expect(harness.store.uniqueProductCount()).toBe(2);
  });
});
