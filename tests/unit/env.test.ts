import { describe, expect, it } from "vitest";

import { parseRuntimeEnv } from "@/config/env";

describe("runtime environment", () => {
  it("uses demo with no integration credentials in development", () => {
    expect(parseRuntimeEnv({ NODE_ENV: "development" }).catalogMode).toBe("demo");
  });

  it("rejects a partial Supabase configuration without echoing values", () => {
    const secret = "sb_secret_sensitive";
    expect(() =>
      parseRuntimeEnv({
        NODE_ENV: "development",
        SUPABASE_URL: "https://example.supabase.co",
        SUPABASE_SECRET_KEY: secret,
      }),
    ).toThrowError(/configuração incompleta/i);

    try {
      parseRuntimeEnv({ NODE_ENV: "development", SUPABASE_SECRET_KEY: secret });
    } catch (error) {
      expect(String(error)).not.toContain(secret);
    }
  });

  it("requires production site and database configuration", () => {
    expect(() => parseRuntimeEnv({ NODE_ENV: "production" })).toThrowError(/produção/i);
  });

  it("accepts a complete production catalog configuration", () => {
    expect(
      parseRuntimeEnv({
        NODE_ENV: "production",
        NEXT_PUBLIC_SITE_URL: "https://orvani.example",
        SUPABASE_URL: "https://example.supabase.co",
        SUPABASE_PUBLISHABLE_KEY: "sb_publishable_example",
        SUPABASE_SECRET_KEY: "sb_secret_example",
      }).catalogMode,
    ).toBe("supabase");
  });
});
