# Orvani — Composição Genérica de Link Afiliado por Query Parameters

Data: 2026-09-11  
Status: aguardando revisão do usuário

## 1. Objetivo

Permitir que o Orvani trabalhe com parceiros que fornecem um único link de afiliado com parâmetros de rastreamento, enquanto cada produto possui sua própria URL.

A primeira implementação usará a estratégia `affiliate_query_merge`.

Exemplo inicial:

- Link do Produto:
  `https://contingenciamaxima.com.br/produto/9b597da1-2d3a-47e5-86c6-5852f2c68000`
- Link Afiliado base:
  `https://contingenciamaxima.com.br?ref=lukn`
- Link Afiliado efetivo:
  `https://contingenciamaxima.com.br/produto/9b597da1-2d3a-47e5-86c6-5852f2c68000?ref=lukn`

O usuário continuará digitando no LibreOffice o link original do produto e o link afiliado base. O Orvani fará a composição em memória antes de sincronizar.

## 2. Escopo da versão 1

A versão 1 suportará somente parceiros cujo rastreamento possa ser transportado pelos parâmetros da query string.

Exemplos de parâmetros compatíveis:

- `ref=...`
- `affiliate=...`
- `tag=...`
- `utm_source=...`
- outros parâmetros fornecidos pelo próprio link afiliado

A implementação não dependerá do nome do parâmetro. Ela transportará os parâmetros presentes no link afiliado base, respeitando as regras de segurança deste documento.

## 3. Fora de escopo

Não fazem parte desta versão:

- links afiliados baseados em redirects especiais;
- templates de caminho;
- códigos inseridos no path da URL;
- cookies criados artificialmente pelo Orvani;
- automação de login em painel de afiliado;
- scraping para descobrir regras de afiliação;
- alteração da estrutura das abas `Importações` ou `Produtos`;
- criação de novas colunas no `Orvani.ods`;
- tentativa de transformar automaticamente parceiros não cadastrados.

Estratégias futuras poderão ser adicionadas separadamente, por exemplo:

- `affiliate_redirect`;
- `affiliate_path_template`;
- outras estratégias aprovadas posteriormente.

## 4. Fluxo funcional

O fluxo permanecerá:

```text
Orvani.ods
  -> normalização do registro
  -> identificação do parceiro
  -> composição do link afiliado efetivo
  -> validação local
  -> hash/deduplicação
  -> Apps Script
  -> Importações
  -> workflow pending
  -> Produtos
  -> site Orvani
```

Para um parceiro `affiliate_query_merge`, o LibreOffice mantém os valores digitados pelo usuário:

```text
Link Produto:  URL direta do produto
Link Afiliado: link afiliado base
```

O payload enviado para `Importações` manterá:

```text
Link do Produto: URL direta original
Link de Afiliado: URL final composta
```

Assim, o link-base continua reutilizável no arquivo local, enquanto `Importações`, `Produtos`, Divulgação e o site recebem o link final que aponta diretamente ao produto.

## 5. Registro de parceiros

Cada parceiro terá uma configuração explícita.

A configuração deverá permitir, no mínimo:

```text
key
display_name
allowed_hosts
affiliate_strategy
```

O parceiro inicial será:

```text
key: contingencia_maxima
display_name: Contingência Máxima
allowed_hosts:
  - contingenciamaxima.com.br
affiliate_strategy: affiliate_query_merge
```

Hosts com subdomínio serão aceitos somente quando pertencentes ao domínio permitido pela configuração.

Os parceiros existentes — Mercado Livre, Shopee, SHEIN e Amazon — continuarão com sua estratégia atual e não passarão pela composição `affiliate_query_merge`.

## 6. Algoritmo `affiliate_query_merge`

Entradas:

- URL do produto;
- URL afiliada base;
- configuração do parceiro.

Etapas:

1. Validar que as duas URLs usam `https`.
2. Resolver o hostname das duas URLs.
3. Confirmar que as duas URLs pertencem ao mesmo parceiro registrado.
4. Confirmar que os hosts são compatíveis com `allowed_hosts`.
5. Usar scheme, host, path e fragment exclusivamente da URL do produto.
6. Ler os parâmetros já existentes na URL do produto.
7. Ler os parâmetros da URL afiliada base.
8. Remover da query do produto as chaves que também aparecem no link afiliado.
9. Acrescentar os pares de parâmetros do link afiliado.
10. Reconstruir a URL utilizando um parser/encoder de URL, nunca concatenação textual manual.

A URL afiliada base precisa possuir ao menos um parâmetro de query para esta estratégia. Um link sem parâmetros não é suficiente para `affiliate_query_merge`.

O path do link afiliado base não será usado. A versão 1 existe apenas para transporte de query parameters.

## 7. Regras de conflito

Parâmetros exclusivos do produto serão preservados.

Exemplo:

```text
Produto:
https://loja.com/produto/123?cor=azul

Afiliado:
https://loja.com?ref=lukn

Resultado:
https://loja.com/produto/123?cor=azul&ref=lukn
```

Quando uma chave existir nas duas URLs, o valor vindo do link afiliado prevalece.

Exemplo:

```text
Produto:
https://loja.com/produto/123?ref=antigo&cor=azul

Afiliado:
https://loja.com?ref=lukn

Resultado:
https://loja.com/produto/123?cor=azul&ref=lukn
```

Se o link afiliado possuir a mesma chave mais de uma vez, todas as ocorrências afiliadas dessa chave serão preservadas e substituirão as ocorrências equivalentes existentes no produto.

## 8. Segurança e validação

A composição será fail-closed.

O produto não será enviado para `Importações` se ocorrer qualquer uma destas condições:

- uma das URLs não for HTTPS;
- URL malformada;
- hostname ausente;
- parceiro desconhecido;
- estratégia não suportada;
- produto e link afiliado pertencem a parceiros/domínios incompatíveis;
- link afiliado da estratégia `affiliate_query_merge` não possui query parameters.

O Calc receberá `ERRO LOCAL` e uma mensagem objetiva.

Exemplos de mensagens:

```text
Link Produto e Link Afiliado pertencem a domínios incompatíveis.
Link Afiliado não possui parâmetros para composição.
Link Afiliado deve usar HTTPS.
```

Nenhum link parcial ou presumido será publicado em caso de erro.

## 9. Normalização, hash e deduplicação

A composição precisa ocorrer antes da criação do payload e do hash efetivo.

O hash deve representar o link afiliado final, não apenas o link-base digitado.

Consequência desejada:

```text
?ref=lukn
```

alterado para:

```text
?ref=novo
```

deve fazer a linha ser considerada alterada e gerar nova sincronização, mesmo que todos os demais campos continuem iguais.

O valor digitado no Calc não será sobrescrito pela automação.

## 10. Integração com LibreOffice

O dropdown `Plataforma` passará a incluir:

```text
Contingência Máxima
```

A inferência por URL reconhecerá `contingenciamaxima.com.br`.

A leitura das colunas atuais permanece inalterada.

Não haverá nova coluna.

As colunas envolvidas continuam sendo:

- `Link Produto`;
- `Link Afiliado`;
- `Plataforma`;
- `Status`;
- `Mensagem`.

## 11. Integração com Apps Script e Importações

O contrato de transporte atual não será ampliado.

O Apps Script continuará recebendo:

```text
Link do Produto
Link de Afiliado
Plataforma
```

Para `Contingência Máxima`, `Link de Afiliado` já chegará composto pelo cliente local.

A aba `Importações` armazenará o link afiliado efetivo.

O mecanismo existente de `ID Automação`, upsert e deduplicação continuará sendo usado sem mudanças estruturais.

## 12. Integração com publicação `Importações -> Produtos`

O registro de parceiros da automação será ampliado com `contingencia_maxima`.

Para produtos digitais cadastrados manualmente, o fluxo deverá preservar os metadados fornecidos pelo usuário, seguindo o comportamento de `Modo de Atualização = Manual`.

O host final do link afiliado precisará ser aceito pelo registro do parceiro.

A aba `Produtos` continuará recebendo o link afiliado final na coluna existente `Link de Afiliado`.

## 13. Integração com site e Divulgação

O frontend deverá reconhecer `Contingência Máxima` como parceiro autorizado para links externos.

A lista de hosts autorizados do site deverá incluir somente os hosts explicitamente cadastrados para o parceiro.

A Central de Divulgação deverá usar o link já persistido em `Produtos`, sem recomposição adicional.

A composição ocorrerá uma única vez no início do pipeline.

## 14. Compatibilidade

Não serão alteradas as regras existentes de:

- Mercado Livre;
- Shopee;
- SHEIN;
- Amazon.

Esses parceiros continuarão utilizando seus links afiliados atuais diretamente.

A nova lógica só será acionada quando a configuração do parceiro declarar:

```text
affiliate_strategy = affiliate_query_merge
```

## 15. Testes obrigatórios

A implementação seguirá TDD.

### Composição

Devem existir testes para:

```text
/produto/123 + ?ref=lukn
-> /produto/123?ref=lukn
```

```text
/produto/123?cor=azul + ?ref=lukn
-> /produto/123?cor=azul&ref=lukn
```

```text
/produto/123?ref=antigo + ?ref=lukn
-> /produto/123?ref=lukn
```

Também devem ser testados:

- parâmetros percent-encoded;
- múltiplos parâmetros afiliados;
- parâmetros duplicados no link afiliado;
- fragmento do produto preservado;
- path do produto preservado.

### Segurança

Devem falhar:

- `http://`;
- hosts incompatíveis;
- hostname vazio;
- parceiro não registrado;
- link afiliado sem query;
- URL malformada.

### Regressão

Devem continuar passando testes de:

- Mercado Livre;
- Shopee;
- SHEIN;
- Amazon;
- hash/deduplicação;
- publicação em `Importações`;
- publicação em `Produtos`;
- validação de links externos do frontend;
- dropdown e inicialização do workbook.

## 16. Critérios de aceitação

A funcionalidade estará concluída quando for possível:

1. abrir `Orvani Catálogo`;
2. criar um produto digital;
3. informar o link direto do produto;
4. informar `https://contingenciamaxima.com.br?ref=lukn` em `Link Afiliado`;
5. selecionar ou inferir `Contingência Máxima`;
6. salvar;
7. observar em `Importações` o link direto composto com `?ref=lukn`;
8. permitir que o fluxo existente publique o registro em `Produtos`;
9. confirmar que o site utiliza o mesmo link final;
10. confirmar que os parceiros existentes não sofreram regressão.

## 17. Rollout

A implementação deverá ser feita em branch/worktree isolada.

Ordem de rollout:

1. testes RED da composição;
2. componente de composição;
3. integração no pipeline local;
4. registro de `Contingência Máxima` no LibreOffice;
5. registro no backend de publicação;
6. registro no frontend;
7. suíte de regressão;
8. teste manual com um produto real;
9. somente depois da validação manual: merge e push.

Nenhuma alteração de produção deverá ser enviada ao `main` antes do teste manual.
