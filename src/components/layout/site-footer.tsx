import Link from "next/link";

import { Logo } from "@/components/brand/logo";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__grid">
        <div>
          <Logo className="site-footer__logo" />
          <p>Boas escolhas em um só lugar.</p>
        </div>
        <nav aria-label="Institucional">
          <strong>Orvani</strong>
          <Link href="/sobre">Sobre</Link>
          <Link href="/como-funciona">Como funciona</Link>
          <Link href="/transparencia">Transparência</Link>
        </nav>
        <nav aria-label="Informações legais">
          <strong>Informações</strong>
          <Link href="/privacidade">Privacidade</Link>
          <Link href="/termos">Termos de uso</Link>
        </nav>
        <div className="site-footer__note">
          <strong>Antes de comprar</strong>
          <p>Preço, disponibilidade e condições são definidos pela loja parceira.</p>
        </div>
      </div>
      <div className="site-footer__bottom">
        <span>© {new Date().getFullYear()} Orvani</span>
        <span>Catálogo independente · Brasil</span>
      </div>
    </footer>
  );
}
