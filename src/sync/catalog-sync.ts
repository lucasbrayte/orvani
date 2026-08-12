import { parseSheet } from "./sheet-parser";
import type { CatalogSyncDependencies, SyncResult } from "./types";

const emptyResult: Omit<SyncResult, "status"> = {
  read: 0,
  imported: 0,
  updated: 0,
  rejected: 0,
  deactivated: 0,
};

export async function synchronizeCatalog(
  dependencies: CatalogSyncDependencies,
): Promise<SyncResult> {
  let runId: string;
  try {
    runId = await dependencies.repository.beginSync();
  } catch {
    dependencies.logger.error("catalog_sync_start_failed", { code: "SYNC_START_FAILED" });
    return { status: "failed", ...emptyResult, errorCode: "SYNC_START_FAILED" };
  }

  dependencies.logger.info("catalog_sync_started", { runId });

  try {
    const rows = await dependencies.reader.read();
    const parsed = parseSheet(rows, dependencies.imageHosts, dependencies.affiliateHosts);
    const counts = await dependencies.repository.applySnapshot({
      runId,
      products: parsed.valid,
      preservedIds: parsed.preservedIds,
      rowsRead: parsed.rowsRead,
      rejected: parsed.rejected.length,
      errors: parsed.rejected,
    });
    const status = parsed.rejected.length > 0 ? "partial" : "success";
    const result: SyncResult = {
      status,
      read: parsed.rowsRead,
      imported: counts.inserted,
      updated: counts.updated,
      rejected: parsed.rejected.length,
      deactivated: counts.deactivated,
    };
    dependencies.logger.info("catalog_sync_finished", {
      runId,
      status,
      read: result.read,
      imported: result.imported,
      updated: result.updated,
      rejected: result.rejected,
      deactivated: result.deactivated,
    });
    return result;
  } catch {
    try {
      await dependencies.repository.failSync(runId, "CATALOG_SYNC_FAILED");
    } catch {
      dependencies.logger.error("catalog_sync_finalize_failed", { runId, code: "FINALIZE_FAILED" });
    }
    dependencies.logger.error("catalog_sync_failed", { runId, code: "CATALOG_SYNC_FAILED" });
    return { status: "failed", ...emptyResult, errorCode: "CATALOG_SYNC_FAILED" };
  }
}
