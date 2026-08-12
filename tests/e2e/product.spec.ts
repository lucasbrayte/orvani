import { expect, test } from "@playwright/test";

test("product page identifies destination and shares its canonical URL", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/produto/fone-essencial");

  await expect(page.getByRole("heading", { level: 1, name: /fone essencial/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /ver oferta na shopee/i })).toHaveAttribute(
    "href",
    /\/go\/demo-001/,
  );
  await expect(page.getByText(/preço e disponibilidade podem mudar/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: /produtos relacionados/i })).toBeVisible();
  await page.getByRole("button", { name: /copiar link/i }).click();
  await expect(page.getByRole("status")).toContainText(/link copiado/i);
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "/produto/fone-essencial",
  );
});

test("missing products render a clear not-found state", async ({ page }) => {
  await page.goto("/produto/produto-inexistente");
  await expect(page.getByRole("heading", { name: /não encontramos essa oferta/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /voltar ao catálogo/i })).toBeVisible();
});
