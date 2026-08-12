import { describe, expect, it } from "vitest";

import { buildProductJsonLd, serializeJsonLd } from "@/lib/structured-data";

import { makeProduct } from "../fixtures/products";

describe("product structured data", () => {
  it("identifies the partner as seller without invented ratings", () => {
    const json = buildProductJsonLd(
      makeProduct({ partner: "amazon", stockStatus: "informativo" }),
      "https://orvani.example",
    );

    expect(json.offers.seller.name).toBe("Amazon");
    expect(json).not.toHaveProperty("aggregateRating");
    expect(json.offers).not.toHaveProperty("availability");
    expect(json.offers.url).toBe("https://orvani.example/go/product-1");
  });

  it("maps only explicit availability", () => {
    const available = buildProductJsonLd(
      makeProduct({ stockStatus: "disponivel" }),
      "https://orvani.example",
    );
    const unavailable = buildProductJsonLd(
      makeProduct({ stockStatus: "indisponivel" }),
      "https://orvani.example",
    );

    expect(available.offers.availability).toBe("https://schema.org/InStock");
    expect(unavailable.offers.availability).toBe("https://schema.org/OutOfStock");
  });

  it("prevents spreadsheet text from closing the JSON-LD script", () => {
    const serialized = serializeJsonLd({
      description: '</script><img src=x onerror="alert(1)">',
    });

    expect(serialized).not.toContain("<");
    expect(serialized).not.toContain("</script>");
    expect(JSON.parse(serialized)).toEqual({
      description: '</script><img src=x onerror="alert(1)">',
    });
  });
});
