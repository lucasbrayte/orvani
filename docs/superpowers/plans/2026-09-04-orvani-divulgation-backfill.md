# Divulgação Legacy Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inserir com segurança na Central de Divulgação os produtos antigos já publicados, com dry-run e idempotência.

**Architecture:** Um planejador puro recebe Importações, Produtos já parseados e a fila Divulgação atual. O CLI orquestra leitura e escrita pelo gateway existente; o GitHub Actions expõe modos manuais separados para dry-run e execução confirmada.

**Tech Stack:** Python 3.12, Google Sheets API existente, pytest, Bash, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-04-orvani-divulgation-backfill-design.md`

## Global Constraints

- Não alterar o fluxo automático de novos produtos.
- Não duplicar `ID Divulgação`.
- `--dry-run` faz zero escritas.
- Execução real exige confirmação explícita.
- Itens inválidos são contabilizados e ignorados individualmente.
- Não alterar a Central local nem automatizar publicação no WhatsApp.

---

### Task 1: Planejador idempotente

**Files:** `automation/divulgation_backfill.py`, `tests/test_divulgation_backfill.py`

- [ ] Escrever RED para módulo ausente e um publicado antigo.
- [ ] Implementar filtro PUBLICADO/Sim/Sim e `SheetUpdate` idempotente.
- [ ] Cobrir duplicata, produto ausente, produto inativo e item inválido.
- [ ] Executar GREEN.

### Task 2: CLI com dry-run

**Files:** `automation/cli.py`, `tests/test_divulgation_backfill.py`

- [ ] Escrever RED para `backfill-divulgation --dry-run`.
- [ ] Ler Importações, Produtos e Divulgação pelo gateway existente.
- [ ] Dry-run não escreve; modo real escreve somente `report.updates`.
- [ ] Executar GREEN e regressões.

### Task 3: GitHub Actions protegido

**Files:** `.github/scripts/run-affiliate-sync.sh`, `.github/workflows/sync-affiliates.yml`

- [ ] Expor `backfill-dry-run` e `backfill`.
- [ ] Exigir `confirm_backfill=true` para escrita real.
- [ ] Rodar shell check, regressões, commit, fast-forward, pós-merge e push.
