import { describe, expect, it } from "vitest";

import { mapProductRow } from "@/catalog/supabase-repository";

describe("Supabase product mapping", () => {
  it("maps numeric strings and never requires affiliate_url for public reads", () => {
    const product = mapProductRow({
      id: "db-1",
      name: "Item",
      slug: "item",
      category: "Casa",
      type: "fisico",
      short_description: "Descrição",
      description: "Descrição completa",
      current_price: "49.90",
      previous_price: null,
      currency: "BRL",
      primary_image: "/images/product-fallback.svg",
      images: [],
      partner: "amazon",
      featured: false,
      active: true,
      stock_status: "informativo",
      tags: [],
      updated_at: "2026-08-11T00:00:00.000Z",
    });

    expect(product.currentPrice).toBe(49.9);
    expect(product).not.toHaveProperty("affiliateUrl");
  });
});
