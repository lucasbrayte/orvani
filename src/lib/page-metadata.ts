import type { Metadata } from "next";

import { getRuntimeEnv } from "@/config/env";
import { siteIdentity } from "@/lib/site";

export function buildPageMetadata({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  const siteUrl = getRuntimeEnv().siteUrl;
  const canonical = new URL(path, siteUrl).href;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      type: "website",
      locale: "pt_BR",
      siteName: siteIdentity.name,
      title,
      description,
      url: canonical,
      images: [{ url: new URL("/opengraph-image", siteUrl).href, alt: `${siteIdentity.name} — ${siteIdentity.slogan}` }],
    },
  };
}
