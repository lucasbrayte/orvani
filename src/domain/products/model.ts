export const partners = ["amazon", "shopee", "mercado_livre"] as const;
export type Partner = (typeof partners)[number];

export const productTypes = ["fisico", "digital"] as const;
export type ProductType = (typeof productTypes)[number];

export const stockStatuses = ["disponivel", "indisponivel", "informativo"] as const;
export type StockStatus = (typeof stockStatuses)[number];

export type Product = {
  id: string;
  name: string;
  slug: string;
  category: string;
  type: ProductType;
  shortDescription: string;
  description: string;
  currentPrice: number;
  previousPrice: number | null;
  currency: "BRL";
  primaryImage: string;
  images: string[];
  partner: Partner;
  affiliateUrl: string;
  featured: boolean;
  active: boolean;
  stockStatus: StockStatus;
  tags: string[];
  updatedAt: string;
};

export type PublicProduct = Omit<Product, "affiliateUrl">;

export function toPublicProduct({ affiliateUrl, ...product }: Product): PublicProduct {
  void affiliateUrl;
  return product;
}
