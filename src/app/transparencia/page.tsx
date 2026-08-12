import { InstitutionalPage } from "@/components/institutional/institutional-page";
import { buildPageMetadata } from "@/lib/page-metadata";

export const metadata = buildPageMetadata({
  title: "Transparência de afiliados",
  description: "Saiba como links de afiliados e comissões ajudam a manter a Orvani.",
  path: "/transparencia",
});

export default function TransparencyPage() {
  return (
    <InstitutionalPage
      eyebrow="Relação com parceiros"
      title="Transparência de afiliados"
      lead="Queremos que você saiba o que acontece quando abre uma oferta."
      sections={[
        {
          title: "Como a Orvani se mantém",
          content: <p>Quando você acessa uma loja por um link identificado, a Orvani pode receber uma comissão caso uma compra elegível seja concluída. Em regra, isso não altera o preço cobrado de você.</p>,
        },
        {
          title: "Responsabilidade pela compra",
          content: <p>A Orvani não vende, não processa pagamentos e não é responsável por estoque, preço final, entrega, troca, garantia ou atendimento. Essas condições pertencem à loja parceira escolhida.</p>,
        },
        {
          title: "Curadoria e atualização",
          content: <p>A possibilidade de comissão não autoriza informações inventadas. Descontos são calculados somente quando existem preços atual e anterior válidos, e a data de atualização fica visível na página do produto.</p>,
        },
      ]}
      note={<><strong>Sempre confira no destino</strong><p>O preço e a disponibilidade válidos são os apresentados pela loja parceira no momento da visita.</p></>}
    />
  );
}
