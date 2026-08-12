import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";

import { getRuntimeEnv } from "@/config/env";
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
  metadataBase: new URL(getRuntimeEnv().siteUrl),
  title: {
    default: `${siteIdentity.name} — ${siteIdentity.slogan}`,
    template: `%s — ${siteIdentity.name}`,
  },
  description:
    "Descubra produtos físicos e digitais em lojas parceiras, com curadoria simples e transparente.",
  alternates: { canonical: "/" },
  applicationName: siteIdentity.name,
  category: "shopping",
  keywords: ["catálogo", "ofertas", "produtos", "afiliados", "comparação"],
  formatDetection: { telephone: false, address: false, email: false },
  openGraph: {
    type: "website",
    locale: "pt_BR",
    siteName: siteIdentity.name,
    title: `${siteIdentity.name} — ${siteIdentity.slogan}`,
    description:
      "Produtos físicos e digitais selecionados em lojas parceiras, com clareza sobre o destino.",
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteIdentity.name} — ${siteIdentity.slogan}`,
    description:
      "Produtos físicos e digitais selecionados em lojas parceiras, com clareza sobre o destino.",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang={siteIdentity.locale}
      className={`${inter.variable} ${manrope.variable}`}
      data-scroll-behavior="smooth"
    >
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
