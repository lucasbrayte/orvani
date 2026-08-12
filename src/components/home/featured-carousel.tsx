"use client";

import useEmblaCarousel from "embla-carousel-react";
import { useCallback, useEffect, useState } from "react";

import type { PublicProduct } from "@/domain/products/model";
import { ProductCard } from "@/components/product/product-card";

export function FeaturedCarousel({ products }: { products: PublicProduct[] }) {
  const [viewportRef, api] = useEmblaCarousel({ align: "start", containScroll: "trimSnaps" });
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [snapCount, setSnapCount] = useState(products.length);

  const update = useCallback(() => {
    if (!api) return;
    setSelectedIndex(api.selectedScrollSnap());
    setSnapCount(api.scrollSnapList().length);
  }, [api]);

  useEffect(() => {
    if (!api) return;
    update();
    api.on("select", update).on("reInit", update);
    return () => {
      api.off("select", update).off("reInit", update);
    };
  }, [api, update]);

  return (
    <section
      className="featured content-section"
      role="region"
      aria-label="Ofertas em destaque"
      data-index={selectedIndex}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") api?.scrollPrev();
        if (event.key === "ArrowRight") api?.scrollNext();
      }}
    >
      <div className="section-heading">
        <div><span className="section-kicker section-kicker--offer">Em destaque</span><h2>Ofertas que merecem atenção</h2></div>
        <div className="carousel-controls">
          <button type="button" onClick={() => api?.scrollPrev()} disabled={selectedIndex === 0} aria-label="Oferta anterior">←</button>
          <button type="button" onClick={() => api?.scrollNext()} disabled={selectedIndex >= snapCount - 1} aria-label="Próxima oferta">→</button>
        </div>
      </div>
      <div className="embla" ref={viewportRef}>
        <div className="embla__container">
          {products.map((product, index) => (
            <div className="embla__slide" key={product.id} aria-roledescription="slide" aria-label={`${index + 1} de ${products.length}`}>
              <ProductCard product={product} priority={index === 0} />
            </div>
          ))}
        </div>
      </div>
      <div className="carousel-dots" aria-label="Escolher oferta">
        {Array.from({ length: snapCount }, (_, index) => (
          <button key={index} type="button" aria-label={`Ir para oferta ${index + 1}`} aria-current={selectedIndex === index ? "true" : undefined} onClick={() => api?.scrollTo(index)} />
        ))}
      </div>
      <p className="sr-only" aria-live="polite">Oferta {selectedIndex + 1} de {snapCount}</p>
    </section>
  );
}
