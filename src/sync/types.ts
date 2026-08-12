import type { Product } from "@/domain/products/model";

export type RowRejection = {
  row: number;
  id?: string;
  code: "INVALID_ROW";
  fields: string[];
};

export type ParsedSheet = {
  valid: Product[];
  rejected: RowRejection[];
  preservedIds: string[];
  rowsRead: number;
};

export interface SheetReader {
  read(): Promise<string[][]>;
}

export interface CatalogSyncRepository {
  beginSync(): Promise<string>;
  failSync(runId: string, code: string): Promise<void>;
  applySnapshot(input: {
    runId: string;
    products: Product[];
    preservedIds: string[];
    rowsRead: number;
    rejected: number;
    errors: RowRejection[];
  }): Promise<{ inserted: number; updated: number; deactivated: number }>;
}

export type SyncLogger = {
  info(event: string, details: Record<string, number | string>): void;
  error(event: string, details: Record<string, number | string>): void;
};

export type CatalogSyncDependencies = {
  reader: SheetReader;
  repository: CatalogSyncRepository;
  imageHosts: readonly string[];
  affiliateHosts: readonly string[];
  logger: SyncLogger;
};

export type SyncResult = {
  status: "success" | "partial" | "failed";
  read: number;
  imported: number;
  updated: number;
  rejected: number;
  deactivated: number;
  errorCode?: "CATALOG_SYNC_FAILED" | "SYNC_START_FAILED";
};
