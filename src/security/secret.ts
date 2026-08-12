import { timingSafeEqual } from "node:crypto";

export function verifyBearerSecret(header: string | null, expected: string): boolean {
  const match = /^Bearer ([^\s]+)$/.exec(header ?? "");
  const candidate = match?.[1] ?? "";
  const expectedBuffer = Buffer.from(expected, "utf8");
  if (expectedBuffer.length === 0) return false;

  const candidateBuffer = Buffer.from(candidate, "utf8");
  const comparable = Buffer.alloc(expectedBuffer.length);
  candidateBuffer.copy(comparable, 0, 0, expectedBuffer.length);
  const equalBytes = timingSafeEqual(expectedBuffer, comparable);

  return Boolean(match) && candidateBuffer.length === expectedBuffer.length && equalBytes;
}
