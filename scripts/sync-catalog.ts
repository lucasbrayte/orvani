import { loadEnvFile } from "node:process";

import { SupabaseAdminCatalogRepository } from "@/catalog/admin-repository";
import { getAffiliateHosts, getImageHosts, getSheetsEnv } from "@/config/env";
import { GoogleSheetsReader } from "@/integrations/google/sheets";
import { parseAllowedHosts } from "@/security/external-url";
import { synchronizeCatalog } from "@/sync/catalog-sync";

try {
  loadEnvFile(".env.local");
} catch (error) {
  if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
}

async function main() {
  const imageHostConfig = getImageHosts();
  if (!imageHostConfig) throw new Error("PRODUCT_IMAGE_ALLOWED_HOSTS não está configurada.");

  const result = await synchronizeCatalog({
    reader: new GoogleSheetsReader(getSheetsEnv()),
    repository: new SupabaseAdminCatalogRepository(),
    imageHosts: parseAllowedHosts(imageHostConfig),
    affiliateHosts: parseAllowedHosts(getAffiliateHosts()),
    logger: {
      info: (event, details) => console.log(JSON.stringify({ event, ...details })),
      error: (event, details) => console.error(JSON.stringify({ event, ...details })),
    },
  });

  console.log(JSON.stringify(result));
  if (result.status === "failed") process.exitCode = 1;
}

main().catch(() => {
  console.error(JSON.stringify({ status: "failed", code: "CONFIGURATION_ERROR" }));
  process.exitCode = 1;
});
