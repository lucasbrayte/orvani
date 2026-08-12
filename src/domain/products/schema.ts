import { z } from "zod";

import { partners, productTypes, stockStatuses } from "./model";

const safeText = z.string().trim().min(1).max(5_000);

const productObjectSchema = z.object({
  id: z.string().trim().min(1).max(120).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/),
  name: safeText.max(180),
  slug: z.string().min(1).max(180).regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  category: safeText.max(80),
  type: z.enum(productTypes),
  shortDescription: safeText.max(280),
  description: safeText,
  currentPrice: z.number().finite().positive(),
  previousPrice: z.number().finite().positive().nullable(),
  currency: z.literal("BRL"),
  primaryImage: z.string().trim().min(1).max(2_048),
  images: z.array(z.string().trim().min(1).max(2_048)).max(12),
  partner: z.enum(partners),
  affiliateUrl: z.string().trim().min(1).max(2_048),
  featured: z.boolean(),
  active: z.boolean(),
  stockStatus: z.enum(stockStatuses),
  tags: z.array(z.string().trim().min(1).max(80)).max(30),
  updatedAt: z.iso.datetime({ offset: true }),
});

export const productSchema = productObjectSchema.superRefine((product, context) => {
  if (product.previousPrice !== null && product.previousPrice <= product.currentPrice) {
    context.addIssue({
      code: "custom",
      path: ["previousPrice"],
      message: "O preço anterior deve ser maior que o preço atual.",
    });
  }
});

export const publicProductSchema = productObjectSchema
  .omit({ affiliateUrl: true })
  .superRefine((product, context) => {
    if (product.previousPrice !== null && product.previousPrice <= product.currentPrice) {
      context.addIssue({
        code: "custom",
        path: ["previousPrice"],
        message: "O preço anterior deve ser maior que o preço atual.",
      });
    }
  });
