import type { Partner } from "@/domain/products/model";

const partnerNames: Record<Partner, string> = {
  amazon: "Amazon",
  shopee: "Shopee",
  mercado_livre: "Mercado Livre",
};

export function PartnerBadge({ partner }: { partner: Partner }) {
  return <span className="partner-badge">Na {partnerNames[partner]}</span>;
}

export function partnerName(partner: Partner) {
  return partnerNames[partner];
}
