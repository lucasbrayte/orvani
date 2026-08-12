import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";

import { siteIdentity } from "@/lib/site";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

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
        <SiteHeader />
        <main id="conteudo" tabIndex={-1}>
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
