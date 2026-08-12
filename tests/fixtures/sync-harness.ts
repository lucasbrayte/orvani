import type { Product } from "@/domain/products/model";
import type { CatalogSyncDependencies, CatalogSyncRepository } from "@/sync/types";

import { makeProduct } from "./products";
import { header, validRow } from "./sheets";

function rowWith(overrides: Record<number, string>): string[] {
  const row = [...validRow];
  for (const [index, value] of Object.entries(overrides)) row[Number(index)] = value;
  return row;
}

const namedSnapshots: Record<string, string[][]> = {
  "one-valid-one-invalid": [
    [...header],
    rowWith({ 0: "valid", 1: "Produto Válido", 2: "produto-valido" }),
    rowWith({ 0: "invalid-old", 1: "Produto Inválido", 2: "produto-invalido", 9: "USD" }),
  ],
  "valid-snapshot": [
    [...header],
    rowWith({ 0: "snapshot-a", 1: "Produto A", 2: "produto-a" }),
    rowWith({ 0: "snapshot-b", 1: "Produto B", 2: "produto-b", 7: "99.90", 8: "" }),
  ],
};

class MemorySyncStore implements CatalogSyncRepository {
  private readonly products = new Map<string, Product>();
  private runSequence = 0;

  constructor(existingIds: string[]) {
    for (const id of existingIds) {
      this.products.set(id, makeProduct({ id, slug: id, name: `Produto ${id}` }));
    }
  }

  async beginSync(): Promise<string> {
    this.runSequence += 1;
    return `run-${this.runSequence}`;
  }

  async failSync(): Promise<void> {}

  async applySnapshot(input: {
    products: Product[];
    preservedIds: string[];
  }): Promise<{ inserted: number; updated: number; deactivated: number }> {
    let inserted = 0;
    let updated = 0;
    let deactivated = 0;
    const incoming = new Set(input.products.map((product) => product.id));
    const preserved = new Set(input.preservedIds);

    for (const product of input.products) {
      const existing = this.products.get(product.id);
      if (!existing) inserted += 1;
      else if (JSON.stringify(existing) !== JSON.stringify(product)) updated += 1;
      this.products.set(product.id, product);
    }

    for (const [id, product] of this.products) {
      if (product.active && !incoming.has(id) && !preserved.has(id)) {
        this.products.set(id, { ...product, active: false });
        deactivated += 1;
      }
    }
    return { inserted, updated, deactivated };
  }

  activeIds(): string[] {
    return [...this.products.values()]
      .filter((product) => product.active)
      .map((product) => product.id)
      .sort();
  }

  uniqueProductCount(): number {
    return this.products.size;
  }
}

export function createMemorySyncHarness(options: { existingIds?: string[] } = {}) {
  const store = new MemorySyncStore(options.existingIds ?? []);
  const base = {
    repository: store,
    imageHosts: ["images.example.com"],
    affiliateHosts: ["amazon.com.br"],
    logger: { info: () => undefined, error: () => undefined },
  };

  return {
    store,
    withRows(name: keyof typeof namedSnapshots): CatalogSyncDependencies {
      return {
        ...base,
        reader: { read: async () => structuredClone(namedSnapshots[name]) },
      };
    },
    withReadError(error: Error): CatalogSyncDependencies {
      return {
        ...base,
        reader: { read: async () => Promise.reject(error) },
      };
    },
  };
}
