import { describe, expect, it } from "vitest";

import { buildContentSecurityPolicy } from "@/security/csp";
import { buildSecurityHeaders } from "@/security/headers";

describe("security headers", () => {
  it("builds a strict production CSP around a request nonce", () => {
    const csp = buildContentSecurityPolicy("nonce-value", false);

    expect(csp).toContain("script-src 'self' 'nonce-nonce-value' 'strict-dynamic'");
    expect(csp).toContain("style-src 'self' 'nonce-nonce-value'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("upgrade-insecure-requests");
    expect(csp).not.toContain("'unsafe-inline'");
    expect(csp).not.toContain("'unsafe-eval'");
  });

  it("limits unsafe-eval to development diagnostics", () => {
    const csp = buildContentSecurityPolicy("nonce-value", true);

    expect(csp).toContain("'unsafe-eval'");
    expect(csp).not.toContain("upgrade-insecure-requests");
    expect(csp).not.toContain("'unsafe-inline'");
  });

  it("adds HSTS only in production and always sends baseline protections", () => {
    const production = buildSecurityHeaders(true);
    const development = buildSecurityHeaders(false);

    expect(production).toContainEqual({
      key: "Strict-Transport-Security",
      value: "max-age=63072000; includeSubDomains; preload",
    });
    expect(development.some(({ key }) => key === "Strict-Transport-Security")).toBe(false);
    expect(production).toContainEqual({ key: "X-Content-Type-Options", value: "nosniff" });
    expect(production).toContainEqual({
      key: "Referrer-Policy",
      value: "strict-origin-when-cross-origin",
    });
    expect(production.find(({ key }) => key === "Permissions-Policy")?.value).toContain(
      "camera=()",
    );
  });
});
