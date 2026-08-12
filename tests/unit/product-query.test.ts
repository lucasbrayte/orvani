import { describe, expect, it } from "vitest";

import { queryProducts } from "@/domain/products/query";

import { makeProduct } from "../fixtures/products";

const products = [
  makeProduct({
    id: "1",
    name: "Câmera Compacta",
    slug: "camera-compacta",
    category: "Eletrônicos",
    tags: ["foto"],
    currentPrice: 300,
    previousPrice: 400,
    partner: "amazon",
  }),
  makeProduct({
    id: "2",
    name: "Curso de Fotografia",
    slug: "curso-de-fotografia",
    category: "Cursos",
    tags: ["foto"],
    type: "digital",
    currentPrice: 80,
    partner: "mercado_livre",
    updatedAt: "2026-08-12T12:00:00.000Z",
  }),
  makeProduct({
    id: "3",
    name: "Fone Essencial",
    slug: "fone-essencial",
    category: "Eletrônicos",
    currentPrice: 120,
    partner: "shopee",
  }),
];

describe("catalog query", () => {
  it("searches name, description and tags without accents", () => {
    expect(
      queryProducts(products, { search: "camera", page: 1, pageSize: 12 }).items.map(
        (item) => item.id,
      ),
    ).toEqual(["1"]);
    expect(queryProducts(products, { search: "foto", page: 1, pageSize: 12 }).total).toBe(2);
  });

  it("combines filters and sorts by price", () => {
    const result = queryProducts(products, {
      category: "Eletrônicos",
      partner: "shopee",
      minPrice: 100,
      maxPrice: 150,
      sort: "price_asc",
      page: 1,
      pageSize: 12,
    });

    expect(result.items.map((item) => item.id)).toEqual(["3"]);
  });

  it("sorts discounts and recent updates from literal expectations", () => {
    expect(
      queryProducts(products, { sort: "discount_desc", page: 1, pageSize: 12 }).items.map(
        (item) => item.id,
      ),
    ).toEqual(["1", "2", "3"]);
    expect(
      queryProducts(products, { sort: "recent", page: 1, pageSize: 12 }).items.map(
        (item) => item.id,
      ),
    ).toEqual(["2", "1", "3"]);
  });

  it("paginates with bounded page size", () => {
    const result = queryProducts(products, { page: 2, pageSize: 1 });
    expect(result.page).toBe(2);
    expect(result.totalPages).toBe(3);
  });
});
