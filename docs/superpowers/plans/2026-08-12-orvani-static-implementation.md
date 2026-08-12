# Orvani Estática — Plano de Implementação

> **Para trabalhadores agênticos:** SUB-HABILIDADE OBRIGATÓRIA: use `superpowers:subagent-driven-development` (recomendado) ou `superpowers:executing-plans` para implementar este plano tarefa por tarefa. As etapas usam caixas de seleção (`- [ ]`) para acompanhamento.

**Objetivo:** Substituir a aplicação Next.js por uma vitrine estática segura, acessível e configurável por CSV público, deixando somente `index.html`, `style.css` e `script.js` visíveis.

**Arquitetura:** `script.js` começa com a configuração editorial e encapsula funções puras para CSV, validação e filtros, mais controladores DOM para catálogo, carrossel e atualização. `index.html` fornece landmarks e estados-base; `style.css` fornece o sistema visual mobile-first. Testes Node e Playwright vivem em diretório temporário fora do projeto e são apagados depois da verificação.

**Tecnologias:** HTML5, CSS moderno, JavaScript ES2022 sem módulos externos, Node.js somente como executor temporário de testes, Python `http.server` e Playwright já disponível no backup somente durante a migração.

## Restrições globais

- Preservar `.git` e o backup verificado `backup/orvani-before-static` no commit `9936b48f9f55708251c04834bb6ec4537dbf6ed1`.
- Não remover nada antes de verificar backup, status limpo e lista exata de alvos.
- O resultado final visível deve conter somente `index.html`, `style.css` e `script.js`.
- Não deixar React, Next.js, TypeScript, Tailwind, Supabase, npm, `package.json`, `node_modules`, bundler, framework, servidor ou build.
- Não usar `innerHTML`, `insertAdjacentHTML`, `document.write` ou `eval` com conteúdo editorial.
- Aceitar somente HTTPS, sem credenciais/porta, com host exato ou subdomínio delimitado por parceiro configurado.
- Não fazer deploy, publicar planilha ou solicitar credenciais.

---

### Tarefa 1: Harness temporário e núcleo seguro do catálogo

**Arquivos:**
- Criar: `C:/Users/lucas/AppData/Local/Temp/orvani-static-tests/unit.mjs`
- Criar: `script.js`

**Interfaces:**
- Produz: `window.OrvaniCore.parseCsv(text)`, `normalizeRows(rows)`, `validatePartnerUrl(raw, partnerKey)`, `filterProducts(products, filters)`, `calculateDiscount(current, previous)`.
- Consome: `CONFIG.affiliatePartners` e cabeçalhos exatos da especificação.

- [ ] **Etapa 1: escrever testes unitários falhos**

O harness deve carregar `script.js` em `vm`, com um `document` mínimo que impeça a inicialização DOM. Casos literais: CSV com `"Cabo, USB"`, `"linha 1\nlinha 2"`, aspas `""`; CRLF; linha vazia; domínio parecido `amazon.com.br.evil.example`; subdomínio válido; HTTP; credenciais; loja desconhecida; preço anterior menor; acentos na busca; linha inválida junto de válida.

- [ ] **Etapa 2: confirmar vermelho**

Executar:

```powershell
node "$env:LOCALAPPDATA\Temp\orvani-static-tests\unit.mjs"
```

Esperado: falha porque `script.js` ou `OrvaniCore` não existe.

- [ ] **Etapa 3: implementar o núcleo mínimo em `script.js`**

Adicionar no início o `CONFIG` literal exigido e dez produtos fictícios. Implementar parser por estados `FIELD`, `QUOTED`, `AFTER_QUOTE`, preservando novas linhas citadas e rejeitando aspas ilegais. Normalizar cabeçalho exato e produtos por linha, retornar `{ products, rejected }`, e expor `Object.freeze` em `globalThis.OrvaniCore`.

- [ ] **Etapa 4: confirmar verde**

Executar o harness e exigir todos os casos aprovados e nenhuma rejeição inesperada.

- [ ] **Etapa 5: registrar checkpoint**

```powershell
git add script.js
git commit -m "feat: add static catalog core"
```

### Tarefa 2: Documento semântico e renderização segura

**Arquivos:**
- Criar: `index.html`
- Modificar: `script.js`
- Criar: `C:/Users/lucas/AppData/Local/Temp/orvani-static-tests/dom.mjs`

**Interfaces:**
- Consome: funções do `OrvaniCore`.
- Produz: landmarks e IDs estáveis `site-header`, `mobile-menu`, `featured-carousel`, `category-list`, `catalog-search`, `category-filter`, `type-filter`, `result-count`, `product-grid`, `catalog-state`, `retry-button`.

- [ ] **Etapa 1: escrever teste DOM falho**

Usar navegador real posteriormente para acessibilidade; neste harness, validar o comportamento do documento servido: dados da demonstração aparecem, textos com `<img onerror>` permanecem texto, links têm `target="_blank"` e o `rel` completo, filtros combinam busca/categoria/tipo, botão limpar restaura resultados e linha rejeitada não interrompe renderização.

- [ ] **Etapa 2: confirmar vermelho**

Executar o harness e observar falha por IDs/renderizadores ausentes.

- [ ] **Etapa 3: implementar HTML e renderização**

Criar landmarks, labels, live regions discretas e templates estruturais. Em JS, criar tudo com `document.createElement`, `textContent`, `setAttribute` com valores constantes/validados e `replaceChildren`. Implementar imagem com `error` para placeholder data URL seguro, formatação BRL, desconto somente válido, categorias e estados.

- [ ] **Etapa 4: confirmar verde**

Executar os testes DOM temporários.

- [ ] **Etapa 5: registrar checkpoint**

```powershell
git add index.html script.js
git commit -m "feat: render accessible static catalog"
```

### Tarefa 3: Sistema visual responsivo

**Arquivos:**
- Criar: `style.css`
- Modificar: `index.html`
- Modificar: `script.js`

**Interfaces:**
- Consome: classes semânticas do documento.
- Produz: layout estável em 320 px, 768 px e desktop; estados `is-open`, `is-active`, `is-visible`, `is-dragging`, `is-loading`.

- [ ] **Etapa 1: escrever checks visuais falhos no harness E2E**

Asserções: largura do documento não excede viewport em 320 px; skip link recebe foco; foco visível; cards mantêm proporção; menu móvel fechado inicialmente e abre; desktop mostra navegação; `prefers-reduced-motion` remove transições e elementos não ficam invisíveis.

- [ ] **Etapa 2: confirmar vermelho**

Servir por HTTP e executar o conjunto visual, esperando falhas sem CSS.

- [ ] **Etapa 3: implementar `style.css`**

Definir tokens, reset, tipografia de sistema, containers, cabeçalho fixo, hero, carrossel, filtros, cards, estados, rodapé, breakpoints e motion query. Coral ficará restrito a oferta/desconto; textos pequenos usarão variante violeta de contraste adequado.

- [ ] **Etapa 4: confirmar verde em desktop e celular**

Executar testes em Chromium desktop e viewport móvel.

- [ ] **Etapa 5: registrar checkpoint**

```powershell
git add index.html style.css script.js
git commit -m "feat: style static Orvani storefront"
```

### Tarefa 4: Carrossel, menu e movimento

**Arquivos:**
- Modificar: `script.js`
- Modificar: `style.css`
- Modificar: `index.html`

**Interfaces:**
- Produz: controlador de carrossel com `goTo`, `next`, `previous`, `pause(reason)`, `resume(reason)` e gesto Pointer Events; menu com `aria-expanded`, Escape e clique externo; observer de entrada.

- [ ] **Etapa 1: escrever testes E2E falhos**

Validar botão seguinte/anterior, indicadores, ArrowLeft/ArrowRight, arraste horizontal acima do limiar, pausa em hover/foco/ponteiro/`visibilitychange`, ausência de autoplay com um slide/reduced motion, anúncio somente em ação do usuário, menu por botão/Escape/clique fora e classes visíveis sem motion.

- [ ] **Etapa 2: confirmar vermelho**

Executar o recorte E2E de interação e observar falhas nas funções ausentes.

- [ ] **Etapa 3: implementar controladores**

Usar conjunto de motivos de pausa e temporizador único de 6000 ms. No movimento reduzido, não criar timer. Slides inativos recebem `aria-hidden="true"`; controles reais atualizam `aria-current`. Pointer capture será usado durante arraste.

- [ ] **Etapa 4: confirmar verde**

Executar testes E2E de mouse, teclado, toque e reduced motion.

- [ ] **Etapa 5: registrar checkpoint**

```powershell
git add index.html style.css script.js
git commit -m "feat: add accessible static interactions"
```

### Tarefa 5: CSV remoto, atualização e erro recuperável

**Arquivos:**
- Modificar: `script.js`
- Criar: `C:/Users/lucas/AppData/Local/Temp/orvani-static-tests/catalog.csv`
- Criar: `C:/Users/lucas/AppData/Local/Temp/orvani-static-tests/bad-response-server.mjs`

**Interfaces:**
- Produz: `loadCatalog({ manual })`, agendamento por visibilidade e retry.

- [ ] **Etapa 1: escrever testes de integração falhos**

Servir cópia temporária dos três arquivos com `spreadsheetUrl` apontando ao fixture. Validar `fetch` sem cache, CSV válido, linha inválida isolada, carga inicial com rede 500, botão tentar novamente, ausência de fallback demo, atualização posterior preservando catálogo com aviso e timer apenas quando visível.

- [ ] **Etapa 2: confirmar vermelho**

Executar testes e observar estado remoto ausente.

- [ ] **Etapa 3: implementar carregamento**

Validar que a URL da planilha é HTTPS antes de buscar; usar `fetch(CONFIG.spreadsheetUrl, { cache: "no-store" })`; checar `response.ok`; nunca registrar CSV ou URL completa. Cancelar timer ao ocultar e atualizar ao retornar se o intervalo venceu.

- [ ] **Etapa 4: confirmar verde**

Executar integração em sucesso, parcial e falha/retry.

- [ ] **Etapa 5: registrar checkpoint**

```powershell
git add script.js
git commit -m "feat: sync public CSV catalog"
```

### Tarefa 6: Remoção controlada da implementação anterior

**Arquivos:**
- Remover exatamente: `.env.example`, `.gitignore`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs`, `eslint.config.mjs`, `next-env.d.ts`, `next.config.ts`, `package-lock.json`, `package.json`, `playwright.config.ts`, `postcss.config.mjs`, `public`, `scripts`, `src`, `supabase`, `tests`, `tsconfig.json`, `vitest.config.ts`.
- Remover artefatos exatos não rastreados: `.next`, `.worktrees` vazia, `node_modules`, `tsconfig.tsbuildinfo`.
- Preservar: `.git`, `index.html`, `style.css`, `script.js`.

**Interfaces:** nenhuma.

- [ ] **Etapa 1: rever o backup e prévia de remoção**

Comparar novamente `git rev-parse backup/orvani-before-static` com `9936b48...`, `git cat-file -t` com `commit`, status e listagem dos alvos. Executar prévia de `git clean` somente nos artefatos ignorados.

- [ ] **Etapa 2: remover alvos rastreados por patch explícito**

Usar `apply_patch` para apagar arquivos de topo rastreados e arquivos em diretórios. Não tocar em `.git`.

- [ ] **Etapa 3: remover diretórios gerados por alvos literais validados**

Usar PowerShell nativo ou `git clean -fdx -- <alvo literal>` depois de confirmar que cada caminho absoluto está sob a raiz do projeto.

- [ ] **Etapa 4: validar árvore final**

`Get-ChildItem -Force` deve listar `.git`, `index.html`, `style.css`, `script.js`; `git status --short` deve mostrar as remoções e os três arquivos.

- [ ] **Etapa 5: registrar substituição**

```powershell
git add -A
git commit -m "refactor: replace Orvani with static storefront"
```

### Tarefa 7: Verificação final e relatório

**Arquivos:**
- Verificar: `index.html`, `style.css`, `script.js`.
- Remover: `C:/Users/lucas/AppData/Local/Temp/orvani-static-tests` após capturar resultados.

- [ ] **Etapa 1: executar testes unitários temporários**

Exigir 0 falhas em parser, validação, normalização, desconto e filtro.

- [ ] **Etapa 2: servir por HTTP simples**

Executar `python -m http.server 5500 --bind 127.0.0.1` a partir da raiz em processo oculto e verificar resposta 200 de `/`, `/style.css` e `/script.js`.

- [ ] **Etapa 3: executar E2E completo**

Validar demo, fixture CSV, erro/retry, desktop, celular, teclado, pointer, reduced motion, links, console e overflow. Capturar screenshots temporários e inspecionar visualmente; não copiá-los ao projeto.

- [ ] **Etapa 4: executar scans estáticos**

Confirmar ausência de `innerHTML`, `insertAdjacentHTML`, `document.write`, `eval`, protocolo HTTP em links aceitos, credenciais, scripts externos, dependências e arquivos extras. Confirmar `CONFIG` no início de `script.js`.

- [ ] **Etapa 5: limpar harness e confirmar restauração**

Remover somente o diretório temporário exato. Confirmar que `git show backup/orvani-before-static:README.md` funciona e que a branch permanece apontando ao commit verificado.

- [ ] **Etapa 6: confirmar estado final**

Exigir árvore Git limpa no `master`, três arquivos visíveis e servidor de teste encerrado. Relatar backup, removidos, verificações reais, local da URL CSV, cadastro de parceiro, publicação do Sheets e linha completa de exemplo.
