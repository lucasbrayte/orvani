import path from "node:path";

import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

describe("ESLint workspace boundaries", () => {
  it(
    "ignores isolated Git worktrees nested under the repository",
    async () => {
      const eslint = new ESLint();
      const nestedWorktreeFile = path.join(
        process.cwd(),
        ".worktrees",
        "probe",
        "src",
        "page.tsx",
      );

      await expect(eslint.isPathIgnored(nestedWorktreeFile)).resolves.toBe(true);
    },
    20_000,
  );
});
