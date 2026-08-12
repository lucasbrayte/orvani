"use client";

import { useState } from "react";

import { ProductImage } from "./product-image";

export function ProductGallery({ name, images }: { name: string; images: string[] }) {
  const uniqueImages = [...new Set(images.length ? images : ["/images/product-fallback.svg"])];
  const [selected, setSelected] = useState(0);

  return (
    <div className="product-gallery">
      <div className="product-gallery__main">
        <ProductImage src={uniqueImages[selected]} alt={`${name}, imagem ${selected + 1}`} priority sizes="(max-width: 800px) 94vw, 48vw" />
      </div>
      {uniqueImages.length > 1 && (
        <div className="product-gallery__thumbs" aria-label="Galeria de imagens">
          {uniqueImages.map((image, index) => (
            <button type="button" key={image} aria-label={`Mostrar imagem ${index + 1}`} aria-pressed={selected === index} onClick={() => setSelected(index)}>
              <ProductImage src={image} alt="" sizes="5rem" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
