const DECIMAL_PRICE = /^(0|[1-9]\d*)\.\d{2}$/;
const BRAZILIAN_PRICE = /^(0|[1-9]\d{0,2}(?:\.\d{3})*),\d{2}$/;

export function parsePrice(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;

  if (typeof value === "number") {
    if (!Number.isFinite(value) || value <= 0) throw new Error("Preço inválido.");
    return Math.round(value * 100) / 100;
  }

  const normalized = value.trim();
  let canonical: string;

  if (DECIMAL_PRICE.test(normalized)) {
    canonical = normalized;
  } else if (BRAZILIAN_PRICE.test(normalized)) {
    canonical = normalized.replaceAll(".", "").replace(",", ".");
  } else {
    throw new Error("Preço em formato inválido ou ambíguo.");
  }

  const parsed = Number(canonical);
  if (!Number.isFinite(parsed) || parsed <= 0) throw new Error("Preço inválido.");
  return parsed;
}

export function parseBoolean(value: string | boolean | number): boolean {
  if (typeof value === "boolean") return value;
  const normalized = String(value).trim().toLocaleLowerCase("pt-BR");
  if (["true", "sim", "1"].includes(normalized)) return true;
  if (["false", "não", "nao", "0"].includes(normalized)) return false;
  throw new Error("Booleano inválido.");
}

export function parseList(value: string | string[] | null | undefined): string[] {
  if (value === null || value === undefined || value === "") return [];

  let entries: unknown;
  if (Array.isArray(value)) {
    entries = value;
  } else if (value.trim().startsWith("[")) {
    try {
      entries = JSON.parse(value);
    } catch {
      throw new Error("Lista JSON inválida.");
    }
  } else {
    entries = value.split("|");
  }

  if (!Array.isArray(entries) || entries.some((entry) => typeof entry !== "string")) {
    throw new Error("A lista deve conter somente textos.");
  }

  return [...new Set(entries.map((entry) => entry.trim()).filter(Boolean))];
}

export function normalizeSlug(value: string): string {
  return value
    .trim()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " e ")
    .toLocaleLowerCase("pt-BR")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
}

export function calculateDiscount(current: number, previous: number | null): number | null {
  if (!Number.isFinite(current) || current <= 0 || previous === null) return null;
  if (!Number.isFinite(previous) || previous <= current) return null;
  return Math.round(((previous - current) / previous) * 100);
}
