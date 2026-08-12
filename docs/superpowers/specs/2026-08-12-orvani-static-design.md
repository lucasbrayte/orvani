# Orvani Estática — Especificação de Design

## Objetivo

Substituir a aplicação Next.js atual por uma vitrine estática, profissional e acessível que funcione por HTTP simples e contenha somente `index.html`, `style.css` e `script.js` na árvore de trabalho, além do diretório oculto `.git`.

O catálogo será demonstrável sem configuração e poderá consumir uma aba pública do Google Sheets publicada como CSV. Não haverá credenciais, servidor de aplicação, banco, dependências, build ou deploy.

## Segurança da substituição

A implementação anterior está preservada na branch `backup/orvani-before-static`, commit `9936b48f9f55708251c04834bb6ec4537dbf6ed1`. A referência e sua árvore foram comparadas ao `master` antes de qualquer remoção.

A remoção abrangerá somente os alvos enumerados da implementação anterior e seus artefatos gerados: arquivos de configuração Next/TypeScript/npm, documentação anterior, `src`, `public`, `scripts`, `supabase`, `tests`, `.next`, `node_modules`, `.worktrees` vazia e `tsconfig.tsbuildinfo`. `.git` será preservado.

## Arquitetura final

### `index.html`

Documento semântico em português do Brasil com skip link, cabeçalho fixo, logotipo SVG inline original, navegação, menu móvel, hero, carrossel de destaques, categorias, busca, filtros, contador, grade de produtos, estados de carregamento/erro/vazio e rodapé de transparência de afiliados.

Não haverá conteúdo externo obrigatório. Fontes serão do sistema. O HTML conterá somente elementos-base; conteúdo editorial da planilha será criado com APIs seguras do DOM.

### `style.css`

Design mobile-first usando `#635BFF`, `#0B1020`, `#F7F8FC` e coral `#FF6B4A` com moderação. O layout usará proporções estáveis para imagens, foco visível, contraste AA como objetivo, grid responsivo e ausência de rolagem horizontal.

Transições usarão `transform` e `opacity`. `prefers-reduced-motion: reduce` desabilitará autoplay, entradas animadas, rolagem suave e movimentos não essenciais sem retirar funcionalidade.

### `script.js`

O arquivo começará com `CONFIG`, contendo `spreadsheetUrl`, intervalo de cinco minutos e o único cadastro de parceiros/hosts. Os parceiros iniciais serão Amazon, Shopee, Mercado Livre, AliExpress e SHEIN, exatamente conforme os hosts fornecidos no pedido.

O código será uma função autoexecutável dividida internamente por responsabilidade:

- parser CSV por máquina de estados;
- normalização e validação de produtos;
- validação de URL e host por parceiro;
- estado do catálogo, busca e filtros;
- criação segura de elementos DOM;
- controlador do carrossel;
- carregamento, atualização periódica e estados de feedback;
- menu móvel e animações de entrada.

Funções puras essenciais serão expostas por um objeto congelado somente para permitir testes temporários sem introduzir arquivos adicionais no resultado final.

## Dados e fluxo

O cabeçalho aceito será exatamente:

```text
id,nome,descricao_curta,descricao,categoria,tipo,preco,preco_anterior,imagem,imagens,loja,link_afiliado,destaque,ativo
```

Quando `CONFIG.spreadsheetUrl` for exatamente o placeholder, o site usará dez produtos fictícios embutidos, com ilustrações SVG em data URL geradas localmente. Quando houver URL configurada, o fluxo será:

1. exibir carregamento;
2. executar `fetch(url, { cache: "no-store" })`;
3. exigir resposta HTTP bem-sucedida;
4. interpretar CSV com vírgulas, aspas escapadas, CRLF e novas linhas citadas;
5. validar cada linha isoladamente;
6. renderizar somente produtos válidos e ativos;
7. registrar rejeições no console apenas por número da linha, ID seguro e campos, sem ecoar a linha;
8. agendar nova leitura após cinco minutos somente enquanto a aba estiver visível.

Falha com URL real nunca acionará dados de demonstração. O estado de erro terá mensagem clara e botão “Tentar novamente”. O último catálogo válido poderá permanecer visualmente disponível somente durante uma atualização posterior, acompanhado de aviso de falha; a carga inicial sem dados exibirá o estado de erro completo.

## Validação e segurança

Textos da planilha serão atribuídos por `textContent`. Não serão usados `innerHTML`, `insertAdjacentHTML`, `document.write` ou `eval`.

URLs serão analisadas com `new URL`. Somente HTTPS sem usuário, senha ou porta não padrão será aceito. Imagens inválidas usarão um SVG seguro embutido. O link afiliado dependerá de uma chave existente em `CONFIG.affiliatePartners` e será aceito apenas quando o hostname for o host exato ou um subdomínio delimitado por ponto de um host daquela loja. Links abrirão em nova aba com `rel="sponsored nofollow noopener noreferrer"`.

IDs serão únicos. Campos obrigatórios vazios, tipo diferente de `fisico`/`digital`, preço não positivo/ambíguo, booleano diferente de `TRUE`/`FALSE`, loja desconhecida ou URL inválida rejeitarão somente a linha afetada. `preco_anterior` inválido não produzirá desconto ou preço riscado; quando não numérico, a linha será rejeitada para evitar conteúdo editorial ambíguo.

A versão estática considera planilha, imagens e links publicamente legíveis. Nenhum dado privado deverá ser colocado na planilha.

## Busca, filtros e categorias

A busca, sem distinção de maiúsculas ou acentos, abrangerá nome, descrição curta, descrição, categoria, chave e rótulo da loja. Categoria e tipo serão combinados com a busca e aplicados imediatamente. Categorias serão derivadas dos produtos ativos e oferecerão atalhos clicáveis. O contador usará texto singular/plural adequado. Zero correspondências exibirá um estado próprio com ação para limpar filtros.

## Carrossel e interação

O carrossel usará produtos `destaque=TRUE` e `ativo=TRUE`. Haverá setas, indicadores, teclado com setas esquerda/direita e gesto horizontal por Pointer Events. Autoplay terá intervalo de seis segundos e pausará em hover, foco interno, interação por ponteiro e aba oculta; reiniciará do zero após a interação terminar. Com um único destaque, controles e autoplay serão omitidos.

O slide ativo será o único exposto à navegação e leitores de tela. Uma região `aria-live="polite"` anunciará somente mudanças iniciadas pelo usuário, evitando anúncios a cada autoplay.

Menu móvel terá botão real com `aria-expanded`, fechamento por Escape, clique em link e clique fora. Seções e cards entrarão com `IntersectionObserver`, exceto em movimento reduzido.

## Verificação

Testes temporários, mantidos fora da árvore final, validarão:

- CSV simples, vírgulas/aspas/CRLF e quebras citadas;
- linha inválida preservando as válidas;
- URLs permitidas e ataques por HTTP, credenciais, domínio semelhante e subdomínio malicioso;
- preço, desconto, booleanos, duplicidade e filtros combinados;
- demonstração, CSV real de fixture, falha de rede e nova tentativa;
- carrossel por controles, teclado e ponteiro;
- pausa por interação/visibilidade e movimento reduzido;
- menu móvel, foco, desktop, celular e ausência de overflow;
- ausência de erros não tratados;
- servidor HTTP local e existência exclusiva dos três arquivos visíveis.

A validação visual usará navegador real em desktop e viewport móvel. O servidor Python será usado somente durante os testes e não fará parte do projeto.

## Restauração

A implementação anterior poderá ser consultada sem alterar o trabalho atual com:

```bash
git show backup/orvani-before-static:README.md
```

Uma restauração integral deverá ser feita em operação deliberada, por exemplo criando uma nova branch a partir do backup:

```bash
git switch -c restore/orvani-next backup/orvani-before-static
```

Não será feito deploy nem publicação da planilha.
