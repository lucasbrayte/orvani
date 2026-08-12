import type { NextConfig } from "next";

import { buildSecurityHeaders } from "./src/security/headers";
import { buildImageRemotePatterns } from "./src/security/image-hosts";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1"],
  images: {
    remotePatterns: buildImageRemotePatterns(process.env.PRODUCT_IMAGE_ALLOWED_HOSTS),
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: buildSecurityHeaders(process.env.NODE_ENV === "production"),
      },
      {
        source: "/go/:path*",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
};

export default nextConfig;
