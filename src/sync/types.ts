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
