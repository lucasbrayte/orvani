import type { MetadataRoute } from "next";

import { getRuntimeEnv } from "@/config/env";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getRuntimeEnv().siteUrl;
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/go/"],
    },
    sitemap: new URL("/sitemap.xml", siteUrl).href,
    host: siteUrl,
  };
}
