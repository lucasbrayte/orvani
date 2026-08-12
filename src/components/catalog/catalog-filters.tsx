import Form from "next/form";

import type { CatalogQuery } from "@/domain/products/query";

const partners = [
  ["", "Todas as lojas"],
  ["amazon", "Amazon"],
  ["shopee", "Shopee"],
  ["mercado_livre", "Mercado Livre"],
] as const;

export function CatalogFilters({ query, categories }: { query: CatalogQuery; categories: string[] }) {
  return (
    <aside className="catalog-sidebar" aria-label="Filtros do catálogo">
      <div className="catalog-sidebar__title"><span>Filtros</span><a href="/catalogo">Limpar</a></div>
      <Form className="filter-form" action="/catalogo">
        <div className="filter-field filter-field--search">
          <label htmlFor="catalog-search">Buscar produtos</label>
          <input id="catalog-search" name="q" type="search" defaultValue={query.search} placeholder="Nome, descrição ou tag" />
        </div>
        <div className="filter-field">
          <label htmlFor="category">Categoria</label>
          <select id="category" name="categoria" defaultValue={query.category ?? ""}>
            <option value="">Todas as categorias</option>
            {categories.map((category) => <option value={category} key={category}>{category}</option>)}
          </select>
        </div>
        <fieldset className="filter-field filter-radio">
          <legend>Tipo de produto</legend>
          <label><input type="radio" name="tipo" value="" defaultChecked={!query.type} /><span>Todos</span></label>
          <label><input type="radio" name="tipo" value="fisico" defaultChecked={query.type === "fisico"} /><span>Físico</span></label>
          <label><input type="radio" name="tipo" value="digital" defaultChecked={query.type === "digital"} /><span>Digital</span></label>
        </fieldset>
        <div className="filter-field">
          <label htmlFor="partner">Loja parceira</label>
          <select id="partner" name="loja" defaultValue={query.partner ?? ""}>
            {partners.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select>
        </div>
        <fieldset className="filter-field price-range">
          <legend>Faixa de preço</legend>
          <label><span>Mínimo</span><input name="min" inputMode="decimal" defaultValue={query.minPrice?.toFixed(2)} placeholder="R$ 0,00" /></label>
          <label><span>Máximo</span><input name="max" inputMode="decimal" defaultValue={query.maxPrice?.toFixed(2)} placeholder="R$ 1.000,00" /></label>
        </fieldset>
        <div className="filter-field">
          <label htmlFor="sort">Ordenar por</label>
          <select id="sort" name="ordem" defaultValue={query.sort ?? "relevance"}>
            <option value="relevance">Relevância</option>
            <option value="price_asc">Menor preço</option>
            <option value="discount_desc">Maior desconto</option>
            <option value="recent">Atualização recente</option>
          </select>
        </div>
        <button className="button filter-submit" type="submit">Aplicar filtros <span aria-hidden="true">→</span></button>
      </Form>
    </aside>
  );
}
