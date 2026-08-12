import { InstitutionalPage } from "@/components/institutional/institutional-page";
import { buildPageMetadata } from "@/lib/page-metadata";

export const metadata = buildPageMetadata({
  title: "Termos de Uso",
  description: "Condições gerais para uso informativo do catálogo Orvani.",
  path: "/termos",
});

export default function TermsPage() {
  return (
    <InstitutionalPage
      eyebrow="Condições do serviço"
      title="Termos de Uso"
      lead="A Orvani oferece uma experiência informativa de descoberta e comparação."
      sections={[
        {
          title: "Uso do catálogo",
          content: <p>Você pode navegar, pesquisar, compartilhar páginas e acessar ofertas para uso pessoal e lícito. Tentativas de explorar falhas, sobrecarregar endpoints, contornar limites ou extrair o catálogo de forma abusiva não são permitidas.</p>,
        },
        {
          title: "Informações e links externos",
          content: <p>Buscamos manter o catálogo atualizado, mas preços, disponibilidade e condições podem mudar sem aviso. O clique transfere a navegação para uma loja independente, sujeita aos próprios termos e políticas.</p>,
        },
        {
          title: "Compras e suporte",
          content: <p>A Orvani não participa do contrato de compra. Pagamento, emissão de nota, envio, devolução, garantia e suporte devem ser tratados diretamente com a loja parceira.</p>,
        },
        {
          title: "Alterações",
          content: <p>O catálogo e estes termos podem evoluir. Alterações relevantes devem ser publicadas com data de vigência antes da disponibilização pública do serviço.</p>,
        },
      ]}
      note={<><strong>Revisão necessária</strong><p>Este texto-base não substitui orientação jurídica e deve ser revisado antes da publicação.</p></>}
    />
  );
}
