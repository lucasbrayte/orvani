import { describe, expect, it } from "vitest";

import { DemoCatalogRepository } from "@/catalog/demo-repository";

describe("demo catalog repository", () => {
  it("returns only active products and resolves slug and related queries", async () => {
    const repository = new DemoCatalogRepository();
    const page = await repository.list({ page: 1, pageSize: 12 });

    expect(page.items.length).toBeGreaterThanOrEqual(12);
    expect(page.items.every((product) => product.active)).toBe(true);

    const product = await repository.getBySlug("fone-essencial");
    expect(product?.partner).toBe("shopee");
    expect((await repository.getRelated(product!, 4)).every((item) => item.id !== product!.id)).toBe(
      true,
    );
  });

  it("does not expose affiliate targets through the public contract", async () => {
    const repository = new DemoCatalogRepository();
    const product = await repository.getBySlug("fone-essencial");

    expect(product).not.toHaveProperty("affiliateUrl");
  });
});
