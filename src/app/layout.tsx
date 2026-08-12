import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";

import { siteIdentity } from "@/lib/site";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: `${siteIdentity.name} — ${siteIdentity.slogan}`,
    template: `%s — ${siteIdentity.name}`,
  },
  description:
    "Descubra produtos físicos e digitais em lojas parceiras, com curadoria simples e transparente.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang={siteIdentity.locale} className={`${inter.variable} ${manrope.variable}`}>
      <body>
        <a className="skip-link" href="#conteudo">
          Pular para o conteúdo
        </a>
        <header className="site-shell" aria-label="Cabeçalho principal">
          <a className="wordmark" href="/" aria-label="Orvani, página inicial">
            Orvani
          </a>
        </header>
        <main id="conteudo" tabIndex={-1}>
          {children}
        </main>
        <footer className="site-shell">
          <p>Orvani — boas escolhas em um só lugar.</p>
        </footer>
      </body>
    </html>
  );
}
