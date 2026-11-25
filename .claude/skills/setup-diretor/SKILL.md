---
name: setup-diretor
description: 'Guia o Felipe (diretor do hospital, não desenvolvedor), um passo por vez, do zero até planejar e prototipar o app no Mac dele com o Claude Max, numa cópia local com dados fictícios, e abrir o card para o time no GitHub. Também é o roteiro do dia a dia dele depois do setup. Use quando o diretor disser "/setup-diretor", "me ajuda a configurar", "quero planejar uma ideia", "quero testar uma mudança", "abre um card", ou quando a sessão roda num fork do hospital-reunioes no Mac do diretor.'
---

# Setup do diretor

Quem fala com você é o **Felipe**, diretor do hospital. Ele não é desenvolvedor e não tinha conta no GitHub. Desde 24/11/2026 ele planeja as ideias de mudança no Claude dele (Claude Max, Claude Desktop, Mac M5 Pro) em vez da aba Tecnologia do app, que custava cerca de US$ 0,21 por pergunta na API. Esta skill leva ele do zero até quatro coisas:

1. Planejar uma ideia (`/grill-with-docs`).
2. Prototipar no Mac dele, com o app rodando local e o banco local com dados fictícios, nunca produção (`/prototype`).
3. Escrever o PRD e a ideia de mudança no código.
4. Abrir o card (issue) no repositório para o time.

O texto que o Felipe lê, passo a passo, está em `references/passo-a-passo.md`. As mensagens para ele mandar ao Pedro estão em `references/pedro.md`. O formato do card está em `references/modelo-do-card.md`. Leia os três antes do primeiro passo.

**Antes do clone** (a pasta ainda não existe no Mac dele), leia os mesmos arquivos pelo endereço público do repositório:

https://raw.githubusercontent.com/pedrorezendefig/hospital-reunioes/main/.claude/skills/setup-diretor/SKILL.md

Troque `SKILL.md` por `references/passo-a-passo.md`, `references/pedro.md` e `references/modelo-do-card.md`.

## Como conduzir

- **Um passo por vez.** Mostre um passo, espere o "feito" (ou "pronto", "ok"), confira e só então mostre o próximo. Nunca despeje a parte inteira.
- **Confira sempre por comando**, nunca pela palavra dele: `bash .claude/skills/setup-diretor/scripts/conferir.sh` depois do clone, e o comando de cada passo antes disso. Se a conferência falhar, explique em uma frase o que viu e repita só o passo que faltou.
- **Comece pelo diagnóstico.** Antes do clone, pergunte o que ele já fez (Max, Claude Desktop, conta no GitHub) e comece na primeira parte que falta. Depois do clone, rode o `conferir.sh` e comece na primeira linha `FALTA`.
- **Escreva para leigo:** onde clicar, o que digitar, o que aparece na tela. Link inteiro, sozinho na linha, começando por `https://`. Sem jargão; quando um termo técnico é inevitável (fork, branch, PR), explique numa frase na primeira vez.
- **Faça você o que dá para fazer.** Instalação pelo Homebrew, clone, subir o app, conferir: rode você mesmo. Ele só faz o que exige o dedo dele: criar conta, digitar a senha do Mac, aprovar o login no navegador, abrir e arrastar um app.
- **Senha do Mac, senha do GitHub e código de verificação:** quem digita é ele, no lugar certo (Terminal ou navegador). Nunca peça nem leia nenhum desses no chat.
- **Mensagem para o Pedro:** sempre pronta, num bloco de código, tirada de `references/pedro.md`, com o que for específico (login, número do card) já preenchido.
- Texto novo que ele vai ler (o bloco "Para o diretor" do card, um resumo) passa pela skill `humanizer` antes de gravar. Sem travessão nem meia-risca em nada.

## Regras do modo diretor

Valem por cima do `CLAUDE.md` do repositório, que foi escrito para os sócios desenvolvedores.

- **Nada vai para produção daqui.** Nunca rode `/pegar-issue`, `/tdd`, `/ship`, `/onda-enxuta`, `/montar-ondas-enxutas`, `fechar_onda.py`, `/deploy`, `/divulgar`, `/apresentar-prd`, `/guia-humano` nem `/mensagem-prd`. Nunca mergeie nada e nunca marque um PR como pronto para revisão: o PR dele é sempre rascunho. O Felipe não é colaborador do repositório (trabalha num fork, decisão do Pedro em 24/11/2026), então o GitHub já recusa merge e push no repositório do time; a regra é para não tentar.
- **Nunca produção, nunca chave real.** Nada de Coolify, do Studio de produção (`studio.hospitalsaomatheus.cloud`) nem de login no app de produção para testar. O `hospital-reunioes/.env` dele só tem valores do Supabase local, gerados pelo `scripts/env_local.sh`. Chave de IA e de e-mail ficam vazias: com elas vazias o app local usa respostas simuladas e não gasta nada. Nunca peça chave de API a ele nem ao Pedro: o motivo de ele planejar aqui é não pagar API.
- **Nunca dado real.** O repositório é público. Dado fictício só no banco local, com nome inventado (nunca nome de paciente, de funcionário nem de médico de verdade). Print que vai para o card sai do app local, nunca de produção.
- **Arquivo que ele mandar** (especificação, planilha, memória de cálculo, PDF) vai para `local/<tema>/`, que o git ignora, e nunca para o commit (ADR 0070: o que o diretor mandou para o Contas médicas fica em `local/contas-medicas/`). Antes de qualquer commit, `git status --short` não pode listar nada de `local/` nem `.env`.
- **Actions do fork ficam desligadas.** O GitHub desliga os workflows num fork novo; não ligue.
- **O `CLAUDE.md` do repositório manda "nunca parar para perguntar".** Aqui é o contrário: dúvida de negócio se pergunta ao Felipe na hora; dúvida técnica que ele não sabe responder vira linha de "Ficou em aberto" no card, e o Pedro resolve no grill técnico.

## As partes

O texto de cada parte, com o "Como saber que acabou", está em `references/passo-a-passo.md`.

| Parte | O que entrega | Quem faz o quê |
|---|---|---|
| 0. Claude Max e Claude Desktop | O Claude dele aberto | Ele, pela mensagem do Pedro (antes desta skill existir no Mac) |
| 1. Conta no GitHub | Conta com verificação em duas etapas e o login mandado ao Pedro | Ele cria; o Pedro põe o login em `DIRETOR_LOGINS` |
| 2. Ferramentas | Homebrew, git, `gh`, `jq`, Node 22 com `corepack pnpm@9`, `uv`, Supabase CLI e Docker Desktop | Homebrew e Docker pelas mãos dele; o resto você instala |
| 3. GitHub conectado e a cópia baixada | `gh auth login`, fork, clone em `~/hospital-reunioes`, `git config` | `gh auth login` ele roda no Terminal; fork e clone você faz |
| 4. A cópia do app | Supabase local com o seed, `.env` local, app em `http://localhost:3000` | Você roda; ele entra no app e confirma que viu a tela |
| 5. O Claude do jeito do time | 4 plugins do repositório e `playwright-cli` | Você instala; ele reabre o Claude |
| 6. Planejar uma ideia | Entende as skills de planejamento e o porquê de cada uma | Leitura guiada |
| 7. Prototipar | Branch `prototype/<N>-<slug>` no fork, prints, PR rascunho | Você faz; ele testa na tela |
| 8. Abrir o card | Issue no repositório do time, no formato do PRD do diretor | Você escreve e cria; ele aprova o texto antes |

### Parte 2: os comandos

Homebrew pede a senha do Mac, então vai no Terminal (o texto está no passo a passo). Depois dele, rode você, um por vez, e confira cada um:

```bash
brew install git gh jq uv supabase/tap/supabase node@22
brew link --overwrite --force node@22
corepack enable && echo y | corepack pnpm@9 --version
```

Docker Desktop é o `.dmg` para Apple Silicon (link no passo a passo); ele abre, arrasta para Aplicativos, aceita os termos e pula o login. Se o `docker` não estiver no PATH, use `/Applications/Docker.app/Contents/Resources/bin/docker`.

### Parte 3: fork e clone

Depois do `gh auth login` (no Terminal, pelas mãos dele) e do `gh auth status` verde:

```bash
cd ~ && gh repo fork pedrorezendefig/hospital-reunioes --clone --default-branch-only
cd ~/hospital-reunioes && git remote -v   # origin = fork dele, upstream = pedrorezendefig
git config --global user.name "<nome dele>"
git config --global user.email "<ID>+<login>@users.noreply.github.com"
```

O e-mail sai de `gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"'`: assim o e-mail pessoal dele não vai para o repositório público. Depois do clone, peça que ele abra uma conversa nova do Claude na pasta `hospital-reunioes` (texto no passo a passo): é ali que esta skill, as do time e o `CLAUDE.md` passam a valer.

### Parte 4: a cópia do app

```bash
cd ~/hospital-reunioes/hospital-reunioes && supabase start      # primeira vez: 5 a 10 minutos
bash ../.claude/skills/setup-diretor/scripts/env_local.sh        # grava o .env só com valores locais
```

Depois chame a skill `atualizar-app` com `--yes` (ele não precisa ver o preview). Na primeira vez o build leva alguns minutos. Pronto quando `http://localhost:8000/api/health` responde e `http://localhost:3000` abre a tela de login. Ele entra com o usuário do seed (`admin@hospital.com`, senha `Admin@123!`, só existe no banco local) e confirma que viu o menu.

### Parte 5: plugins e playwright-cli

Sem o comando `claude` no Terminal (o Claude Desktop não instala), instale antes com `npm install -g @anthropic-ai/claude-code`; os plugins ficam em `~/.claude/settings.json`, que o Desktop e o Terminal leem.

```bash
claude plugin install code-review@claude-plugins-official
claude plugin install security-guidance@claude-plugins-official
claude plugin install context7@claude-plugins-official
claude plugin install skill-creator@claude-plugins-official
npm install -g @playwright/cli@latest && playwright-cli install --skills
```

A lista de plugins vem de `.claude/skills/setup-maquina/references/plugins.txt`; se ela mudar, siga a lista. Nenhum MCP: tudo o que ele faz passa por `gh`, `git`, `docker` e `supabase`. Depois, ele fecha e abre o Claude de novo.

### Parte 7: o protótipo

1. Atualize a cópia antes de começar (você roda): `gh repo sync <login>/hospital-reunioes --source pedrorezendefig/hospital-reunioes && git checkout main && git pull`.
2. Chame a skill `prototype`. A branch é `prototype/<N>-<slug>`, onde `<N>` é o número do card (se o card ainda não existe, abra-o primeiro pela Parte 8 e volte). O código do protótipo é descartável: responde uma pergunta de tela ou de regra, não vira o código final.
3. Dados que a tela precisa: crie no banco local, com nomes inventados.
4. Suba de novo com a skill `atualizar-app --yes` e peça que ele teste na tela. Ajuste até ele dizer que é isso.
5. Prints pelo `playwright-cli` (2x, tela inteira), gravados em `docs/prototipos/<N>/` dentro da branch do protótipo.
6. Commit e push para o fork (`origin`). Confira antes: nada de `local/`, `.env` ou dado real no `git status`.
7. PR rascunho do fork para o repositório do time:

   ```bash
   gh pr create --draft --repo pedrorezendefig/hospital-reunioes --head <login>:prototype/<N>-<slug> --base main \
     --title "Protótipo: <título do card>" --body-file <arquivo>
   ```

   O corpo diz o que o protótipo responde, como testar e `Refs #<N>` (nunca `Closes`: o protótipo não fecha o card). Depois, comente no card o link do PR.

O PR nunca é mergeado. Quem implementa de verdade é o time, numa fatia que nasce do card.

### Parte 8: o card

1. Escreva o corpo no formato de `references/modelo-do-card.md`, com o que saiu do `/grill-with-docs` e, se houver, do protótipo.
2. Passe o bloco "Para o diretor" e a primeira linha pela skill `humanizer`.
3. Mostre o texto inteiro a ele e espere o "pode criar".
4. Crie no repositório do time, nunca no fork:

   ```bash
   gh issue create --repo pedrorezendefig/hospital-reunioes --title "<título curto>" --body-file <arquivo>
   ```

5. A Action `card-do-diretor.yml` põe `needs-triage` e `origem:diretor` e designa o Pedro em segundos. Confira com `gh issue view <N> --repo pedrorezendefig/hospital-reunioes --json labels,assignees`. Sem as labels depois de um minuto, o login dele ainda não está em `DIRETOR_LOGINS`: mande a mensagem "Card sem label" de `references/pedro.md`.
6. Dê a ele o link do card e a mensagem "Card novo" de `references/pedro.md`.

O card nasce `needs-triage` porque o Pedro faz o grill técnico (`/grill-with-docs #N`) e só o `/to-prd` dele vira `ready-for-agent`. Não use `/to-prd` nem `/to-issues` aqui: os dois publicam como trabalho pronto para o time.

## Dia a dia, depois do setup

Quando ele voltar com uma ideia:

1. Rode o `conferir.sh`. Docker parado: peça que ele abra o Docker Desktop. Supabase parado: `supabase start`.
2. Atualize a cópia (Parte 7, passo 1) e suba o app (skill `atualizar-app --yes`).
3. `/grill-with-docs` com ele sobre a ideia.
4. Protótipo se a ideia mexe em tela ou em regra que ele quer ver funcionando; senão, direto ao card.
5. Card (Parte 8) e mensagem ao Pedro.

## Conferência

```bash
bash .claude/skills/setup-diretor/scripts/conferir.sh
```

Uma linha por item, `OK` ou `FALTA` com o conserto ao lado: Homebrew, git, `gh` logado, Node 22.12 ou mais, `pnpm@9` pelo corepack, `uv`, Supabase CLI, Docker respondendo, o clone com `origin` no fork e `upstream` no repositório do time, o `.env` local ignorado pelo git e sem endereço de produção, Supabase local no ar, app em `:8000` e `:3000`, `playwright-cli` e os plugins. O script nunca imprime valor de chave.

## O que esta skill nunca faz

- Nunca toca produção, Coolify, Vercel nem 1Password.
- Nunca pede, lê ou grava senha, código de verificação ou chave de API.
- Nunca usa `sudo`: o que pede a senha do Mac ele faz no Terminal.
- Nunca commita `.env`, nada de `local/` nem dado real.
- Nunca mergeia, nunca tira PR de rascunho, nunca roda a subida.
