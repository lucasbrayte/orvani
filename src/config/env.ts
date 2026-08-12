import { z } from "zod";

const optionalValue = z.preprocess(
  (value) => (typeof value === "string" && value.trim() === "" ? undefined : value),
  z.string().trim().min(1).optional(),
);

const rawEnvSchema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  CATALOG_DATA_MODE: z.enum(["demo", "supabase"]).optional(),
  NEXT_PUBLIC_SITE_URL: optionalValue,
  SUPABASE_URL: optionalValue,
  SUPABASE_PUBLISHABLE_KEY: optionalValue,
  SUPABASE_SECRET_KEY: optionalValue,
  GOOGLE_SHEETS_SPREADSHEET_ID: optionalValue,
  GOOGLE_SHEETS_RANGE: optionalValue,
  GOOGLE_SERVICE_ACCOUNT_EMAIL: optionalValue,
  GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY: optionalValue,
  CATALOG_SYNC_SECRET: optionalValue,
  AFFILIATE_ALLOWED_HOSTS: optionalValue,
  PRODUCT_IMAGE_ALLOWED_HOSTS: optionalValue,
});

type EnvInput = Record<string, string | undefined>;

function requireCompleteGroup(
  values: Record<string, string | undefined>,
  label: string,
): boolean {
  const present = Object.values(values).filter(Boolean).length;
  if (present > 0 && present < Object.keys(values).length) {
    throw new Error(`Configuração incompleta de ${label}. Verifique as variáveis exigidas.`);
  }
  return present === Object.keys(values).length;
}

function safeUrl(value: string, field: string, requireHttps: boolean): string {
  try {
    const url = new URL(value);
    if ((requireHttps && url.protocol !== "https:") || !["https:", "http:"].includes(url.protocol)) {
      throw new Error();
    }
    return url.origin;
  } catch {
    throw new Error(`A variável ${field} contém uma URL inválida.`);
  }
}

export type RuntimeEnv = {
  nodeEnv: "development" | "test" | "production";
  catalogMode: "demo" | "supabase";
  siteUrl: string;
  supabase?: {
    url: string;
    publishableKey: string;
    secretKey: string;
  };
};

export function parseRuntimeEnv(input: EnvInput): RuntimeEnv {
  let raw: z.infer<typeof rawEnvSchema>;
  try {
    raw = rawEnvSchema.parse(input);
  } catch {
    throw new Error("Configuração de ambiente inválida.");
  }

  const hasSupabase = requireCompleteGroup(
    {
      SUPABASE_URL: raw.SUPABASE_URL,
      SUPABASE_PUBLISHABLE_KEY: raw.SUPABASE_PUBLISHABLE_KEY,
      SUPABASE_SECRET_KEY: raw.SUPABASE_SECRET_KEY,
    },
    "Supabase",
  );

  requireCompleteGroup(
    {
      GOOGLE_SHEETS_SPREADSHEET_ID: raw.GOOGLE_SHEETS_SPREADSHEET_ID,
      GOOGLE_SHEETS_RANGE: raw.GOOGLE_SHEETS_RANGE,
      GOOGLE_SERVICE_ACCOUNT_EMAIL: raw.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY: raw.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY,
    },
    "Google Sheets",
  );

  if (raw.CATALOG_DATA_MODE === "supabase" && !hasSupabase) {
    throw new Error("O modo Supabase exige a configuração completa do banco.");
  }

  if (
    raw.NODE_ENV === "production" &&
    (!raw.NEXT_PUBLIC_SITE_URL || (!hasSupabase && raw.CATALOG_DATA_MODE !== "demo"))
  ) {
    throw new Error(
      "A configuração de produção exige URL pública e Supabase completos ou modo demo explícito.",
    );
  }

  const siteUrl = raw.NEXT_PUBLIC_SITE_URL
    ? safeUrl(raw.NEXT_PUBLIC_SITE_URL, "NEXT_PUBLIC_SITE_URL", raw.NODE_ENV === "production")
    : "http://localhost:3000";

  if (!hasSupabase || raw.CATALOG_DATA_MODE === "demo") {
    return { nodeEnv: raw.NODE_ENV, catalogMode: "demo", siteUrl };
  }

  return {
    nodeEnv: raw.NODE_ENV,
    catalogMode: "supabase",
    siteUrl,
    supabase: {
      url: safeUrl(raw.SUPABASE_URL!, "SUPABASE_URL", true),
      publishableKey: raw.SUPABASE_PUBLISHABLE_KEY!,
      secretKey: raw.SUPABASE_SECRET_KEY!,
    },
  };
}

export function getRuntimeEnv(): RuntimeEnv {
  return parseRuntimeEnv(process.env);
}

export type SheetsEnv = {
  spreadsheetId: string;
  range: string;
  serviceAccountEmail: string;
  privateKey: string;
};

export function getSheetsEnv(input: EnvInput = process.env): SheetsEnv {
  const raw = rawEnvSchema.parse(input);
  const complete = requireCompleteGroup(
    {
      GOOGLE_SHEETS_SPREADSHEET_ID: raw.GOOGLE_SHEETS_SPREADSHEET_ID,
      GOOGLE_SHEETS_RANGE: raw.GOOGLE_SHEETS_RANGE,
      GOOGLE_SERVICE_ACCOUNT_EMAIL: raw.GOOGLE_SERVICE_ACCOUNT_EMAIL,
      GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY: raw.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY,
    },
    "Google Sheets",
  );
  if (!complete) throw new Error("A integração Google Sheets não está configurada.");
  return {
    spreadsheetId: raw.GOOGLE_SHEETS_SPREADSHEET_ID!,
    range: raw.GOOGLE_SHEETS_RANGE!,
    serviceAccountEmail: raw.GOOGLE_SERVICE_ACCOUNT_EMAIL!,
    privateKey: raw.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY!,
  };
}

export function getAffiliateHosts(input: EnvInput = process.env): string {
  const raw = rawEnvSchema.parse(input);
  return raw.AFFILIATE_ALLOWED_HOSTS ??
    "amazon.com.br,amzn.to,shopee.com.br,mercadolivre.com.br,mercadolivre.com";
}

export function getImageHosts(input: EnvInput = process.env): string {
  return rawEnvSchema.parse(input).PRODUCT_IMAGE_ALLOWED_HOSTS ?? "";
}

export function getSyncSecret(input: EnvInput = process.env): string {
  const secret = rawEnvSchema.parse(input).CATALOG_SYNC_SECRET;
  if (!secret || Buffer.byteLength(secret, "utf8") < 32) {
    throw new Error("CATALOG_SYNC_SECRET deve ter pelo menos 32 bytes.");
  }
  return secret;
}
