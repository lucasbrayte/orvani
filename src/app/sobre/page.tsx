import { InstitutionalPage } from "@/components/institutional/institutional-page";
import { buildPageMetadata } from "@/lib/page-metadata";

export const metadata = buildPageMetadata({
  title: "Sobre a Orvani",
  description: "Conheça a proposta de curadoria independente do catálogo Orvani.",
  path: "/sobre",
});

export default function AboutPage() {
  return (
    <InstitutionalPage
      eyebrow="Nossa proposta"
      title="Sobre a Orvani"
      lead="Uma vitrine independente para descobrir produtos físicos e digitais em lojas parceiras."
      sections={[
        {
          title: "Boas escolhas, sem ruído",
          content: <p>A Orvani organiza ofertas de diferentes categorias em uma experiência simples, contemporânea e transparente. A curadoria prioriza informações claras, comparação prática e acesso direto à loja de destino.</p>,
        },
        {
          title: "Uma vitrine, não uma loja",
          content: <p>Não mantemos estoque, não vendemos produtos e não participamos do pagamento, entrega ou garantia. Ao escolher uma oferta, você continua a compra no site da Amazon, Shopee, Mercado Livre ou de outro parceiro identificado.</p>,
        },
        {
          title: "Catálogo em evolução",
          content: <p>Os produtos são revisados e atualizados por uma base editorial própria. Preços e disponibilidade podem mudar entre a atualização do catálogo e a visita à loja parceira.</p>,
        },
      ]}
      note={<><strong>Orvani</strong><p>Boas escolhas em um só lugar.</p></>}
    />
  );
}
