import { DemoCatalogRepository } from "./demo-repository";
import type { CatalogRepository } from "./repository";

let demoRepository: CatalogRepository | undefined;

export function getCatalogRepository(): CatalogRepository {
  demoRepository ??= new DemoCatalogRepository();
  return demoRepository;
}
