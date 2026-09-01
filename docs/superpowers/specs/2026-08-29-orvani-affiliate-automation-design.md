# Automação do catálogo de afiliados da Orvani

**Data:** 29 de agosto de 2026
**Status:** desenho aprovado em conversa, aguardando revisão do documento
**Checkpoint anterior à automação:** `0dd7c88d57df2053b67f12720d8df13f573373de`

## Objetivo

Adicionar ao projeto estático da Orvani uma automação gratuita e controlada para importar e atualizar produtos afiliados a partir de links inseridos em uma aba `Importações` do Google Sheets. O frontend continuará consumindo a aba `Produtos` pela exportação CSV já publicada, sem servidor web, banco de dados, framework ou processo de build.

A automação deve obter somente dados públicos permitidos, preservar o link afiliado original, impedir publicações automáticas sem aprovação humana e manter o último dado válido quando uma consulta falhar.

## Estado inicial preservado

- O site aprovado é composto por `index.html`, `catalogo.html`, `style.css` e `script.js`.
- O ID da planilha é `1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0`.
- A aba `Produtos` é publicada pelo GID `952991100`.
- Os 20 cabeçalhos existentes de `Produtos` permanecerão na mesma ordem.
- A leitura pública inicial encontrou 11 produtos aceitos pelo frontend.
- A linha “Curso Vitrine de Afiliado do Zero” permanece rejeitada porque está declarada como Hotmart e usa `darlanevandro.com.br`, domínio não autorizado para esse parceiro.
- O problema Hotmart será relatado, sem alterar, excluir ou autorizar silenciosamente a linha.

O commit `0dd7c88d57df2053b67f12720d8df13f573373de` registra o estado exato anterior à automação, inclusive os finais de linha CRLF já presentes quando o trabalho começou.

## Escopo

### Incluído

- Pacote Python modular para configuração, validação, importação, atualização e publicação.
- Conectores independentes para Mercado Livre, Shopee, SHEIN e TikTok Shop.
- Extração reutilizável de JSON-LD, Open Graph e metadados públicos.
- Segurança contra SSRF e redirecionamentos não autorizados.
- Integração em lote com Google Sheets por conta de serviço.
- CLI com `setup-sheet`, `sync` e `validate`.
- Workflow manual e agendado no GitHub Actions.
- Testes Python e JavaScript offline por padrão.
- Ajustes focados no adaptador e nos cards do catálogo atual.
- Documentação operacional em português do Brasil.

### Fora do escopo

- Login ou automação de contas de comprador ou afiliado.
- Conversão automática de links pelo painel da Shopee.
- Selenium, Playwright ou emulação de navegador.
- Contorno de CAPTCHA, bloqueio antibot, limitação regional ou autenticação.
- API paga de inteligência artificial.
- Servidor web, banco de dados, frontend Python, npm, bundler ou framework visual.
- Criação de credenciais, contas externas, mudança de permissões ou deploy.
- Escrita na planilha real antes de autorização específica do proprietário.
- Autorização de domínios de loja sem evidência fornecida por uma amostra oficial.

## Arquitetura

O frontend e a automação se comunicam exclusivamente pela aba `Produtos`:

```text
Importações
    -> validação e identificação do parceiro
    -> resolução segura do link
    -> conector da loja
    -> ProductSnapshot normalizado
    -> revisão humana
    -> publicação em lote em Produtos
    -> CSV público existente
    -> script.js
```

O endereço resolvido será usado apenas para identificar o produto e consultar fontes permitidas. O valor escrito em `Link de Afiliado` e usado no botão será sempre o link afiliado original.

### Componentes Python

- `automation/config.py`: ambiente, limites, cabeçalhos, parceiros e categorias configuráveis.
- `automation/models.py`: snapshots, registros de importação, estados, resultados e erros tipados.
- `automation/security.py`: parsing de URL, allowlists, DNS, redirecionamentos e sanitização de logs.
- `automation/http_client.py`: HTTP limitado, tipos de conteúdo, retry e backoff.
- `automation/metadata.py`: extração normalizada de JSON-LD, Open Graph e metatags.
- `automation/categorizer.py`: mapeamento determinístico e regras pequenas de palavras-chave.
- `automation/connectors/base.py`: contrato comum e utilidades de conectores.
- `automation/connectors/*.py`: regras isoladas por loja.
- `automation/sheets.py`: autenticação, leitura, configuração idempotente e escrita em lote.
- `automation/sync.py`: seleção da fila, estados, adoção, publicação e tolerância a falhas.
- `automation/cli.py`: comandos públicos e proteção de `--dry-run`.

Nenhum conector conhecerá detalhes da aba `Produtos`. Nenhum módulo de Sheets interpretará HTML de loja. A sincronização dependerá das interfaces comuns, permitindo testar cada limite com fakes.

## Modelo normalizado

Todos os conectores produzirão um único `ProductSnapshot` imutável contendo, no mínimo:

- parceiro;
- ID externo;
- URL de origem resolvida;
- link afiliado original;
- nome e descrição;
- preço atual e preço anterior com `Decimal`;
- moeda;
- categoria, subcategoria e tipo;
- cupom e validade, quando comprovados;
- até quatro imagens HTTPS únicas;
- disponibilidade opcional;
- instante da coleta.

Preços nunca usarão `float`. Preço anterior igual ou menor que o atual será descartado. O desconto será sempre calculado internamente a partir de preços válidos.

Erros de conector distinguirão URL incompatível, produto não encontrado, falha temporária, bloqueio da loja e dado inválido. A sincronização converterá cada erro em estado e mensagem adequados sem expor parâmetros sensíveis.

## Aba Importações

A aba terá exatamente estes campos na primeira versão:

1. ID Automação
2. Ativo
3. Publicar
4. Destaque
5. Ordem
6. Modo de Atualização
7. Link do Produto
8. Link de Afiliado
9. Plataforma
10. ID Externo
11. Nome
12. Descrição
13. Categoria
14. Subcategoria
15. Tipo
16. Preço Atual
17. Preço Anterior
18. Desconto Calculado
19. Cupom
20. Validade do Cupom
21. Imagem 1
22. Imagem 2
23. Imagem 3
24. Imagem 4
25. Texto do Botão
26. Status
27. Mensagem
28. Tentativas Consecutivas
29. Último Link Publicado
30. Assinatura dos Dados
31. Última Verificação
32. Última Atualização

Novas linhas usarão `Publicar = Não`, `Destaque = Não` e `Modo de Atualização = Automático`. `ID Automação` será gerado uma vez e preservado. Datas serão escritas como datas e preços como números, não como strings formatadas.

`setup-sheet` será idempotente: criará a aba somente se ela não existir; caso exista, validará a estrutura e preservará linhas. Congelamento, filtro, validação de dados e formatação condicional serão auxiliares idempotentes, sem participar da lógica de negócio.

## Estados e transições

Estados permitidos:

- `NOVO`
- `AGUARDANDO CONVERSÃO`
- `PROCESSANDO`
- `REVISAR`
- `PRONTO PARA PUBLICAR`
- `PUBLICADO`
- `ATENÇÃO`
- `ERRO`
- `DESATIVADO`

Fluxo normal de um link afiliado:

```text
NOVO -> PROCESSANDO -> REVISAR
REVISAR + Publicar=Sim -> PRONTO PARA PUBLICAR -> PUBLICADO
```

Fluxo Shopee com link comum:

```text
NOVO -> AGUARDANDO CONVERSÃO
AGUARDANDO CONVERSÃO + Link de Afiliado preenchido -> PROCESSANDO -> REVISAR
```

Entradas interrompidas em `PROCESSANDO` serão recuperáveis por tempo limite documentado, evitando travamento permanente.

Erros temporários preservarão o último snapshot e aumentarão `Tentativas Consecutivas`. Com três falhas consecutivas, o estado passará a `ATENÇÃO`, sem despublicação automática. URL incompatível e dado estruturalmente inválido produzirão `ERRO`. Bloqueio da loja ou coleta parcial que ainda preserve dados úteis produzirá `ATENÇÃO` ou `REVISAR`, conforme a necessidade de decisão humana.

No modo `Bloqueado`, somente `Status`, `Mensagem`, `Última Verificação` e contadores operacionais poderão mudar. Metadados e a linha publicada não serão substituídos.

## Seleção e atualização da fila

Links novos ou alterados terão assinatura calculada a partir do link normalizado. O modo `pending` processará apenas linhas novas, alteradas, em `NOVO`, `ATENÇÃO` recuperável ou `ERRO` recuperável.

O modo `full` processará produtos publicados elegíveis em lotes, com limite de concorrência por domínio. Ele será executado duas vezes ao dia ou manualmente. As execuções horárias comuns não atualizarão todo o catálogo.

`Assinatura dos Dados` evitará escritas quando nada tiver mudado. Em falha temporária, preço, descrição e imagens válidos serão preservados. Zero, `None`, texto inválido ou preço impossível nunca substituirão um preço válido. A ausência momentânea de imagens não apagará URLs anteriores.

## Adoção e publicação sem duplicação

Antes de inserir uma linha em `Produtos`, a automação procurará uma correspondência nesta ordem:

1. `Último Link Publicado`;
2. link afiliado atual;
3. combinação normalizada de plataforma e ID externo, quando reconstruível com segurança.

Correspondência ambígua encerrará a publicação em `REVISAR`, sem sobrescrever linhas. Linhas de `Produtos` nunca serão excluídas. Despublicar significa escrever `Não` em `Ativo *`, conforme decisão humana ou regra futura explicitamente aprovada.

O mapeamento para os 20 cabeçalhos existentes será:

- `Ativo *`: `Sim` somente quando `Ativo` e `Publicar` forem `Sim`;
- `Tipo`: Tipo;
- `Plataforma`: Plataforma;
- `Categoria`: Categoria;
- `Subcategoria`: Subcategoria;
- `Nome`: Nome;
- `Descrição`: Descrição;
- `Preço *`: preço anterior quando houver promoção válida; caso contrário, preço atual;
- `Preço Promocional`: preço atual somente quando preço anterior for maior;
- `Cupom`: cupom comprovado;
- `Validade da oferta`: validade do cupom quando aplicável;
- `Link de Afiliado`: link afiliado original;
- `Texto do Botão`: texto normalizado ou padrão seguro da loja;
- `Vídeo (URL YouTube)`: valor existente preservado;
- `Imagem 1 *` a `Imagem 4`: imagens HTTPS válidas e únicas;
- `Ordem`: Ordem;
- `Destaque`: Destaque.

## Segurança de rede

Toda URL da planilha será entrada não confiável. A validação exigirá:

- esquema HTTPS;
- ausência de usuário, senha e porta personalizada;
- ausência de barra invertida;
- hostname sintaticamente válido;
- host pertencente à allowlist exata do parceiro;
- validação de cada salto de redirecionamento;
- limite fixo de redirecionamentos;
- DNS sem IP privado, loopback, link-local, multicast ou reservado;
- revalidação do destino efetivo da conexão;
- timeout de conexão e leitura;
- limite de tamanho antes de carregar o corpo completo;
- tipo de conteúdo esperado.

O cliente usará User-Agent transparente da Orvani. Retry com backoff exponencial será aplicado apenas a falhas temporárias. Autenticação, CAPTCHA, 403 persistente e bloqueio antibot não serão repetidos automaticamente.

Logs usarão uma representação sanitizada que omite query string e fragmento e limita o caminho quando necessário. Credenciais e JSON de conta de serviço nunca serão impressos.

## Extração pública

O extrator comum seguirá esta ordem:

1. JSON-LD de `Product` e `Offer`;
2. Open Graph;
3. metatags públicas documentadas;
4. seletores específicos isolados no conector.

Ele normalizará Unicode e espaços, removerá HTML e conteúdo executável, limitará a descrição a um tamanho documentado e não copiará avaliações de usuários. Imagens serão HTTPS, únicas e filtradas contra pixels, ícones, logos e sprites quando dimensões ou contexto permitirem.

Categoria virá primeiro da fonte oficial. Em seguida serão usados um mapeamento central de categorias Orvani e regras pequenas de palavras-chave. Falta de confiança resultará em `Outros` e `REVISAR`. Nenhum serviço de IA será usado.

## Estratégia por parceiro

### Mercado Livre

- Primeiro conector implementado.
- Separará ID de anúncio e ID de catálogo.
- Usará apenas endpoints oficiais documentados ou metadados públicos permitidos.
- Links atuais serão usados somente em smoke tests opcionais e sanitizados.
- Resultado real será documentado como API, metadados disponíveis, bloqueio ou modo semiautomático.

### Shopee

- Segundo conector implementado.
- Aceitará hosts oficiais confirmados pelo projeto e validará links curtos salto a salto.
- Não autenticará no portal de afiliados.
- Permitirá a fila `AGUARDANDO CONVERSÃO` e grupos auxiliares de no máximo cinco links comuns.
- Se GitHub Actions sofrer bloqueio persistente, manterá dados anteriores e solicitará revisão manual.

### SHEIN

- Terá contrato completo e testes por fixture sanitizada.
- Não será declarada validada em produção sem uma amostra real de afiliado.
- Hosts existentes no frontend não constituem evidência automática suficiente para novos fluxos Python; o spike confirmará somente o que uma amostra real permitir.

### TikTok Shop

- Será parceiro independente no Python e no frontend.
- Terá contrato e testes por fixture.
- Começará sem autorização ampla de domínios.
- A allowlist será ampliada somente após uma amostra oficial do proprietário.
- O conector ficará preparado para credenciais futuras por variáveis de ambiente, sem exigir API na primeira versão.

## Google Sheets

A autenticação usará `GOOGLE_SERVICE_ACCOUNT_JSON` lido diretamente do ambiente. `ORVANI_SPREADSHEET_ID`, `ORVANI_IMPORT_WORKSHEET` e `ORVANI_PRODUCTS_WORKSHEET` controlarão o destino com padrões seguros.

O cliente fará leituras e escritas em lote e retry de 429 e falhas temporárias. `--dry-run` executará validação e planejamento sem chamar operações de escrita. O comando `validate` verificará configuração, acesso, abas, cabeçalhos, parceiros e consistência sem revelar segredos.

Nenhuma escrita real ocorrerá durante desenvolvimento e testes sem credencial configurada e autorização específica do proprietário.

## CLI

Comandos previstos:

```bash
python -m automation.cli setup-sheet --dry-run
python -m automation.cli setup-sheet
python -m automation.cli sync --mode pending --dry-run
python -m automation.cli sync --mode pending
python -m automation.cli sync --mode full --dry-run
python -m automation.cli sync --mode full
python -m automation.cli validate
```

Saídas serão concisas, sanitizadas e terão códigos de retorno adequados para uso local e no GitHub Actions.

## GitHub Actions

`.github/workflows/sync-affiliates.yml` terá:

- `workflow_dispatch` com `pending`, `full` e `validate`;
- agenda horária em minuto diferente de zero;
- seleção de `full` em dois horários UTC documentados e `pending` nos demais;
- versão estável de Python compatível com dependências verificadas;
- cache seguro de dependências;
- timeout de job;
- grupo de concorrência único;
- permissões mínimas do `GITHUB_TOKEN`;
- segredos expostos apenas ao passo da CLI;
- nenhum artifact com dados da planilha, páginas de loja, cookies ou credenciais.

A documentação explicará que agendamentos podem atrasar e que a execução manual oferece atualização imediata.

## Frontend

O frontend manterá HTML, CSS e JavaScript puro, CSP, validação HTTPS, APIs seguras do DOM, carrossel, busca, filtros, categorias, estados de erro e links externos com `target="_blank"` e `rel="sponsored nofollow noopener noreferrer"`.

`script.js` será ajustado para:

- consumir Subcategoria, Cupom, Validade da oferta, Texto do Botão e Ordem;
- ordenar numericamente com valores vazios ao final e estabilidade;
- exibir cupom somente quando presente e dentro de uma validade reconhecida;
- limitar e normalizar texto personalizado do botão;
- manter texto vindo da planilha como texto, nunca HTML;
- calcular desconto somente quando preço anterior for maior;
- usar identidade persistente quando plataforma e ID externo estiverem disponíveis;
- reconhecer TikTok Shop apenas em hosts confirmados;
- atualizar o CSV a cada cinco minutos, sem confundir esse refresh com a automação Python.

O CSS receberá somente estilos compatíveis para selo e validade de cupom. `index.html` e `catalogo.html` só mudarão se a renderização segura exigir marcação estática que não possa ser criada pelo JavaScript.

## Testes

O desenvolvimento seguirá ciclos de teste falhando, implementação mínima e teste passando.

### Python

Testes unitários offline cobrirão:

- validação HTTPS e rejeições de HTTP, credenciais, porta e barra invertida;
- redirecionamento não autorizado;
- IP e DNS privados;
- sanitização de logs;
- JSON-LD único e múltiplo;
- `Decimal`, preço anterior e imagens únicas;
- ausência de cupom inventado;
- contrato e seleção de conectores;
- mapeamento Importações para Produtos;
- adoção sem duplicação, alteração de link e ambiguidade;
- modo Bloqueado;
- preservação após falha temporária;
- três falhas consecutivas;
- `--dry-run`, escrita em lote e assinatura sem escrita.

Integrações de rede serão opcionais por `RUN_LIVE_TESTS=1`, sem login nem cookie. Mercado Livre e Shopee usarão amostras atuais somente em smoke tests. SHEIN e TikTok Shop permanecerão pendentes até existirem amostras reais.

### JavaScript

Testes com `node:test` cobrirão compatibilidade de cabeçalhos, TikTok Shop, ordem estável, cupom válido/ausente/expirado, botão padrão, texto malicioso, desconto e URLs externas.

O ambiente inicial não possui `node` no `PATH`. Antes de declarar essa suíte executada, será procurado um runtime existente e, se necessário, a limitação será relatada ao proprietário; nenhuma instalação global será feita silenciosamente.

### Validação do site

Um servidor HTTP local será usado para testar `index.html` e `catalogo.html`. A validação distinguirá claramente testes automatizados, smoke tests reais e itens que dependem de credenciais, runtime ou amostras externas.

## Dependências e segredos

As versões de dependências serão escolhidas após consulta à documentação oficial e registradas em `requirements.txt` e `requirements-dev.txt`. O conjunto será mínimo: cliente HTTP maduro, autenticação/cliente do Google Sheets, parser HTML somente se necessário e pytest.

`.env.example` conterá apenas placeholders. `.gitignore` protegerá `.env`, credenciais e arquivos temporários. Nenhuma senha, cookie, token ou credencial será solicitada pelo chat ou incluída no repositório.

## Sequência de entrega

1. Spike público e somente leitura de Mercado Livre e Shopee.
2. Fundação: modelos, erros, configuração, segurança, HTTP, metadados e testes.
3. Integração Sheets, dry-run e testes com fakes.
4. Mercado Livre.
5. Shopee.
6. SHEIN e TikTok Shop por fixtures, com validação real pendente documentada.
7. Sincronização, adoção, estados, assinaturas e tolerância a falhas.
8. Workflow e documentação operacional.
9. Ajustes e testes do frontend.
10. Verificação completa e relatório final.

Commits serão pequenos e temáticos. O checkpoint inicial continuará como referência; nenhum dado ou arquivo existente será removido para executar a entrega.

## Critérios de conclusão

O trabalho estará concluído quando:

- o site atual continuar funcionando;
- Produtos conservar os 20 cabeçalhos e seus dados;
- Importações puder ser configurada de forma idempotente;
- dados públicos fornecidos pela loja puderem preencher uma nova entrada sem digitação manual;
- o link afiliado original for preservado;
- revisão humana controlar a publicação;
- modo Bloqueado, assinatura e atualização incremental funcionarem;
- adoção e alteração de link não duplicarem produtos;
- falhas temporárias preservarem o último dado válido;
- cupons e descontos não forem inventados;
- workflow e CLI estiverem documentados e testados dentro do que não exige credenciais;
- limitações por loja estiverem explícitas;
- suítes executáveis no ambiente passarem;
- nenhuma credencial estiver em código, frontend, planilha pública, logs ou artifacts;
- nenhum deploy tiver sido realizado.

## Dependências externas deliberadamente pendentes

Estas pendências não são lacunas do desenho:

- uma amostra real da SHEIN é necessária para validar seu fluxo em produção;
- uma amostra real do TikTok Shop é necessária para definir hosts exatos e validar seu fluxo;
- credencial de conta de serviço e autorização explícita são necessárias para qualquer escrita real;
- bloqueios reais de Mercado Livre ou Shopee podem exigir operação semiautomática;
- um runtime Node.js é necessário para executar a suíte JavaScript, embora os testes possam ser escritos sem npm.

Qualquer uma dessas condições será relatada como limitação verificada, nunca como sucesso presumido.
