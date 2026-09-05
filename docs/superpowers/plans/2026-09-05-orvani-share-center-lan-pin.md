# Share Center LAN + PIN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir acesso seguro à Central de Divulgação pelo celular na mesma rede local usando PIN e sessão assinada.

**Architecture:** A Central passa a escutar em IPv4 em todas as interfaces, porém cada requisição é filtrada por IP privado e Host/Origin local. Um módulo de autenticação independente fornece validação de PIN, sessão HMAC e rate limiting; a UI ganha tela de login e fallback de clipboard para HTTP local.

**Tech Stack:** Python 3.12 standard library, HTML/CSS/JavaScript, systemd user service, Bash.

**Spec:** `docs/superpowers/specs/2026-09-05-orvani-share-center-lan-pin-design.md`

## Global Constraints

- Nenhuma mudança em `automation/`, `libreoffice_sync/`, Google Sheets ou backfill.
- Porta fixa 8765.
- PIN exatamente 8 dígitos.
- Sessão de 7 dias.
- Cinco falhas em 5 minutos bloqueiam o IP por 15 minutos.
- Clientes públicos são rejeitados mesmo se a porta for encaminhada no roteador.
- Não alterar firewall automaticamente.
- Não implementar acesso 4G/5G nesta etapa.

---

### Task 1: Política de rede e autenticação

**Files:**
- Create: `share_center/auth.py`
- Modify: `share_center/server.py`
- Modify: `tests/test_share_center.py`
- Create: `tests/test_share_center_lan_access.py`

- [ ] Escrever testes RED para bind LAN, política de IP, sessão, PIN e rate limit.
- [ ] Executar testes e confirmar RED por funcionalidade ausente.
- [ ] Implementar módulo de autenticação com HMAC e comparação constante.
- [ ] Integrar autenticação ao servidor e proteger `/api/items` e status.
- [ ] Executar GREEN.

### Task 2: Interface móvel autenticada

**Files:**
- Modify: `share_center/static/index.html`
- Modify: `share_center/static/app.js`
- Modify: `share_center/static/style.css`
- Test: `tests/test_share_center_lan_access.py`

- [ ] Implementar login responsivo e botão Sair.
- [ ] Implementar fallback `execCommand("copy")` para HTTP local.
- [ ] Rodar `node --check` e GREEN.

### Task 3: Instalação e descoberta no Wi-Fi

**Files:**
- Modify: `scripts/install-orvani-share.sh`
- Modify: `scripts/orvani-share-launcher.sh`
- Create: `scripts/orvani-share-access.sh`
- Test: `tests/test_share_center_lan_access.py`

- [ ] Gerar PIN/segredo somente quando a configuração ainda não existir.
- [ ] Preservar PIN e segredo em reinstalações.
- [ ] Reiniciar serviço após copiar a nova versão.
- [ ] Mostrar IPs privados e PIN pelo comando `orvani-share-access`.
- [ ] Rodar regressões, commit, merge, reinstalação, health, push e limpeza.
