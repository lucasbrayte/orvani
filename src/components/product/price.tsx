import { calculateDiscount } from "@/domain/products/normalizers";
import { formatCurrency } from "@/lib/format";

type PriceProps = { current: number; previous: number | null };

export function Price({ current, previous }: PriceProps) {
  const discount = calculateDiscount(current, previous);
  return (
    <div className="price-block">
      <div>
        <strong>{formatCurrency(current)}</strong>
        {previous !== null && <del>{formatCurrency(previous)}</del>}
      </div>
      {discount !== null && <span className="discount-badge">−{discount}%</span>}
    </div>
  );
}
