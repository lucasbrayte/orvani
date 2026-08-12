import type { MetadataRoute } from "next";

import { getCatalogRepository } from "@/catalog/get-repository";
import { getRuntimeEnv } from "@/config/env";

const staticRoutes = [
  "",
  "/catalogo",
  "/sobre",
  "/como-funciona",
  "/transparencia",
  "/privacidade",
  "/termos",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const siteUrl = getRuntimeEnv().siteUrl;
  const repository = getCatalogRepository();
  const products = [];
  let page = 1;
  let totalPages = 1;

  do {
    const result = await repository.list({ page, pageSize: 48, sort: "recent" });
    products.push(...result.items);
    totalPages = result.totalPages;
    page += 1;
  } while (page <= totalPages);

  return [
    ...staticRoutes.map((path, index) => ({
      url: new URL(path || "/", siteUrl).href,
      changeFrequency: (index < 2 ? "daily" : "monthly") as "daily" | "monthly",
      priority: index === 0 ? 1 : index === 1 ? 0.9 : 0.5,
    })),
    ...products.map((product) => ({
      url: new URL(`/produto/${product.slug}`, siteUrl).href,
      lastModified: new Date(product.updatedAt),
      changeFrequency: "daily" as const,
      priority: product.featured ? 0.8 : 0.7,
    })),
  ];
}
