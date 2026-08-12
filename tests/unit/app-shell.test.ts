import { describe, expect, it } from "vitest";

describe("application shell", () => {
  it("publishes the Orvani name and Brazilian locale", async () => {
    const { siteIdentity } = await import("@/lib/site");

    expect(siteIdentity).toEqual({
      name: "Orvani",
      slogan: "Boas escolhas em um só lugar.",
      locale: "pt-BR",
    });
  });
});
