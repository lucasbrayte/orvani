# Orvani

**Boas escolhas em um só lugar.**

A Orvani é uma vitrine brasileira de produtos físicos e digitais. Ela apresenta itens cadastrados editorialmente e direciona o visitante à Amazon, Shopee ou Mercado Livre por links de afiliado. A Orvani não vende produtos, não processa pagamentos e não responde por estoque, checkout, entrega ou garantia da loja parceira.

O repositório inclui uma experiência completa em modo de demonstração, com dados e imagens locais fictícios, além das integrações server-side para Supabase e Google Sheets. Nenhum serviço foi publicado ou provisionado por este projeto.

## Stack e requisitos

- Next.js 16 com App Router, React 19 e TypeScript estrito;
- Tailwind CSS 4, Embla Carousel e componentes acessíveis próprios;
- Supabase/PostgreSQL para catálogo, histórico de sincronização e cliques anônimos;
- Google Sheets API somente no servidor, com escopo de leitura;
- Zod, Vitest, Playwright e axe-core;
- Node.js 22 ou superior e npm.

## Executar localmente

```bash
npm install
```

No PowerShell, copie o modelo de ambiente:

```powershell
Copy-Item .env.example .env.local
```

Para conhecer a interface sem credenciais, defina `CATALOG_DATA_MODE=demo` em `.env.local` e execute:

```bash
npm run dev
```

A aplicação estará em `http://localhost:3000`. O modo de desenvolvimento também assume o catálogo de demonstração quando o Supabase não está configurado. Em produção, `NEXT_PUBLIC_SITE_URL` é obrigatória e o modo deve ser `supabase` ou `demo` explicitamente.

## Variáveis de ambiente

O arquivo [`.env.example`](./.env.example) contém somente nomes, comentários e valores vazios. Não versione `.env.local` ou credenciais reais.

| Variável | Uso |
| --- | --- |
| `CATALOG_DATA_MODE` | `demo` ou `supabase`; seleciona a fonte do catálogo. |
| `NEXT_PUBLIC_SITE_URL` | Origem canônica; deve usar HTTPS em produção. |
| `SUPABASE_URL` | URL HTTPS do projeto Supabase. |
| `SUPABASE_PUBLISHABLE_KEY` | Chave publicável usada pelo repositório server-side de leitura. |
| `SUPABASE_SECRET_KEY` | Credencial administrativa exclusivamente server-side. |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | ID da planilha privada. |
| `GOOGLE_SHEETS_RANGE` | Faixa da aba, recomendada: `produtos!A:S`. |
| `GOOGLE_SERVICE_ACCOUNT_EMAIL` | E-mail da conta de serviço com acesso de visualizador. |
| `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY` | Chave privada PEM; aceita quebras escapadas como `\n`. |
| `CATALOG_SYNC_SECRET` | Segredo forte de pelo menos 32 bytes para a rota de sincronização. |
| `AFFILIATE_ALLOWED_HOSTS` | Allowlist de hosts de destino separados por vírgula. |
| `PRODUCT_IMAGE_ALLOWED_HOSTS` | Allowlist de hosts de imagens separados por vírgula. |

Não existe `CLICK_HASH_SECRET`: a versão atual não coleta IP, identificador de dispositivo ou qualquer dado que exija esse hash.

## Configurar o Supabase

1. Crie um projeto no Supabase e guarde URL, publishable key e secret key em um gerenciador de segredos do ambiente de hospedagem.
2. Aplique a migration [`supabase/migrations/202608110001_orvani_catalog.sql`](./supabase/migrations/202608110001_orvani_catalog.sql) pelo SQL Editor do painel ou com a Supabase CLI (`supabase link` e `supabase db push`). Revise o destino antes de aplicar.
3. Preencha as três variáveis `SUPABASE_*` e defina `CATALOG_DATA_MODE=supabase`.
4. Execute `npm run typecheck` e uma sincronização controlada antes de liberar tráfego.

A migration cria `products`, `sync_runs`, `affiliate_clicks` e a tabela agregada `affiliate_click_daily`. RLS fica ativa em todas elas. Clientes públicos podem ler apenas colunas não sensíveis de produtos ativos; o link afiliado, execuções, eventos e funções administrativas não recebem leitura pública. A secret key é necessária para upsert, métricas e manutenção e nunca deve entrar em `NEXT_PUBLIC_*`, componentes Client ou logs.

## Configurar o Google Sheets privado

1. No Google Cloud Console, crie ou selecione um projeto e habilite a **Google Sheets API**.
2. Crie uma conta de serviço dedicada, sem funções adicionais no projeto.
3. Gere uma chave JSON para essa conta e copie somente `client_email` e `private_key` para as variáveis correspondentes. Não versione o JSON.
4. Crie uma planilha privada com uma aba chamada `produtos` e importe [`docs/catalog-template.csv`](./docs/catalog-template.csv).
5. Compartilhe a planilha com o `client_email` da conta de serviço como **Visualizador**.
6. Configure o ID da planilha e `GOOGLE_SHEETS_RANGE=produtos!A:S`.

O cliente usa exclusivamente o escopo `spreadsheets.readonly`. A planilha nunca é lida no navegador. A chave privada pode ser armazenada em uma única linha com `\n`; o adaptador restaura as quebras somente em memória e não imprime o conteúdo.

### Contrato da aba `produtos`

O cabeçalho deve conter exatamente, sem colunas extras:

```text
id,nome,slug,categoria,tipo,descricao_curta,descricao,preco_atual,preco_anterior,moeda,imagem_principal,imagens,loja,link_afiliado,destaque,ativo,estoque_status,tags,data_atualizacao
```

Regras editoriais:

- `id`: estável e único, iniciado por letra ou número e composto por letras, números, `.`, `_` ou `-`;
- `tipo`: `fisico` ou `digital`; `moeda`: `BRL`;
- `loja`: `amazon`, `shopee` ou `mercado_livre`;
- `estoque_status`: `disponivel`, `indisponivel` ou `informativo`; ele não cria uma promessa de estoque;
- preços: use `129.90` ou `129,90`; milhares no padrão brasileiro, como `1.299,90`, também são aceitos. Símbolos, `1,299.90`, casas decimais ausentes e formatos ambíguos são rejeitados;
- `preco_anterior`: deixe vazio quando não existir; quando informado, deve ser maior que o preço atual;
- `imagens`: prefira um array JSON de URLs, como `["https://cdn.example/imagem-1.webp"]`; URLs separadas por `|` também são aceitas;
- `tags`: prefira um array JSON de textos, como `["audio","casa"]`; textos separados por `|` também são aceitos;
- `destaque` e `ativo`: `true`/`false`, `sim`/`não` ou `1`/`0`;
- `imagem_principal`, cada item de `imagens` e `link_afiliado`: URL HTTPS em host autorizado, sem credenciais ou porta customizada;
- `data_atualizacao`: data ISO 8601 com fuso, por exemplo `2026-08-12T12:00:00-03:00`;
- descrições são tratadas como texto simples; HTML da planilha não é interpretado.

A linha incluída no CSV é explicitamente fictícia e não representa produto, preço ou link afiliado real. Substitua-a e autorize `images.example.com` apenas se realmente usar esse host em um ambiente de teste.

## Sincronização do catálogo

Com Supabase, Google Sheets, hosts de imagens e hosts afiliados configurados:

```bash
npm run sync:catalog
```

O fluxo lê, valida e normaliza as linhas; registra uma execução; e faz upsert idempotente por `id`. Uma linha inválida é rejeitada com número, ID reconhecível, código e campos afetados, sem dados ou segredos. IDs reconhecíveis de linhas rejeitadas são preservados. Itens ausentes só são desativados após uma leitura completa com cabeçalho válido e aplicação transacional do snapshot; falha de leitura, parsing estrutural ou persistência mantém o último catálogo válido.

Para cron, envie um `POST` para `/api/internal/sync` com o segredo apenas no cabeçalho:

```bash
curl --request POST \
  --header "Authorization: Bearer $CATALOG_SYNC_SECRET" \
  https://seu-dominio.example/api/internal/sync
```

Nunca use o segredo na query string. A comparação é feita em tempo constante e a resposta omite detalhes internos. O limite atual é de 6 tentativas a cada 10 minutos por instância. Em hospedagem com múltiplas instâncias, configure também rate limiting compartilhado no provedor ou em um armazenamento dedicado. Agende o cron no painel do provedor somente depois de cadastrar os segredos; este repositório não cria a agenda nem faz deploy.

## Links afiliados e imagens

Todos os CTAs usam `/go/[productId]`. O servidor consulta um produto ativo, recupera a URL armazenada, valida com `URL`, exige HTTPS, bloqueia credenciais, portas e hosts codificados, registra o clique mínimo e emite redirecionamento temporário `307`. Nenhuma URL enviada pelo visitante é aceita.

`AFFILIATE_ALLOWED_HOSTS` aceita hosts separados por vírgula, sem `https://`, caminho, porta, curingas ou IP. A comparação permite apenas o host exato ou um subdomínio real delimitado por ponto. Exemplos iniciais conservadores:

```text
amazon.com.br,amzn.to,shopee.com.br,mercadolivre.com.br,mercadolivre.com
```

Esses exemplos não são uma lista universal. Cadastre somente domínios observados em links oficiais gerados na sua conta, valide a política vigente de cada programa e acrescente testes antes de incluir outro parceiro ou encurtador. O mesmo formato vale para `PRODUCT_IMAGE_ALLOWED_HOSTS`; o host deve constar também na configuração do pipeline de imagens do Next.js, que é gerada a partir dessa variável.

## Privacidade, métricas e retenção

A versão atual não tem conta, carrinho, checkout, cookies analíticos, fingerprinting nem analytics externo. Cada clique registra apenas `product_id`, parceiro e horário. IP bruto, user agent e referer não são armazenados.

A política proposta mantém eventos brutos por 90 dias. Depois disso, a função `aggregate_and_prune_affiliate_clicks` agrega contagens diárias e remove os eventos antigos na mesma execução. Agende-a com uma credencial de serviço em um job protegido, por exemplo:

```sql
select public.aggregate_and_prune_affiliate_clicks(now() - interval '90 days');
```

Revise a necessidade e o prazo de retenção com a assessoria jurídica antes da publicação. Se cookies não essenciais ou analytics externo forem adicionados, eles devem permanecer desativados até consentimento adequado.

## Segurança

Controles implementados incluem validação Zod de ambiente e payload editorial, RLS e privilégios mínimos, consultas pelo cliente oficial, URLs externas em allowlist, rota administrativa autenticada, erros seguros, CSP com nonce sem `unsafe-inline`, HSTS em produção, proteção contra framing, `nosniff`, Referrer Policy e Permissions Policy. `unsafe-eval` existe somente no CSP de desenvolvimento por exigência do bundler; não é emitido em produção.

### Threat model resumido

| Ameaça | Controles | Risco residual / operação |
| --- | --- | --- |
| Vazamento de segredos | Variáveis server-only, `.env*` ignorado, respostas e logs sem tokens. | A plataforma de hospedagem e acessos administrativos ainda precisam de hardening e auditoria. |
| Open redirect | Destino vem do banco por ID e passa por parser nativo, HTTPS e allowlist exata/subdomínio. | Um domínio autorizado comprometido continua sendo confiável; mantenha a lista mínima. |
| XSS pela planilha | Descrições são texto React, schema limita conteúdo e nenhuma linha é renderizada como HTML. | URLs de imagens seguem sendo conteúdo remoto; controle e monitore os hosts. |
| SSRF e URLs externas | IPs, portas, credenciais, HTTP, hostname codificado e host fora da lista são bloqueados. | O otimizador de imagens acessa hosts autorizados; não use hosts que aceitem URLs arbitrárias/proxy. |
| Abuso de endpoints | Segredo forte, `POST`, comparação constante, no-store e rate limit. | O limite em memória não é global; adote controle distribuído no provedor. |
| Envenenamento do catálogo | Planilha privada, conta somente leitura, validação por linha, IDs estáveis e snapshot transacional. | Uma conta Google/editor comprometido pode inserir dados válidos porém maliciosos; revise acessos e execuções. |
| Exposição de métricas | RLS, sem grants públicos e acesso administrativo server-side. | A secret key comprometida permite acesso; rotacione e investigue imediatamente. |

A CSP usa nonce por requisição e, por isso, as páginas passam pelo proxy dinâmico. Essa escolha prioriza uma política de scripts estrita; meça o efeito no cache e no Core Web Vitals no ambiente real antes de alterar a estratégia.

### Rotação de credenciais

1. Gere a nova credencial no provedor sem remover a antiga.
2. Atualize o segredo no ambiente e faça um deploy controlado.
3. Teste leitura, sincronização e redirecionamento sem registrar o valor.
4. Revogue a credencial antiga e revise logs de auditoria.

Para `CATALOG_SYNC_SECRET`, use valor aleatório novo com pelo menos 32 bytes e atualize o cron no mesmo intervalo de manutenção. Para a conta Google, crie uma chave nova, troque `GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY` e revogue a chave anterior. Para Supabase, siga o procedimento atual do painel para rotação da secret key e verifique todos os consumidores server-side.

## Qualidade e verificação

```bash
npm run lint
npm run typecheck
npm test
npm run test:e2e
npm run build
npm audit
```

Os testes cobrem normalização de preço, booleano, lista, slug, desconto, ambiente, headers, URLs adversariais, parser por linha, sincronização parcial/falha/idempotência, rota administrativa, redirecionamento, catálogo, produto, teclado, estados vazios, responsividade e acessibilidade automatizada nas páginas principais. O Playwright usa uma única worker para evitar instabilidade observada no servidor de desenvolvimento do Next.js sobre Windows/OneDrive.

Lighthouse não foi automatizado neste repositório e nenhuma pontuação é prometida. Faça medições em uma build publicada no ambiente final, com rede e imagens reais, e registre os resultados antes do lançamento.

## SEO, conteúdo e publicação

A aplicação inclui metadata por página, canonical, Open Graph, `robots.txt`, sitemap, imagem social e JSON-LD de catálogo/produto. Os dados estruturados não declaram a Orvani como vendedora nem inventam avaliação ou disponibilidade.

Antes de publicar:

1. substitua todos os dados fictícios e valide direitos de uso das imagens e textos;
2. cadastre links de afiliado reais gerados nas contas aprovadas;
3. revise allowlists e políticas atuais de cada programa;
4. contrate revisão jurídica da Política de Privacidade, Termos de Uso e Transparência de Afiliados;
5. execute todos os comandos de qualidade, uma auditoria operacional do Supabase e Lighthouse no ambiente final;
6. configure segredos, cron, observabilidade sem PII, retenção e alertas no provedor escolhido.

É possível hospedar o projeto em provedores compatíveis com Next.js e executar o banco no Supabase. O deploy, o domínio, o cron e quaisquer recursos externos devem ser criados somente com autorização explícita.
