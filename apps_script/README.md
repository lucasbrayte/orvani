# Orvani Apps Script Sync Bridge

## Instalação

1. Abra o projeto Apps Script já vinculado à planilha Orvani.
2. Crie um arquivo de script e copie `apps_script/orvani_sync_webapp.gs`.
3. Em **Configurações do projeto > Propriedades do script**:
   - `ORVANI_SYNC_SECRET=<64 caracteres hexadecimais>`
   - preserve o `GITHUB_TOKEN` existente.
4. Em **Implantar > Nova implantação > Aplicativo da Web**:
   - Executar como: **Eu**
   - Quem pode acessar: **Qualquer pessoa**
5. Copie a URL terminada em `/exec` para `ORVANI_WEBAPP_URL`.
6. Não use a URL `/dev` no serviço Linux.

A URL pública não é a autorização. Cada requisição é autenticada por HMAC-SHA256.

## Checklist

- `onImportacoesEdit` continua instalado.
- `testGitHubDispatch` é apenas diagnóstico manual.
- `ORVANI_SYNC_SECRET` não é commitado.
- `GITHUB_TOKEN` continua apenas nas Script Properties.
- `health` requer assinatura válida.
- Um nonce reutilizado é rejeitado.
- Um lote alterado dispara `pending` uma vez.
- Um lote idêntico não dispara `pending`.
