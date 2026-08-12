import { describe, expect, it } from "vitest";

import { parseSheet } from "@/sync/sheet-parser";

import { header, validRow } from "../fixtures/sheets";

describe("private catalog sheet", () => {
  it("parses a valid row into normalized domain data", () => {
    const result = parseSheet(
      [[...header], [...validRow]],
      ["images.example.com"],
      ["amazon.com.br"],
    );

    expect(result.valid).toHaveLength(1);
    expect(result.valid[0]).toMatchObject({
      id: "demo-001",
      type: "fisico",
      partner: "amazon",
      currentPrice: 1299.9,
    });
    expect(result.rejected).toEqual([]);
  });

  it("rejects one invalid row without discarding valid rows", () => {
    const invalid = [...validRow];
    invalid[0] = "preserve-me";
    invalid[9] = "USD";

    const result = parseSheet(
      [[...header], [...validRow], invalid],
      ["images.example.com"],
      ["amazon.com.br"],
    );

    expect(result.valid).toHaveLength(1);
    expect(result.rejected).toMatchObject([{ row: 3, id: "preserve-me" }]);
    expect(result.preservedIds).toEqual(["preserve-me"]);
  });

  it("fails the snapshot when required headers are missing or duplicated", () => {
    expect(() => parseSheet([["id", "nome"], [...validRow]], [], [])).toThrowError(/cabeçalho/i);
    expect(() => parseSheet([[...header, "id"], [...validRow]], [], [])).toThrowError(/duplicada/i);
  });

  it("rejects semantic data beyond the documented columns", () => {
    expect(() =>
      parseSheet([[...header], [...validRow, "surpresa"]], ["images.example.com"], ["amazon.com.br"]),
    ).toThrowError(/coluna/i);
  });

  it("sanitizes row errors", () => {
    const invalid = [...validRow];
    invalid[13] = "https://user:secret@amazon.com.br/item";

    const result = parseSheet(
      [[...header], invalid],
      ["images.example.com"],
      ["amazon.com.br"],
    );

    expect(JSON.stringify(result.rejected)).not.toContain("secret");
    expect(result.rejected[0]).toMatchObject({ code: "INVALID_ROW", fields: ["link_afiliado"] });
  });
});
