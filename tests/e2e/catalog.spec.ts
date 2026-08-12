import { expect, test } from "@playwright/test";

test("search and filters persist in URL and browser history", async ({ page }) => {
  await page.goto("/catalogo");
  await page.getByLabel("Buscar produtos").fill("fone");
  await page.getByLabel("Loja parceira").selectOption("shopee");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();

  await expect(page).toHaveURL(/q=fone/);
  await expect(page).toHaveURL(/loja=shopee/);
  await expect(page.getByRole("heading", { name: /fone essencial/i })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/catalogo$/);
});

test("catalog announces no results and offers a reset", async ({ page }) => {
  await page.goto("/catalogo?q=produto-que-nao-existe");

  await expect(page.getByRole("status")).toContainText(/nenhuma oferta encontrada/i);
  await page.getByRole("link", { name: /limpar filtros/i }).click();
  await expect(page.getByRole("list", { name: /produtos/i })).toBeVisible();
});
