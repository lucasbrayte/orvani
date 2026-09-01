# Operação segura da automação de afiliados

Este guia é para quem opera a planilha e o workflow. A automação preserva exatamente os 20 cabeçalhos de `Produtos` e as 32 colunas de `Importações`. Ela não apaga produtos, não despublica itens e não altera o CSV público consumido pelo frontend.

## Antes de qualquer escrita

1. Crie um [projeto gratuito no Google Cloud](https://docs.cloud.google.com/resource-manager/docs/creating-managing-projects).
2. Habilite **somente** a [Google Sheets API (`sheets.googleapis.com`)](https://developers.google.com/workspace/guides/enable-apis). Não habilite APIs de Drive ou outras APIs sem decisão separada.
3. Crie uma [conta de serviço exclusiva](https://docs.cloud.google.com/iam/docs/service-accounts-create) para esta automação. Crie localmente uma chave JSON dessa conta conforme o guia de [criar e excluir chaves](https://docs.cloud.google.com/iam/docs/keys-create-delete). A chave é segredo: não a envie em chat, não a versione e não a imprima em logs.
4. Abra a planilha cujo ID fixo é `1oj0NbAkngUjjaYfJy5sEgzfDb7I0klHaUbvTzq6ZDB0` e compartilhe **diretamente apenas essa planilha** com o e-mail da conta de serviço, como **Editor**. Não amplie o acesso geral da planilha; confira as opções de [compartilhamento restrito](https://support.google.com/docs/answer/2494822).
5. No repositório GitHub, crie o secret `GOOGLE_SERVICE_ACCOUNT_JSON` com o conteúdo integral do JSON. Siga o guia de [secrets de repositório](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) e as práticas de [uso seguro de secrets](https://docs.github.com/en/actions/reference/security/secure-use). Nunca cole esse valor em issue, chat, commit ou log.
6. Configure as variáveis do repositório `ORVANI_IMPORT_WORKSHEET=Importações` e `ORVANI_PRODUCTS_WORKSHEET=Produtos`. `ORVANI_SPREADSHEET_ID` é fixo no código e não deve ser trocado.

Os comandos abaixo são instruções para o operador, não evidência de que foram executados neste repositório. Configure o JSON somente no ambiente local ou no secret do GitHub; não inclua a chave em `.env.example`.

```bash
.venv/bin/python -m automation.cli setup-sheet --dry-run
```

Se a aba `Importações` ainda não existir, `validate` encerrará com erro operacional até que o setup aprovado a crie. O primeiro comando que escreve é o seguinte. Ele continua proibido até que o proprietário analise a saída de `setup-sheet --dry-run` e autorize essa escrita separadamente:

```bash
.venv/bin/python -m automation.cli setup-sheet
```

Depois da criação autorizada, execute a validação e os dois dry-runs antes de qualquer sincronização real:

```bash
.venv/bin/python -m automation.cli validate
.venv/bin/python -m automation.cli sync --mode pending --dry-run
.venv/bin/python -m automation.cli sync --mode full --dry-run
```

## Operação manual e conteúdo

1. No GitHub Actions, abra o workflow **Sync affiliate catalog**, clique em **Run workflow** e escolha `setup-dry-run`, `validate`, `pending` ou `full`, conforme o [disparo manual oficial](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow). `validate` é a opção padrão. `setup-dry-run` apenas planeja o setup estrutural da aba `Importações` — criação quando ausente ou ajustes estruturais quando existente — sem escrever; o setup real não fica disponível nesse seletor antes da autorização separada. Depois da criação autorizada, use `validate` e os dry-runs locais antes da primeira sincronização real; `pending` trata a fila e `full` atualiza o catálogo elegível.
2. Para adicionar um item, inclua o link do produto e os campos necessários na aba `Importações`; mantenha `Ativo=Sim`. Para publicar somente após revisão, defina `Publicar=Sim` quando o item estiver pronto. A automação não exclui nem despublica produtos existentes.
3. Links Shopee comuns não são convertidos automaticamente em links de afiliado. Use os grupos oficiais de conversão gerados pela planilha, com no máximo cinco links por grupo/mensagem, e cole o link de afiliado convertido antes de publicar.
4. Para pausar uma linha, defina `Ativo=Não`. Para preservar um item sem atualizá-lo, defina `Modo de Atualização=Bloqueado`. Para pausar tudo, desabilite o workflow no GitHub Actions; reative-o somente com autorização do proprietário.
5. Para revogar acesso, desabilite ou exclua a chave JSON da conta de serviço e remova `GOOGLE_SERVICE_ACCOUNT_JSON` do repositório. Depois, remova o compartilhamento direto da planilha se a conta não for mais usada.

## Agenda, limites e expectativa de operação

O workflow faz execução `full` às **03:17** e **15:17 UTC**. Nos demais horários no minuto **17**, roda `pending`. Execuções agendadas podem atrasar ou ser descartadas sob carga alta da plataforma; consulte o guia oficial de [atrasos de workflow](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows) e use o disparo manual para atualizar quando isso acontecer.

O catálogo é pequeno e as consultas são limitadas, com timeout, redirecionamento restrito e corpo limitado. Isso não garante disponibilidade da loja: bloqueios, mudanças de página ou limites de quota deixam o item para revisão e preservam o catálogo anterior. A operação é deliberadamente semiautomática quando há bloqueio, principalmente para a conversão Shopee.

Na leitura inicial, a amostra Hotmart tinha host incompatível com a regra de host Hotmart; a revalidação pública de 1º de setembro de 2026 não encontrou essa linha no CSV atual, e a automação não a alterou nem a removeu. Nessa mesma revalidação, as amostras atuais de Mercado Livre e Shopee terminaram em `InvalidProductDataError`, sem snapshot normalizado, e por isso permanecem semiautomáticas. SHEIN e TikTok Shop não têm amostra atual validada para um resultado live; não faça alegações de sucesso para essas lojas. A allowlist de TikTok Shop está intencionalmente vazia.

## Smoke tests live opt-in

Por padrão, os testes live são pulados. O opt-in abaixo só é apropriado quando o proprietário autorizar uma verificação externa somente de leitura:

```bash
RUN_LIVE_TESTS=1 .venv/bin/python -m pytest tests/live/test_store_smoke.py -q
```

Ele consulta o CSV público fixo em tempo de execução e seleciona somente linhas ativas de Mercado Livre e Shopee. O export pode seguir exclusivamente o host terminal limitado `doc-…-sheets.googleusercontent.com`; nenhum host amplo de `googleusercontent.com` é aceito. Usa o cliente HTTP seguro e os conectores existentes, sem login, cookies, credenciais, escrita ou impressão de URLs, redirecionamentos, corpos, linhas do CSV e detalhes de erro. Não é deploy nem publicação; neste trabalho não se executa workflow, não se escreve na planilha e não se publica o site.

## Dependências diretas e runtime de testes

As cinco dependências Python diretas são fixadas para instalação reproduzível:

- [`httpx` 0.28.1](https://pypi.org/project/httpx/0.28.1/) fornece o HTTP com limites e validação em torno dele.
- [`google-api-python-client` 2.199.0](https://pypi.org/project/google-api-python-client/2.199.0/) é o transporte da Sheets API.
- [`google-auth` 2.57.0](https://pypi.org/project/google-auth/2.57.0/) carrega a conta de serviço.
- [`pytest` 9.1.1](https://pypi.org/project/pytest/9.1.1/) executa a suíte.
- [`PyYAML` 6.0.3](https://pypi.org/project/PyYAML/6.0.3/) interpreta offline o contrato do workflow.

O [Node 24.20.0](https://nodejs.org/en/download/archive/v24.20.0) é usado somente para executar os testes nativos `node:test`. Ele não é dependência do frontend, não instala dependências e não é um gerenciador de pacotes neste projeto.
