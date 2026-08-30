# Spike: viabilidade pública das lojas

Data/hora (UTC): 2026-08-30T03:09:15Z

## Escopo e salvaguardas

Esta verificação foi somente de leitura. Não houve escrita na planilha, uso de
credenciais, login, cookies, bypass de antibot, deploy, nem retenção de URLs de
afiliado, caminhos, consultas, fragmentos ou corpos de resposta.

O CSV público foi baixado com `User-Agent: Orvani-read-only-spike/1.0`; a leitura
podia consumir até 2.000.001 bytes, como sentinela para detectar se o limite
aceito de 2.000.000 bytes tinha sido excedido. A linha de cabeçalho foi a 4 e continha os 20 campos
esperados. Foram aceitas 11 linhas ativas. A observação existente foi mantida:
a linha 8, plataforma Hotmart, produto “Curso Vitrine de Afiliado do Zero”,
tem host `www.darlanevandro.com.br`, incompatível com a regra de domínio
Hotmart.

## Amostra e método

Foram avaliadas 6 amostras ativas: 4 Shopee e 2 Mercado Livre. Cada solicitação
aceitou somente hosts `mercadolivre.com.br`/`meli.la` ou
`shopee.com.br`/`s.shopee.com.br`; toda resposta DNS foi exigida como global,
redirecionamentos foram validados e limitados a cinco, e os limites foram 5 s de
conexão, 15 s de leitura e 2 MB de corpo. Não houve redirecionamento observado.

| Loja | Linhas | Hosts sanitizados | HTTP terminal / tipo | Tamanho | Marcadores | Resultado |
| --- | --- | --- | --- | --- | --- | --- |
| Shopee | 6, 7 | `s.shopee.com.br` | 200 / `text/html` | 277529 B; 277532 B; dentro de 2 MB | `json_ld=false`, `og_title=false`, `og_image=false`, `structured_price=false` | SEMIAUTOMÁTICO |
| Shopee | 11, 12 | `shopee.com.br` | 200 / `text/html` | 192111 B; 192111 B; dentro de 2 MB | `json_ld=false`, `og_title=false`, `og_image=false`, `structured_price=false` | SEMIAUTOMÁTICO |
| Mercado Livre | 13, 14 | `www.mercadolivre.com.br` | 200 / `text/html` | 20595 B; 20580 B; dentro de 2 MB | `json_ld=false`, `og_title=false`, `og_image=false`, `structured_price=false` | SEMIAUTOMÁTICO |

## Conclusão factual

As duas lojas responderam publicamente dentro dos limites, mas nenhuma amostra
expôs os quatro marcadores de metadados estruturados definidos para a spike.
Por isso, nenhuma é classificada como **VIÁVEL POR API/METADADOS** nesta
verificação; ambas permanecem **SEMIAUTOMÁTICO**. Não houve resultado
**BLOQUEADO** nas amostras disponíveis.

SHEIN e TikTok Shop não tinham amostras no CSV e não foram avaliadas. Nenhuma
escrita foi realizada em qualquer planilha ou serviço externo.
