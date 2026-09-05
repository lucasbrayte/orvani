# Orvani — Backfill da Central de Divulgação

## Objetivo

Adicionar à aba `Divulgação` os produtos antigos que já estavam publicados
antes da Central, sem duplicar itens e sem alterar `Importações` ou `Produtos`.

## Regras

- Apenas Importações com `Status = PUBLICADO`, `Ativo = Sim` e `Publicar = Sim` são candidatas.
- O produto precisa continuar existindo em `Produtos` e estar ativo.
- A divulgação usa os dados atuais de `Produtos`.
- O mesmo `ID Automação` mantém o mesmo `ID Divulgação`; executar novamente é idempotente.
- Produtos já presentes em `Divulgação` não são duplicados.
- Produto ausente, inativo ou inválido é contabilizado e ignorado individualmente.
- `--dry-run` nunca escreve na planilha.
- O modo real exige confirmação explícita no GitHub Actions.
- Nenhuma automação não oficial do WhatsApp é adicionada.

## Fluxo

`Importações antigas PUBLICADO -> Produtos atuais -> Divulgação -> Central local`

## Comandos

```bash
python -m automation.cli backfill-divulgation --dry-run
python -m automation.cli backfill-divulgation
```
