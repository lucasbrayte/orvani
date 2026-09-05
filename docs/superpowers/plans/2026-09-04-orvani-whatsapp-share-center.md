# WhatsApp Share Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar uma fila backend idempotente de divulgação e uma Central local segura para preparar publicações manuais no Canal do WhatsApp.

**Architecture:** A automação cria a aba `Divulgação` e adiciona uma linha apenas na primeira publicação de cada `ID Automação`. Um serviço Python local somente em loopback lê essa aba pelo CSV público da mesma planilha, combina os registros com estado local e serve uma UI sem dependências externas.

**Tech Stack:** Python 3.12, Google Sheets API existente, biblioteca padrão Python, HTML/CSS/JavaScript, systemd user service.

**Spec:** `docs/superpowers/specs/2026-09-04-orvani-whatsapp-share-center-design.md`

## Global Constraints

- Sem automação não oficial do WhatsApp.
- Sem segredos no frontend.
- Bind exclusivo em 127.0.0.1:8765.
- Criar divulgação somente na primeira transição para PUBLICADO.
- Mudanças posteriores de catálogo não geram duplicatas.
- Estados locais: PENDENTE, PUBLICADO, ARQUIVADO.
- Preservar Mercado Livre, Shopee, SHEIN e Amazon.

---

### Task 1: Contrato da fila backend

**Files:** `automation/config.py`, `automation/sheets.py`, `automation/models.py`, `automation/sync.py`, `automation/cli.py`, `tests/test_divulgation_queue.py`

- [ ] Escrever testes RED para cabeçalhos, ID determinístico, primeira publicação e deduplicação.
- [ ] Criar `DIVULGATION_HEADERS` e criação idempotente da aba.
- [ ] Planejar uma linha A:K somente quando o item muda de não-publicado para PUBLICADO.
- [ ] Escrever Produtos, depois Divulgação, e somente então expor PUBLICADO.
- [ ] Rodar GREEN e regressões.

### Task 2: Central local

**Files:** `share_center/*`, `tests/test_share_center.py`

- [ ] Escrever testes RED para CSV, moeda, texto e estado local.
- [ ] Implementar parser estrito da aba Divulgação.
- [ ] Implementar estado local atômico com permissão 0600.
- [ ] Implementar HTTP somente loopback, proteção de Host/Origin e JSON estrito.
- [ ] Implementar UI de cards e ações manuais.
- [ ] Rodar GREEN e checagem sintática do JavaScript.

### Task 3: Instalação e acionamento

**Files:** `scripts/install-orvani-share.sh`, `scripts/orvani-share-launcher.sh`, `systemd/orvani-share.service`, `.github/workflows/sync-affiliates.yml`

- [ ] Instalar a Central em `~/.local/share/orvani-share`.
- [ ] Habilitar e iniciar `orvani-share.service`.
- [ ] Disparar sync backend em push de mudanças da automação.
- [ ] Verificar health local, regressões, commit, fast-forward, push e limpeza.
