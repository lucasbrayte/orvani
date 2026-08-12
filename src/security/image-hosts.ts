import { parseAllowedHosts } from "./external-url";

export type ImageRemotePattern = {
  protocol: "https";
  hostname: string;
  port: "";
  pathname: "/**";
};

export function buildImageRemotePatterns(value: string | undefined): ImageRemotePattern[] {
  if (!value?.trim()) return [];
  return parseAllowedHosts(value).flatMap((hostname) => [
    { protocol: "https", hostname, port: "", pathname: "/**" },
    { protocol: "https", hostname: `**.${hostname}`, port: "", pathname: "/**" },
  ]);
}
