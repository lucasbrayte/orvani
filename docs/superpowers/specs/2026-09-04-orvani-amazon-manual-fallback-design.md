# Orvani — Amazon Manual Fallback Design

Data: 2026-09-04

## Objetivo

Adicionar Amazon como parceiro plenamente suportado no fluxo operacional atual da Orvani sem API da Amazon nesta fase. O operador continuará cadastrando o produto no LibreOffice Calc e usando `Modo Atualização = Automático`, como já faz com os outros parceiros. O backend tentará o fluxo automático existente; como não haverá conector/API Amazon nesta versão, uma falha de obtenção de metadados deverá cair em um fallback seguro que publica os dados revisados no Calc.

## Escopo

Esta entrega inclui somente Amazon no fluxo de catálogo. WhatsApp, Product Advertising API, scraping de páginas, geração automática de link afiliado, atualização automática de preço/estoque e qualquer integração autenticada com a Amazon ficam fora desta versão.

## Estado atual relevante

- O frontend já reconhece `amazon`, exibe o rótulo `Amazon` e aceita `amazon.com.br` e `amzn.to` como hosts de afiliado.
- O backend Python ainda não inclui Amazon em `PARTNERS`; atualmente os parceiros backend são Mercado Livre, Shopee, SHEIN e TikTok Shop.
- O cliente LibreOffice ainda valida somente Mercado Livre, Shopee e SHEIN e o dropdown de Plataforma também contém somente esses três.
- Shopee, Mercado Livre e SHEIN já possuem caminhos de fallback que reaproveitam dados revisados do Calc quando a obtenção automática falha.

## Regra operacional aprovada

Para produtos Amazon:

- `Ativo`: `Sim` ou `Não` conforme o produto deve aparecer no catálogo.
- `Publicar`: `Sim` para publicar.
- `Modo Atualização`: `Automático`.
- `Plataforma`: `Amazon`.
- `Link Produto`: URL direta do produto em `amazon.com.br` contendo um ASIN identificável.
- `Link Afiliado`: URL afiliada gerada manualmente pelo operador, podendo usar `amazon.com.br` ou `amzn.to`.
- `Nome`, `Descrição`, `Categoria`, `Subcategoria`, `Tipo`, `Preço Atual`, `Preço Anterior`, `Imagem 1..4` e `Texto Botão`: preenchidos/revisados no Calc conforme necessário.

A primeira versão não promete buscar ou corrigir automaticamente esses campos na Amazon.

## Identidade segura do produto Amazon

O backend deve extrair o ASIN somente da URL direta informada em `Link Produto`. O ASIN é a identidade externa da publicação Amazon nesta versão.

Padrões mínimos aceitos na URL direta:

- `/dp/<ASIN>`
- `/gp/product/<ASIN>`
- `/gp/aw/d/<ASIN>`

O ASIN deve ter exatamente 10 caracteres alfanuméricos ASCII. O parser deve ignorar query string e fragmento para fins de identidade.

`amzn.to` é permitido em `Link Afiliado`, mas não será usado para descobrir identidade nesta versão. Se `Link Produto` não fornecer um ASIN seguro, o fallback deve falhar e o produto não deve ser publicado.

## Configuração do backend

Adicionar `amazon` em `automation.config.PARTNERS` com:

- key: `amazon`
- display name: `Amazon`
- allowed hosts: `amazon.com.br`, `amzn.to`
- `live_verified = False` nesta fase, porque não existe conector automático Amazon validado.

Nenhuma credencial, token, cookie ou segredo Amazon será adicionado.

## Fluxo do backend

Fluxo desejado:

```text
LibreOffice Calc
  -> Apps Script / Importações
  -> pending workflow
  -> registro Amazon em Automático
  -> backend tenta o caminho normal de obtenção
  -> Amazon sem conector/API válido nesta versão
  -> UnsupportedUrlError ou InvalidProductDataError
  -> fallback Amazon valida os dados revisados
  -> ProductSnapshot Amazon
  -> validação/matching/publicação existente
  -> Produtos
  -> site
```

O fallback Amazon deve ser aplicado apenas a registros cuja plataforma canônica seja `amazon` e somente quando a falha for compatível com ausência/metadados inválidos (`UnsupportedUrlError` ou `InvalidProductDataError`). Falhas temporárias de rede não devem ser convertidas silenciosamente em sucesso se o motor atual as classificar como temporárias.

## Fallback Amazon

Criar um helper dedicado, seguindo o padrão dos fallbacks existentes, por exemplo:

```python
_manual_amazon_snapshot(record: ImportRecord, fetched_at: datetime) -> ProductSnapshot
```

Regras:

1. Confirmar que o registro é Amazon.
2. Validar `Link Produto` como URL HTTPS de `amazon.com.br`.
3. Validar `Link Afiliado` como URL HTTPS permitida para Amazon (`amazon.com.br` ou `amzn.to`).
4. Extrair ASIN seguro do `Link Produto`.
5. Exigir `Nome` não vazio.
6. Exigir `Preço Atual` positivo.
7. Se `Preço Anterior` existir, exigir valor positivo e maior que `Preço Atual`.
8. Exigir pelo menos uma imagem HTTPS válida.
9. Reaproveitar os preenchimentos/defaults já aprovados para campos opcionais, sem tornar Amazon mais rígida do que os parceiros atuais.
10. Construir `ProductSnapshot(partner="amazon", external_id=<ASIN>, catalog_id=None, ...)` usando os valores revisados do Calc.

Quando o fallback for usado com sucesso, a mensagem operacional deve indicar claramente:

```text
Produto publicado via fallback manual da Amazon.
```

## Seleção e retry

Um registro Amazon em `Automático` que esteja em estado reprocessável deve continuar elegível se o fallback estiver pronto. Adicionar um helper de readiness equivalente aos parceiros existentes, garantindo que uma linha Amazon anteriormente marcada com erro por ausência de conector possa ser reprocessada após o código novo entrar em produção ou após o operador corrigir campos obrigatórios.

Não alterar a semântica de `Manual` nem `Bloqueado`.

## LibreOffice Calc

Atualizar o cliente local para reconhecer Amazon como plataforma válida:

- normalização canônica: `amazon` -> `Amazon`;
- inferência por host: `amazon.com.br` ou `amzn.to` -> `Amazon`;
- conjunto de plataformas locais válidas inclui `Amazon`;
- dropdown Plataforma passa a ser exatamente:

```text
Mercado Livre;Shopee;SHEIN;Amazon
```

O valor continua trafegando para `Importações` como `Amazon`.

### Atualização do arquivo já existente

A mudança não deve apagar, recriar ou substituir o `Orvani.ods` do usuário. O instalador deve atualizar o cliente local e preservar dados. Se a arquitetura atual não reaplicar validações em um workbook existente automaticamente, o patch deve fornecer uma operação segura/idempotente para atualizar apenas a validação da coluna Plataforma no documento existente, preferencialmente via UNO enquanto o documento estiver aberto ou por uma rotina explícita que preserve todas as células.

É proibido recriar o workbook apenas para adicionar Amazon ao dropdown.

## Frontend

Não reconstruir o frontend. O suporte básico a Amazon já existe. Fazer apenas a mudança de consistência necessária no rodapé/parceiros públicos: quando Amazon estiver oficialmente habilitada no backend, `footerPartnerLabels()` deve incluir Amazon junto de Mercado Livre, SHEIN e Shopee.

A validação de links do frontend deve continuar limitada aos hosts já configurados para Amazon.

## Segurança

- Somente HTTPS.
- Comparação de host por domínio exato ou subdomínio real; não usar `includes()` para validar host.
- Não seguir/redirecionar `amzn.to` para extrair ASIN nesta primeira versão.
- Não fazer scraping da Amazon.
- Não adicionar credenciais Amazon.
- Não confiar em ASIN vindo de campo textual arbitrário; extrair somente da URL direta aceita.
- Não aceitar publicação se a identidade Amazon não puder ser determinada com segurança.
- Não alterar ID Automação, política de deduplicação, persistência em Produtos ou verificações de integridade existentes.

## TDD e testes

A implementação deve começar por testes RED e só então alterar produção.

Cobertura mínima:

### Backend/configuração

- `PARTNERS["amazon"]` existe com rótulo e hosts exatos.
- URLs `amazon.com.br` e `amzn.to` passam na validação de parceiro Amazon.
- host parecido/malicioso não passa.

### Identidade Amazon

- extrai ASIN de `/dp/<ASIN>`.
- extrai ASIN de `/gp/product/<ASIN>`.
- extrai ASIN de `/gp/aw/d/<ASIN>`.
- rejeita ASIN com tamanho/formato inválido.
- rejeita URL sem ASIN.
- não usa `amzn.to` para identidade.

### Fallback Automático

- `UpdateMode.AUTOMATICO` + Amazon + falha de conector compatível -> publica dados do Calc.
- preserva nome, preço, imagem e link afiliado revisados.
- escreve `partner = amazon` em Produtos.
- usa ASIN como `external_id`.
- mensagem é `Produto publicado via fallback manual da Amazon.`.
- sem nome, preço, imagem ou ASIN seguro -> permanece erro e não publica.
- preço anterior inválido -> erro.
- retry/reselection reconhece Amazon quando o fallback está pronto.

### LibreOffice

- normalização de `Amazon` funciona.
- inferência por `amazon.com.br` funciona.
- inferência por `amzn.to` funciona.
- validação local aceita Amazon.
- dropdown contém exatamente Mercado Livre, Shopee, SHEIN e Amazon.
- atualização da validação do workbook existente é idempotente e não altera conteúdo de produtos.

### Frontend

- configuração Amazon continua presente.
- `footerPartnerLabels()` retorna `Mercado Livre`, `SHEIN`, `Shopee`, `Amazon` na ordem aprovada.
- links Amazon continuam validados pelos hosts configurados.

### Regressão

Executar pelo menos:

```text
pytest: suites de config, sync, segurança, LibreOffice, fallbacks Mercado Livre/SHEIN/Shopee, persistência de Produtos
node: tests/js/catalog.test.js e demais testes JS relevantes
bash -n nos scripts de instalação alterados, se houver
git diff --check
```

## Estratégia de entrega em um único patch

O usuário quer um único helper executável. Depois da aprovação desta especificação, a implementação será empacotada em um único patch Python que:

1. verifica branch/estado do Git e não sobrescreve alterações inesperadas;
2. cria uma worktree/branch isolada;
3. grava os testes Amazon primeiro;
4. executa RED e confirma que falha pela ausência do novo comportamento;
5. aplica todas as alterações de produção;
6. executa suites focadas e regressões;
7. executa `git diff --check` e verificações de sintaxe;
8. faz commit da implementação;
9. faz fast-forward da `main`;
10. executa verificação pós-merge;
11. faz `git push origin main`;
12. reinstala/reinicia com segurança o cliente LibreOffice se arquivos locais dele forem alterados;
13. preserva worktree para diagnóstico em caso de falha antes de completar o merge;
14. limpa worktree/branch apenas após sucesso comprovado.

O patch não deve pedir ao usuário para executar vários scripts intermediários.

## Critérios de aceite

A entrega está pronta quando:

- `Amazon` pode ser selecionada/usada no Calc sem erro local;
- salvar uma linha Amazon envia `Plataforma = Amazon` para `Importações`;
- uma linha Amazon com `Modo Atualização = Automático`, dados válidos e links válidos é publicada em `Produtos` usando fallback seguro;
- o produto aparece no site com imagem, preço e link afiliado corretos;
- `amzn.to` pode ser usado como link afiliado;
- `Link Produto` direto fornece um ASIN seguro;
- não há duplicação de produto por reprocessamento idempotente;
- os fluxos Mercado Livre, Shopee e SHEIN continuam verdes;
- nenhum segredo Amazon é necessário;
- o workbook existente e seus dados são preservados.
