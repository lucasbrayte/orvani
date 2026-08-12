import Link from "next/link";

import { Logo } from "@/components/brand/logo";

import { MobileMenu } from "./mobile-menu";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="site-header__brand" href="/" aria-label="Orvani, página inicial">
          <Logo />
        </Link>
        <nav className="desktop-nav" aria-label="Navegação principal">
          <Link href="/catalogo">Catálogo</Link>
          <Link href="/catalogo?tipo=fisico">Produtos físicos</Link>
          <Link href="/catalogo?tipo=digital">Produtos digitais</Link>
        </nav>
        <form className="header-search" action="/catalogo" role="search">
          <label className="sr-only" htmlFor="header-search">
            Buscar produtos
          </label>
          <input id="header-search" name="q" type="search" placeholder="O que você procura?" />
          <button type="submit" aria-label="Buscar">
            <span aria-hidden="true">⌕</span>
          </button>
        </form>
        <MobileMenu />
      </div>
    </header>
  );
}
