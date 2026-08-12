import { describe, expect, it } from "vitest";

import { verifyBearerSecret } from "@/security/secret";

describe("sync secret", () => {
  it.each([null, "", "Basic abc", "Bearer", "Bearer wrong"])(
    "rejects invalid authorization %s",
    (header) => {
      expect(verifyBearerSecret(header, "a".repeat(48))).toBe(false);
    },
  );

  it("accepts only the exact Bearer secret", () => {
    const secret = "a".repeat(48);
    expect(verifyBearerSecret(`Bearer ${secret}`, secret)).toBe(true);
    expect(verifyBearerSecret(`Bearer ${secret}x`, secret)).toBe(false);
  });
});
