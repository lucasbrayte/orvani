import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const pages = ["/", "/catalogo", "/produto/fone-essencial", "/transparencia"];

for (const path of pages) {
  test(`${path} has no detectable WCAG A/AA violations`, async ({ page }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();

    const violations = results.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.map((node) => ({
        target: node.target.join(" "),
        message: node.any[0]?.message ?? node.failureSummary,
      })),
    }));
    expect(violations).toEqual([]);
  });
}

test("skip link moves keyboard navigation to the main content", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: /pular para o conteúdo/i });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main#conteudo")).toBeFocused();
});

test("small screens do not introduce document-level horizontal scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/catalogo");
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
});
