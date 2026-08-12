"use client";

import Image from "next/image";
import { useState } from "react";

type ProductImageProps = {
  src: string;
  alt: string;
  priority?: boolean;
  sizes?: string;
};

export function ProductImage({ src, alt, priority = false, sizes }: ProductImageProps) {
  const [source, setSource] = useState(src || "/images/product-fallback.svg");
  return (
    <Image
      src={source}
      alt={alt}
      fill
      preload={priority}
      sizes={sizes ?? "(max-width: 680px) 86vw, (max-width: 1100px) 42vw, 25vw"}
      onError={() => setSource("/images/product-fallback.svg")}
    />
  );
}
