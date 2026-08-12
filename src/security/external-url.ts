import { isIP } from "node:net";

function normalizeAllowedHost(value: string): string {
  const input = value.trim().toLocaleLowerCase("en-US");
  if (!input || input.includes("://") || input.includes("/") || input.includes("%") || input.endsWith(".")) {
    throw new Error("Host permitido inválido.");
  }

  const parsed = new URL(`https://${input}`);
  if (parsed.hostname !== input || parsed.port || isIP(parsed.hostname)) {
    throw new Error("Host permitido inválido.");
  }
  return parsed.hostname;
}

export function parseAllowedHosts(value: string): string[] {
  const hosts = value.split(",").map(normalizeAllowedHost);
  return [...new Set(hosts)];
}

export function validateExternalUrl(raw: string, allowedHosts: readonly string[]): URL {
  if (raw !== raw.trim() || raw.includes("\\")) throw new Error("URL externa inválida.");

  const authority = /^https:\/\/([^/?#]+)/i.exec(raw)?.[1] ?? "";
  if (authority.includes("%")) throw new Error("Hostname codificado não é permitido.");

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("URL externa inválida.");
  }

  const hostname = url.hostname.toLocaleLowerCase("en-US");
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.port ||
    !hostname ||
    hostname.endsWith(".") ||
    isIP(hostname)
  ) {
    throw new Error("Destino externo não permitido.");
  }

  const normalizedAllowedHosts = allowedHosts.map(normalizeAllowedHost);
  const allowed = normalizedAllowedHosts.some(
    (candidate) => hostname === candidate || hostname.endsWith(`.${candidate}`),
  );
  if (!allowed) throw new Error("Host externo não permitido.");

  url.hostname = hostname;
  return url;
}
