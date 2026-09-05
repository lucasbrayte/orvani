# Orvani — Acesso móvel local à Central de Divulgação

## Objetivo

Permitir que a Central de Divulgação seja usada pelo notebook e pelo celular
na mesma rede Wi-Fi, sem expor a aplicação à internet pública e sem alterar o
backend de produtos ou o fluxo de backfill.

## Regras de segurança

- O servidor escuta em `0.0.0.0:8765`, mas rejeita clientes cujo IP não esteja
  em loopback, RFC1918, link-local IPv4 ou ULA/link-local IPv6.
- O navegador só pode usar `Host` e `Origin` com IP privado/loopback e porta 8765.
- A interface exige PIN numérico de 8 dígitos antes de liberar a fila.
- O PIN fica em `~/.config/orvani-share/share.env` com permissão 0600.
- A sessão é assinada por HMAC-SHA256 com segredo aleatório persistente.
- Sessão válida por 7 dias, cookie HttpOnly + SameSite=Strict.
- Cinco tentativas inválidas em 5 minutos bloqueiam novas tentativas daquele IP
  por 15 minutos.
- `/api/health` e os arquivos estáticos podem ser acessados sem sessão, mas
  `/api/items` e qualquer alteração de status exigem sessão válida.
- POST exige `Origin` permitido para reduzir CSRF.
- Nenhuma porta de roteador é aberta e nenhuma regra de firewall é alterada.
- Nenhum segredo da Orvani é enviado ao navegador.
- Clipboard possui fallback para HTTP em IP local, pois `navigator.clipboard`
  pode estar indisponível fora de contexto seguro.
- Acesso fora de casa por 4G/5G não faz parte desta etapa; isso ficará para
  Tailscale ou solução equivalente.

## Operação

Após instalação:

```bash
orvani-share-access
```

O comando mostra URL local, URLs IPv4 privadas e o PIN atual.
