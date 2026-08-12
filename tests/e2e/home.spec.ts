import { expect, test } from "@playwright/test";

test("home explains the service and exposes keyboard-operable highlights", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1, name: /boas escolhas/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /ver catálogo/i })).toBeVisible();
  await expect(page.getByText(/direcionado à loja parceira/i)).toBeVisible();

  const carousel = page.getByRole("region", { name: /ofertas em destaque/i });
  const next = carousel.getByRole("button", { name: /próxima oferta/i });
  await expect(next).toBeVisible();
  await next.focus();
  await page.keyboard.press("Enter");
  await expect(carousel).toHaveAttribute("data-index", "1");
});

test("mobile menu keeps focus and closes with Escape", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const trigger = page.getByRole("button", { name: /abrir menu/i });
  await trigger.click();
  const menu = page.getByRole("navigation", { name: /menu móvel/i });
  await expect(menu).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toBeHidden();
  await expect(trigger).toBeFocused();
});
