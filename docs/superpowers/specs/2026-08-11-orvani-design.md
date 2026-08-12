# Orvani — especificação de produto e arquitetura

Data: 11 de agosto de 2026

## 1. Objetivo

A Orvani será uma vitrine brasileira de produtos físicos e digitais. O visitante poderá descobrir, pesquisar, filtrar e comparar ofertas publicadas editorialmente. A Orvani não processará pedidos ou pagamentos: o único fluxo comercial terminará em um redirecionamento identificado e validado para Amazon, Shopee ou Mercado Livre.

O primeiro release deve funcionar sem credenciais em modo de demonstração, usando dados e ilustrações locais claramente fictícios. Quando as integrações forem configuradas, o mesmo código deverá ler o catálogo sincronizado no Supabase, importar uma planilha privada do Google Sheets e registrar métricas mínimas de cliques.

## 2. Decisões e alternativas

### Arquitetura escolhida

Será usado Next.js com App Router, TypeScript estrito e Tailwind CSS. O catálogo será acessado por uma interface de repositório com duas implementações:

- `demo`: dados fictícios locais, sem segredos ou serviços externos;
- `supabase`: leitura e escrita server-side em PostgreSQL, com privilégios separados para consultas públicas do catálogo e operações administrativas.

Essa separação deixa desenvolvimento e testes reproduzíveis e permite ativar produção apenas configurando variáveis de ambiente.

### Alternativas descartadas

1. **Supabase obrigatório:** reduz uma implementação de repositório, mas impede execução sem credenciais e torna testes locais mais frágeis.
2. **Catálogo estático ou CSV em produção:** simplifica hospedagem, porém não satisfaz sincronização idempotente, histórico de execuções e métricas operacionais.
3. **SPA puramente client-side:** facilitaria alguns filtros, mas exporia integrações, enfraqueceria SEO e aumentaria JavaScript no navegador.

## 3. Identidade e experiência

### Marca

- Nome: Orvani.
- Slogan: “Boas escolhas em um só lugar.”
- Cores: azul-violeta `#635BFF`, azul-marinho `#0B1020`, branco suave `#F7F8FC` e coral `#FF6B4A` apenas para ofertas e destaques.
- Tipografia: Manrope em títulos e Inter em textos, carregadas por `next/font` para hospedagem local no build, com fallbacks de sistema.
- Logotipo: SVG próprio composto por um “O” geométrico interrompido por dois nós conectados, sugerindo conexão e descoberta. Não utilizará símbolo, wordmark ou geometria copiados de terceiros.

### Direção visual

O visual será editorial e minimalista: fundo claro, áreas de respiro grandes, grid consistente, contornos discretos, sombras suaves e blocos escuros pontuais para contraste. Imagens de demonstração serão ilustrações SVG locais abstratas, com proporção constante, sem marcas de marketplaces ou fotografias copiadas.

### Estrutura de navegação

O cabeçalho fixo conterá logotipo, link para catálogo, categorias principais, busca e menu móvel. O rodapé reunirá explicação de afiliados, navegação institucional e aviso de revisão jurídica.

A home terá hero curto, carrossel acessível de destaques sem autoplay agressivo, atalhos de categoria, “Destaques”, “Novidades”, “Ofertas selecionadas” e uma explicação clara sobre o redirecionamento para lojas parceiras.

O catálogo usará parâmetros de URL como fonte de verdade para consulta, filtros, ordenação e página. O servidor entregará o primeiro resultado; um pequeno Client Component atualizará o formulário e a URL sem transformar a página inteira em código cliente. Os filtros serão categoria, tipo, parceiro, preço mínimo/máximo e ordenação. Paginação numerada manterá links acessíveis e previsíveis.

A página de produto terá galeria, descrição textual, parceiro, preços válidos, desconto calculado no servidor, status informativo, atualização, CTA para `/go/[productId]`, aviso de destino, compartilhamento nativo/WhatsApp/link e produtos relacionados. Não haverá avaliações, contagem regressiva, estoque presumido, prova social ou escassez inventada.

Páginas adicionais: Sobre, Como funciona, Transparência de afiliados, Privacidade, Termos, 404 e estado de produto indisponível. Os textos jurídicos serão bases informativas em português brasileiro e o README exigirá revisão profissional antes da publicação.

## 4. Componentes e limites de módulo

Cada unidade terá uma responsabilidade explícita:

- `src/domain/products`: tipos, schemas, normalização de preços/booleanos, slug, cálculo de desconto, consulta e ordenação;
- `src/catalog`: contrato de repositório, implementação demo e implementação Supabase;
- `src/sync`: leitura do Sheets, parsing de linhas, classificação de erros e orquestração idempotente;
- `src/security`: configuração de hosts, validação de URLs, comparação constante, headers e rate limiting;
- `src/metrics`: registro mínimo de cliques, sem IP bruto;
- `src/components`: componentes de interface pequenos, sem regras de persistência;
- `src/app`: composição de rotas, metadados e handlers HTTP.

Funções de domínio permanecerão puras sempre que possível. Clientes do Google e Supabase serão injetados nos serviços para permitir testes sem rede e para impedir que detalhes de infraestrutura contaminem parsing e regras de negócio.

## 5. Modelo de dados

### `products`

Usará `id` textual estável como chave primária, `slug` único, campos editoriais, preços em `numeric(12,2)`, moeda, arrays de imagens/tags, loja enumerada, URL afiliada, flags de destaque/atividade e timestamp de atualização. `preco_anterior` será nulo quando ausente ou menor/igual ao preço atual; desconto só será exposto quando matematicamente válido.

RLS ficará ativa. O papel anônimo receberá leitura apenas das colunas públicas necessárias e somente para linhas ativas. A coluna `affiliate_url` não será legível publicamente; `/go/[productId]` a buscará com cliente server-only administrativo. Operações de sincronização usarão a chave secreta exclusivamente no servidor.

### `sync_runs`

Registrará status, início/fim, quantidade lida, inserida, atualizada, rejeitada e desativada, além de um resumo JSON seguro de erros. Não armazenará conteúdo da chave privada, tokens, consultas completas ou payloads desnecessários. Não haverá permissão pública.

### `affiliate_clicks`

Registrará identificador do produto, parceiro e instante do clique. Não armazenará IP bruto, user-agent completo, fingerprint ou cookie. A tabela não terá leitura pública. Uma rotina SQL documentada agregará métricas por produto/dia e removerá eventos detalhados após 90 dias.

## 6. Planilha e sincronização

A aba padrão será `produtos`, com as colunas, na ordem documentada:

`id, nome, slug, categoria, tipo, descricao_curta, descricao, preco_atual, preco_anterior, moeda, imagem_principal, imagens, loja, link_afiliado, destaque, ativo, estoque_status, tags, data_atualizacao`

`imagens` e `tags` aceitarão JSON array ou uma lista separada por `|`; o caractere literal `|` dentro de um valor deverá ser representado por JSON. Preços aceitarão apenas formato decimal canônico (`1299.90`) ou formato brasileiro completo (`1.299,90`); formatos ambíguos, símbolos monetários e misturas inválidas serão rejeitados. Booleanos aceitarão um conjunto fechado documentado (`true/false`, `1/0`, `sim/não`).

A Google Sheets API será chamada apenas no servidor com escopo somente leitura. A chave privada será obtida de variável server-only e terá sequências `\n` normalizadas em memória sem qualquer log do valor.

Fluxo de sincronização:

1. criar execução com status `running`;
2. ler cabeçalho e todas as linhas da faixa configurada;
3. rejeitar a execução inteira se leitura, cabeçalho ou integridade global falhar;
4. validar cada linha independentemente e registrar somente razões sanitizadas;
5. executar upsert por `id` em uma transação ou função RPC idempotente;
6. desativar ausentes somente quando a leitura foi integral, o cabeçalho foi válido e não houve erro global; linhas individualmente inválidas preservam o registro anterior correspondente;
7. finalizar contadores e status;
8. preservar o catálogo anterior em qualquer falha total.

Para evitar desativar um produto cuja linha ficou temporariamente inválida, IDs reconhecíveis de linhas rejeitadas entram no conjunto de preservação. IDs ausentes ou inválidos não autorizam desativação por inferência.

Haverá `npm run sync:catalog` e `POST /api/internal/sync`. O endpoint aceitará o segredo somente no header `Authorization: Bearer`, comparará bytes de mesmo tamanho em tempo constante e aplicará limite de tentativas por instância. Em produção distribuída, o README recomendará rate limiting adicional no provedor; essa limitação residual será explícita. Respostas serão genéricas e logs não incluirão segredo ou stack trace.

## 7. Redirecionamento de afiliados

O navegador nunca fornecerá a URL de destino. `/go/[productId]` buscará um produto ativo, recuperará sua URL armazenada e aplicará:

1. parsing com `URL` nativa;
2. protocolo exatamente `https:`;
3. ausência de usuário e senha;
4. ausência de porta explícita inesperada;
5. hostname em minúsculas e sem ponto terminal;
6. correspondência com allowlist por igualdade ou subdomínio delimitado por ponto;
7. rejeição de hostname codificado, domínio parecido e esquemas não HTTPS;
8. registro assíncrono e tolerante a falha da métrica mínima;
9. resposta `307` sem cache para o destino validado.

`AFFILIATE_ALLOWED_HOSTS` conterá hosts exatos separados por vírgula. Exemplos iniciais serão documentados como ponto de partida a confirmar com os links reais: `amazon.com.br`, `amzn.to`, `shopee.com.br`, `mercadolivre.com.br` e `mercadolivre.com`. A lista não será considerada universal. Testes cobrirão domínio semelhante, subdomínio malicioso, credenciais, HTTP, `javascript:`, `data:`, encoding e produto ausente.

Os CTAs e avisos sempre exibirão a loja de destino. Links externos auxiliares usarão `rel="sponsored nofollow noopener noreferrer"` quando aplicável.

## 8. Segurança e privacidade

Variáveis serão validadas por schemas Zod por contexto, no boot ou primeiro uso. Desenvolvimento sem credenciais completas usará demo; produção ou sincronização com configuração parcial falhará de forma segura. Nenhum segredo terá prefixo `NEXT_PUBLIC_`.

URLs de imagens externas serão validadas por HTTPS e allowlist própria configurada no build. Imagens inválidas cairão em placeholder local. Descrições da planilha serão renderizadas apenas como texto; não haverá `dangerouslySetInnerHTML` para conteúdo editorial.

Headers incluirão CSP com nonce para scripts, HSTS somente em produção, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` e `frame-ancestors 'none'`. Se o runtime do Next exigir `unsafe-inline` para estilos gerados, a exceção ficará restrita a `style-src` e será justificada no README; `script-src` não usará `unsafe-eval` ou `unsafe-inline` em produção.

O threat model documentará vazamento de segredos, open redirect, XSS por planilha, URLs externas/SSRF, abuso de endpoints, envenenamento do catálogo e exposição de métricas. Riscos residuais incluirão rate limiting por instância, confiança operacional no editor da planilha, disponibilidade de terceiros e defasagem temporária de preço/estoque. Haverá instruções de rotação para Google, Supabase, sincronização e allowlists.

## 9. SEO, cache e desempenho

Cada rota terá título e descrição próprios, canonical baseado em `NEXT_PUBLIC_SITE_URL`, Open Graph, robots e sitemap. Produtos ativos gerarão JSON-LD `Product` com `Offer` cujo vendedor será a loja parceira; disponibilidade só será incluída quando o status editorial tiver mapeamento inequívoco. Não haverá avaliações ou disponibilidade inventadas.

Páginas e consultas usarão Server Components por padrão. O catálogo terá cache com revalidação temporal e tag; o endpoint de sincronização invalidará a tag ao concluir. O script administrativo dependerá da revalidação temporal quando executado fora do processo web. Imagens usarão dimensões reservadas, `next/image`, prioridade somente acima da dobra e lazy loading no restante.

Client Components ficarão limitados ao menu, carrossel, filtros progressivos e compartilhamento. Animações serão CSS discretas e desativadas ou reduzidas por `prefers-reduced-motion`.

## 10. Acessibilidade

O objetivo é WCAG 2.2 AA: landmarks semânticos, hierarquia de títulos, skip link, foco sempre visível, contraste, labels persistentes, erros associados, status anunciados e teclado completo. O carrossel terá nome acessível, controles explícitos, indicadores, gesto de toque e teclas direcionais sem capturar navegação global. Não haverá autoplay por padrão.

Filtros funcionarão como formulário HTML mesmo sem JavaScript. Estados de carregamento, vazio, falha e ausência de resultados terão mensagens e ações claras. Testes automatizados com Axe complementarão, mas não substituirão, verificações de teclado no Playwright.

## 11. Testes e evidências

Vitest cobrirá preço, booleanos, slug, desconto, parsing de linha, consulta, hosts e URLs adversariais. Testes de integração usarão fakes in-memory para verificar sincronização parcial, falha total, upsert idempotente, preservação do catálogo e regra de desativação.

Playwright cobrirá home, pesquisa, filtros persistidos na URL, página de produto, teclado, estado vazio e redirecionamentos permitido/bloqueado. `@axe-core/playwright` verificará violações automatizáveis nas páginas principais.

Antes da entrega serão executados, com resultados registrados: lint, TypeScript, testes unitários/integrados, E2E, build de produção e auditoria de dependências. Vulnerabilidades serão analisadas individualmente; não haverá upgrade destrutivo automático. Medições Lighthouse só serão declaradas se realmente executadas no ambiente disponível.

## 12. Entregáveis e limites

O repositório conterá aplicação, migrations, template de planilha, `.env.example`, testes, placeholders locais e README em português. O README explicará instalação, Supabase, migrations, conta de serviço Google, compartilhamento como visualizador, allowlists, sincronização, agenda de cron, testes, segurança, retenção, rotação e opções de deploy.

Não fazem parte deste release: cadastro, carrinho, checkout, pagamentos, publicação, compra de serviços, criação automática de projetos externos, analytics de terceiros, cookies não essenciais ou uso de credenciais reais. Configuração e deploy dependentes do usuário serão listados no relatório final.
