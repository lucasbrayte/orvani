import { describe, expect, it } from "vitest";

import { parseAllowedHosts, validateExternalUrl } from "@/security/external-url";
import { buildImageRemotePatterns } from "@/security/image-hosts";

const hosts = ["amazon.com.br", "amzn.to", "shopee.com.br", "mercadolivre.com.br"];

describe("external URL allowlist", () => {
  it("normalizes a comma-separated host configuration", () => {
    expect(parseAllowedHosts(" Amazon.com.br, amzn.to,amazon.com.br ")).toEqual([
      "amazon.com.br",
      "amzn.to",
    ]);
  });

  it.each([
    "https://amazon.com.br/produto",
    "https://www.amazon.com.br/produto",
    "https://s.shopee.com.br/abc",
  ])("allows exact hosts and delimited subdomains: %s", (value) => {
    expect(validateExternalUrl(value, hosts).protocol).toBe("https:");
  });

  it.each([
    "https://amazon.com.br.evil.example/item",
    "https://notamazon.com.br/item",
    "https://evil-amazon.com.br/item",
    "https://user:pass@amazon.com.br/item",
    "http://amazon.com.br/item",
    "https://amazon.com.br:444/item",
    "javascript:alert(1)",
    "data:text/html,hello",
    "https://%65vil.example/item",
    "https://127.0.0.1/item",
  ])("blocks unsafe destination: %s", (value) => {
    expect(() => validateExternalUrl(value, hosts)).toThrow();
  });
});

describe("Next image allowlist", () => {
  it("maps each configured host to exact and subdomain-only HTTPS patterns", () => {
    expect(buildImageRemotePatterns("cdn.example.com")).toEqual([
      { protocol: "https", hostname: "cdn.example.com", port: "", pathname: "/**" },
      { protocol: "https", hostname: "**.cdn.example.com", port: "", pathname: "/**" },
    ]);
  });

  it("uses no remote image origin when the setting is empty", () => {
    expect(buildImageRemotePatterns("  ")).toEqual([]);
  });
});
