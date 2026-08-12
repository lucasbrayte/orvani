import type { PublicProduct } from "@/domain/products/model";

import { ProductCard } from "./product-card";

export function ProductGrid({ products, label = "Produtos" }: { products: PublicProduct[]; label?: string }) {
  return (
    <div className="product-grid" role="list" aria-label={label}>
      {products.map((product) => (
        <div role="listitem" key={product.id}>
          <ProductCard product={product} />
        </div>
      ))}
    </div>
  );
}
