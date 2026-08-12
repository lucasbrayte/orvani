import { expect, test } from "@playwright/test";

test("affiliate route returns a temporary no-store redirect to the stored partner", async ({ request }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "HTTP route behavior is viewport-independent");
  test.slow();
  const response = await request.get("/go/demo-001", { maxRedirects: 0 });

  expect(response.status()).toBe(307);
  expect(response.headers().location).toBe("https://shopee.com.br/");
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect(response.headers()["referrer-policy"]).toBe("no-referrer");
});

test("an unknown product cannot produce an external redirect", async ({ request }, testInfo) => {
  test.skip(testInfo.project.name !== "chromium", "HTTP route behavior is viewport-independent");
  const response = await request.get("/go/unknown-product", { maxRedirects: 0 });

  expect(response.status()).toBe(404);
  expect(response.headers().location).toBeUndefined();
  expect(await response.text()).toMatch(/oferta não encontrada/i);
});
