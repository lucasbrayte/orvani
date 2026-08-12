import { describe, expect, it } from "vitest";

import { parseCatalogSearchParams } from "@/domain/products/search-params";

describe("catalog search params", () => {
  it("normalizes valid shareable filters", () => {
    expect(
      parseCatalogSearchParams({
        q: "fone",
        tipo: "fisico",
        loja: "amazon",
        min: "10.00",
        max: "500.00",
        ordem: "price_asc",
        pagina: "2",
      }),
    ).toMatchObject({
      search: "fone",
      type: "fisico",
      partner: "amazon",
      minPrice: 10,
      maxPrice: 500,
      sort: "price_asc",
      page: 2,
      pageSize: 12,
    });
  });

  it("falls back safely for invalid enums, ranges and pages", () => {
    expect(
      parseCatalogSearchParams({
        tipo: "script",
        ordem: "random",
        min: "-1",
        max: "NaN",
        pagina: "999999",
      }),
    ).toEqual({ page: 1, pageSize: 12, sort: "relevance" });
  });

  it("uses only the first value and bounds user text", () => {
    const result = parseCatalogSearchParams({
      q: ["  câmera  ", "ignored"],
      categoria: "x".repeat(200),
    });
    expect(result.search).toBe("câmera");
    expect(result.category).toBeUndefined();
  });
});
