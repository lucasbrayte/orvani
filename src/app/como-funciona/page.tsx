import { InstitutionalPage } from "@/components/institutional/institutional-page";
import { buildPageMetadata } from "@/lib/page-metadata";

export const metadata = buildPageMetadata({
  title: "Como funciona",
  description: "Entenda como pesquisar, comparar e abrir ofertas pela Orvani.",
  path: "/como-funciona",
});

export default function HowItWorksPage() {
  return (
    <InstitutionalPage
      eyebrow="Passo a passo"
      title="Como funciona"
      lead="A Orvani ajuda na descoberta; a loja parceira cuida de toda a compra."
      sections={[
        {
          title: "1. Pesquise e filtre",
          content: <p>Use a busca, categorias, tipo de produto, parceiro e faixa de preço para encontrar itens do catálogo. Os filtros ficam no endereço da página para você compartilhar ou retomar a pesquisa.</p>,
        },
        {
          title: "2. Confira as informações",
          content: <p>A página do produto mostra descrição, preço registrado, parceiro e data da última atualização. Não exibimos avaliações, estoque ou urgência sem uma fonte editorial válida.</p>,
        },
        {
          title: "3. Visite a loja parceira",
          content: <p>O botão “Ver oferta” passa por uma rota protegida da Orvani e abre somente um domínio parceiro previamente autorizado. Confirme preço, disponibilidade, frete e condições no destino antes de comprar.</p>,
        },
      ]}
      note={<><strong>Importante</strong><p>A Orvani não recebe pagamentos nem oferece carrinho ou checkout.</p></>}
    />
  );
}
