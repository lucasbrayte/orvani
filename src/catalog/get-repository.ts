import { DemoCatalogRepository } from "./demo-repository";
import type { CatalogRepository } from "./repository";
import { SupabaseCatalogRepository } from "./supabase-repository";
import { getRuntimeEnv } from "@/config/env";

let repository: CatalogRepository | undefined;

export function getCatalogRepository(): CatalogRepository {
  if (repository) return repository;
  const env = getRuntimeEnv();
  repository = env.catalogMode === "supabase" ? new SupabaseCatalogRepository() : new DemoCatalogRepository();
  return repository;
}
