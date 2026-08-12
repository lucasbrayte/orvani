import { InstitutionalPage } from "@/components/institutional/institutional-page";
import { buildPageMetadata } from "@/lib/page-metadata";

export const metadata = buildPageMetadata({
  title: "Política de Privacidade",
  description: "Entenda quais dados mínimos a Orvani trata e por quanto tempo.",
  path: "/privacidade",
});

export default function PrivacyPage() {
  return (
    <InstitutionalPage
      eyebrow="Dados e privacidade"
      title="Política de Privacidade"
      lead="Texto-base para explicar, em linguagem direta, o tratamento mínimo de dados na Orvani."
      sections={[
        {
          title: "Dados tratados",
          content: <><p>Esta versão não possui cadastro, carrinho ou checkout. Ao abrir uma oferta, registramos somente o identificador do produto, parceiro, horário, origem aproximada da navegação e um identificador técnico de sessão quando necessário para limitar abuso.</p><p>Não armazenamos IP bruto, não criamos perfil comportamental e não usamos fingerprinting.</p></>,
        },
        {
          title: "Finalidades e cookies",
          content: <p>As métricas próprias servem para medir cliques anônimos, melhorar a curadoria e proteger os endpoints. Não carregamos analytics externo ou cookies não essenciais nesta versão. Se isso mudar, o recurso dependerá do mecanismo de consentimento aplicável.</p>,
        },
        {
          title: "Retenção e segurança",
          content: <p>Eventos detalhados de clique devem ser agregados e removidos em até 90 dias. Logs administrativos são mantidos somente pelo período necessário à operação. Segredos ficam no servidor e devem ser rotacionados após suspeita de exposição.</p>,
        },
        {
          title: "Seus direitos e contato",
          content: <p>Antes da publicação, será necessário informar um canal oficial do controlador para solicitações de acesso, correção, oposição ou eliminação previstas na legislação brasileira.</p>,
        },
      ]}
      note={<><strong>Revisão necessária</strong><p>Este texto-base deve passar por revisão jurídica profissional e receber os dados oficiais de contato antes da publicação.</p></>}
    />
  );
}
