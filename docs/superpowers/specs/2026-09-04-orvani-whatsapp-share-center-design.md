# Orvani — Central de Divulgação WhatsApp

## Objetivo

Preparar automaticamente uma fila de divulgação quando um produto realmente
entra em `Produtos` pela primeira vez e oferecer uma interface local em
`http://127.0.0.1:8765` para copiar texto, link e abrir imagem/WhatsApp.

## Regras

- A fila backend usa a aba `Divulgação`.
- Um item entra na fila somente na primeira transição real para `PUBLICADO`.
- Atualizações posteriores de preço, nome ou imagem não geram duplicatas.
- A fila guarda nome, descrição curta, preço efetivo, imagem e link afiliado.
- A interface local nunca publica automaticamente no WhatsApp.
- Não usar Selenium, Playwright, whatsapp-web.js, sessão ou QR do WhatsApp.
- O servidor local escuta exclusivamente em `127.0.0.1:8765`.
- Estados da Central: `PENDENTE`, `PUBLICADO`, `ARQUIVADO`.
- Nesta v1 o estado operacional da Central fica em arquivo local 0600. A aba
  backend permanece como registro de origem com estado inicial `PENDENTE`.
  Isso evita exigir redeploy do Apps Script ou credencial de escrita local.
- A interface escapa conteúdo dinâmico e não expõe segredos.

## Fluxo

`LibreOffice -> Importações -> Produtos -> Divulgação -> Central local -> WhatsApp`

## Publicação preparada

```text
🛍️ Nome do produto

Descrição curta.

💰 R$ 99,90

🔗 Confira na loja:
https://link-afiliado
```
