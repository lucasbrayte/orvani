import { ZodError } from "zod";

import type { Partner, Product, ProductType, StockStatus } from "@/domain/products/model";
import { normalizeSlug, parseBoolean, parseList, parsePrice } from "@/domain/products/normalizers";
import { productSchema } from "@/domain/products/schema";
import { validateExternalUrl } from "@/security/external-url";

import type { ParsedSheet, RowRejection } from "./types";

export const PRODUCT_HEADERS = [
  "id",
  "nome",
  "slug",
  "categoria",
  "tipo",
  "descricao_curta",
  "descricao",
  "preco_atual",
  "preco_anterior",
  "moeda",
  "imagem_principal",
  "imagens",
  "loja",
  "link_afiliado",
  "destaque",
  "ativo",
  "estoque_status",
  "tags",
  "data_atualizacao",
] as const;

type ProductHeader = (typeof PRODUCT_HEADERS)[number];

const pathToHeader: Record<keyof Product, ProductHeader> = {
  id: "id",
  name: "nome",
  slug: "slug",
  category: "categoria",
  type: "tipo",
  shortDescription: "descricao_curta",
  description: "descricao",
  currentPrice: "preco_atual",
  previousPrice: "preco_anterior",
  currency: "moeda",
  primaryImage: "imagem_principal",
  images: "imagens",
  partner: "loja",
  affiliateUrl: "link_afiliado",
  featured: "destaque",
  active: "ativo",
  stockStatus: "estoque_status",
  tags: "tags",
  updatedAt: "data_atualizacao",
};

class RowFieldError extends Error {
  constructor(readonly fields: ProductHeader[]) {
    super("Linha inválida.");
  }
}

function parseField<T>(field: ProductHeader, parser: () => T): T {
  try {
    return parser();
  } catch {
    throw new RowFieldError([field]);
  }
}

function stableId(value: string): string | undefined {
  const id = value.trim();
  return /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(id) ? id : undefined;
}

function rowFields(row: string[], indexes: Map<ProductHeader, number>): Record<ProductHeader, string> {
  return Object.fromEntries(
    PRODUCT_HEADERS.map((header) => [header, row[indexes.get(header)!]?.trim() ?? ""]),
  ) as Record<ProductHeader, string>;
}

function parseProduct(
  fields: Record<ProductHeader, string>,
  imageHosts: readonly string[],
  affiliateHosts: readonly string[],
): Product {
  const currentPrice = parseField("preco_atual", () => parsePrice(fields.preco_atual));
  if (currentPrice === null) throw new RowFieldError(["preco_atual"]);

  const previousPrice = parseField("preco_anterior", () => parsePrice(fields.preco_anterior));
  const imageList = parseField("imagens", () => parseList(fields.imagens));
  const primaryImage = parseField("imagem_principal", () =>
    validateExternalUrl(fields.imagem_principal, imageHosts).href,
  );
  const images = imageList.map((image) =>
    parseField("imagens", () => validateExternalUrl(image, imageHosts).href),
  );
  const affiliateUrl = parseField("link_afiliado", () =>
    validateExternalUrl(fields.link_afiliado, affiliateHosts).href,
  );

  try {
    return productSchema.parse({
      id: fields.id,
      name: fields.nome,
      slug: normalizeSlug(fields.slug),
      category: fields.categoria,
      type: fields.tipo as ProductType,
      shortDescription: fields.descricao_curta,
      description: fields.descricao,
      currentPrice,
      previousPrice,
      currency: fields.moeda,
      primaryImage,
      images,
      partner: fields.loja as Partner,
      affiliateUrl,
      featured: parseField("destaque", () => parseBoolean(fields.destaque)),
      active: parseField("ativo", () => parseBoolean(fields.ativo)),
      stockStatus: fields.estoque_status as StockStatus,
      tags: parseField("tags", () => parseList(fields.tags)),
      updatedAt: fields.data_atualizacao,
    });
  } catch (error) {
    if (error instanceof RowFieldError) throw error;
    if (error instanceof ZodError) {
      const fields = error.issues
        .map((issue) => pathToHeader[issue.path[0] as keyof Product])
        .filter((field): field is ProductHeader => Boolean(field));
      throw new RowFieldError([...new Set(fields)]);
    }
    throw new RowFieldError([]);
  }
}

function validateHeader(rawHeader: string[]): Map<ProductHeader, number> {
  const header = rawHeader.map((value) => value.trim());
  if (new Set(header).size !== header.length) {
    throw new Error("O cabeçalho contém coluna duplicada.");
  }

  const missing = PRODUCT_HEADERS.filter((required) => !header.includes(required));
  const extras = header.filter((column) => column && !PRODUCT_HEADERS.includes(column as ProductHeader));
  if (missing.length || extras.length || header.length !== PRODUCT_HEADERS.length) {
    throw new Error("Cabeçalho da planilha inválido.");
  }

  return new Map(PRODUCT_HEADERS.map((required) => [required, header.indexOf(required)]));
}

export function parseSheet(
  rows: string[][],
  imageHosts: readonly string[],
  affiliateHosts: readonly string[],
): ParsedSheet {
  if (rows.length === 0) throw new Error("Cabeçalho da planilha ausente.");
  const indexes = validateHeader(rows[0]);
  const dataRows = rows.slice(1).filter((row) => row.some((cell) => cell.trim() !== ""));

  if (dataRows.some((row) => row.slice(PRODUCT_HEADERS.length).some((cell) => cell.trim() !== ""))) {
    throw new Error("A planilha contém dados em coluna não documentada.");
  }

  const valid: Product[] = [];
  const rejected: RowRejection[] = [];
  const preservedIds = new Set<string>();

  dataRows.forEach((row, index) => {
    const values = rowFields(row, indexes);
    const recognizableId = stableId(values.id);
    try {
      valid.push(parseProduct(values, imageHosts, affiliateHosts));
    } catch (error) {
      if (recognizableId) preservedIds.add(recognizableId);
      rejected.push({
        row: index + 2,
        ...(recognizableId ? { id: recognizableId } : {}),
        code: "INVALID_ROW",
        fields: error instanceof RowFieldError ? [...new Set(error.fields)].sort() : [],
      });
    }
  });

  return {
    valid,
    rejected,
    preservedIds: [...preservedIds],
    rowsRead: dataRows.length,
  };
}
