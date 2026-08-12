import { expect, test } from "@playwright/test";

const pages = [
  ["/sobre", /sobre a orvani/i],
  ["/como-funciona", /como funciona/i],
  ["/transparencia", /transparência de afiliados/i],
  ["/privacidade", /política de privacidade/i],
  ["/termos", /termos de uso/i],
] as const;

test.describe("institutional pages", () => {
  for (const [path, heading] of pages) {
    test(`${path} has a unique heading and canonical URL`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", new RegExp(path));
      if (path === "/transparencia") {
        await expect(page.getByText(/a orvani pode receber uma comissão/i)).toBeVisible();
        await expect(page.getByText(/não vende, não processa pagamentos/i)).toBeVisible();
      }
    });
  }
});

test("metadata routes and security headers are served", async ({ request }) => {
  const response = await request.get("/");
  const headers = response.headers();
  const csp = headers["content-security-policy"];

  expect(csp).toMatch(/nonce-[A-Za-z0-9+/=]+/);
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).not.toContain("'unsafe-inline'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");

  await expect((await request.get("/robots.txt")).text()).resolves.toContain("Sitemap:");
  await expect((await request.get("/sitemap.xml")).text()).resolves.toContain(
    "/produto/fone-essencial",
  );
});
