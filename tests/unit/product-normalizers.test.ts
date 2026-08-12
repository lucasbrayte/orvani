import { describe, expect, it } from "vitest";

import {
  calculateDiscount,
  normalizeSlug,
  parseBoolean,
  parseList,
  parsePrice,
} from "@/domain/products/normalizers";

describe("product normalizers", () => {
  it.each([
    ["1299.90", 1299.9],
    ["1.299,90", 1299.9],
    ["0,99", 0.99],
  ])("parses unambiguous price %s", (input, expected) => {
    expect(parsePrice(input)).toBe(expected);
  });

  it.each(["1,299.90", "R$ 10,00", "12.345", "-1.00", "0"])(
    "rejects invalid or ambiguous price %s",
    (input) => expect(() => parsePrice(input)).toThrow(),
  );

  it.each([
    ["true", true],
    ["sim", true],
    ["1", true],
    ["false", false],
    ["não", false],
    ["0", false],
  ])("normalizes boolean %s", (input, expected) => {
    expect(parseBoolean(input)).toBe(expected);
  });

  it("rejects unknown booleans", () => {
    expect(() => parseBoolean("talvez")).toThrow();
  });

  it("accepts JSON or pipe-separated lists", () => {
    expect(parseList('["leve", "digital"]')).toEqual(["leve", "digital"]);
    expect(parseList("leve|digital")).toEqual(["leve", "digital"]);
  });

  it("creates a stable ASCII slug", () => {
    expect(normalizeSlug("  Câmera & Ação  ")).toBe("camera-e-acao");
  });

  it("calculates only a valid rounded discount", () => {
    expect(calculateDiscount(75, 100)).toBe(25);
    expect(calculateDiscount(100, 100)).toBeNull();
    expect(calculateDiscount(120, 100)).toBeNull();
  });
});
