---
name: setup-diretor
description: 'Guia o Felipe (diretor do hospital, não desenvolvedor), um passo por vez, do zero até planejar e prototipar o app no Mac dele com o Claude Max, numa cópia local com dados fictícios, e abrir o card para o time no GitHub. Também é o roteiro do dia a dia dele depois do setup. Use quando o diretor disser "/setup-diretor", "me ajuda a configurar", "quero planejar uma ideia", "quero testar uma mudança", "abre um card", "o que está no meu nome", "guarda este arquivo", ou quando a sessão roda num fork do hospital-reunioes no Mac do diretor.'
---

# Setup do diretor

Quem fala com você é o **Felipe**, diretor do hospital. Ele não é desenvolvedor e não tinha conta no GitHub. Desde 24/11/2026 ele planeja as ideias de mudança no Claude dele (Claude Max, Claude Desktop, Mac M5 Pro) em vez da aba Tecnologia do app, que custava cerca de US$ 0,21 por pergunta na API. Esta skill leva ele do zero até seis coisas:

1. Planejar uma ideia (`/grill-with-docs`).
2. Prototipar no Mac dele, com o app rodando local e o banco local com dados fictícios, nunca produção (`/prototype`).
3. Escrever o PRD e a ideia de mudança no código.
4. Abrir o card (issue) no repositório para o time.
5. Guardar o Arquivo de apoio no repositório privado `hospital-arquivos`.
6. Receber, responder, devolver e fechar a Tarefa do diretor.

O texto que o Felipe lê, passo a passo, está em `references/passo-a-passo.md`. As mensagens para ele mandar ao Pedro estão em `references/pedro.md`. O formato do card está em `references/modelo-do-card.md`. Leia os três antes do primeiro passo.

**Antes do clone** (a pasta ainda não existe no Mac dele), leia os mesmos arquivos pelo endereço público do repositório:

https://raw.githubusercontent.com/Vitta-Share/hospital-reunioes/main/.claude/skills/setup-diretor/SKILL.md

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

- **Nada vai para produção daqui.** Nunca rode `/pegar-issue`, `/tdd`, `/ship`, `/onda-enxuta`, `/montar-ondas-enxutas`, `fechar_onda.py`, `/deploy`, `/divulgar`, `/apresentar-prd`, `/guia-humano` nem `/mensagem-prd`. Nunca mergeie nada e nunca marque um PR como pronto para revisão: o PR dele é sempre rascunho. Desde 25/11/2026 o Felipe é colaborador do repositório (ADR 0113, decisão 2), para receber, devolver e fechar card; o código dele continua saindo do fork. Duas travas seguram o merge: a negação no `settings.json` do Claude dele (Parte 5) e o check `PR do diretor assumido`, que reprova o PR dele até um Desenvolvedor pôr a label `assumido`. Nunca tire a negação e nunca ponha nem tire a label `assumido`: ela é da Vitta.
- **Nunca produção, nunca chave real.** Nada de Coolify, do Studio de produção (`studio.hospitalsaomatheus.cloud`) nem de login no app de produção para testar. O `hospital-reunioes/.env` dele só tem valores do Supabase local, gerados pelo `scripts/env_local.sh`. Chave de IA e de e-mail ficam vazias: com elas vazias o app local usa respostas simuladas e não gasta nada. Nunca peça chave de API a ele nem ao Pedro: o motivo de ele planejar aqui é não pagar API.
- **Nunca dado real.** O repositório é público. Dado fictício só no banco local, com nome inventado (nunca nome de paciente, de funcionário nem de médico de verdade). Print que vai para o card sai do app local, nunca de produção.
- **Arquivo que ele mandar** (especificação, planilha, memória de cálculo, PDF) é Arquivo de apoio: vai para o repositório privado `hospital-arquivos`, na pasta do card (Parte 10), e o card leva só o link (ADR 0113, decisão 11). Nunca vai para o commit do repositório público nem como anexo do card. Antes de qualquer commit no `hospital-reunioes`, `git status --short` não pode listar nada de `local/` nem `.env`.
- **Bug não nasce aqui.** Se ele contar um erro do app, não investigue nem abra card: aponte o Assistente do app, o robô no canto inferior direito do app do hospital, que conduz o relato (ADR 0113, decisão 8). Daqui saem só melhorias.
- **Actions do fork ficam desligadas.** O GitHub desliga os workflows num fork novo; não ligue.
- **O `CLAUDE.md` do repositório manda "nunca parar para perguntar".** Aqui é o contrário: dúvida de negócio se pergunta ao Felipe na hora; dúvida técnica que ele não sabe responder vira linha de "Ficou em aberto" no card, e o Pedro resolve no grill técnico.

## As partes

O texto de cada parte, com o "Como saber que acabou", está em `references/passo-a-passo.md`.

| Parte | O que entrega | Quem faz o quê |
|---|---|---|
| 0. Claude Max e Claude Desktop | O Claude dele aberto | Ele, pela mensagem do Pedro (antes desta skill existir no Mac) |
| 1. Conta no GitHub | Conta com verificação em duas etapas e o login mandado ao Pedro | Ele cria; o Pedro põe o login em `DIRETOR_LOGINS` e convida |
| 2. Ferramentas | Homebrew, git, `gh`, `jq`, Node 22 com `corepack pnpm@9`, `uv`, Supabase CLI e Docker Desktop | Homebrew e Docker pelas mãos dele; o resto você instala |
| 3. GitHub conectado e a cópia baixada | `gh auth login`, fork, clone em `~/hospital-reunioes`, `git config` | `gh auth login` ele roda no Terminal; fork e clone você faz |
| 4. A cópia do app | Supabase local com o seed, `.env` local, app em `http://localhost:3000` | Você roda; ele entra no app e confirma que viu a tela |
| 5. O Claude do jeito do time | 4 plugins do repositório, `playwright-cli` e a trava do merge | Você instala; ele reabre o Claude |
| 6. O convite do time | Colaborador do `hospital-reunioes` e do `hospital-arquivos` | Você aceita os convites pelo `gh`, depois da trava |
| 7. Planejar uma ideia | Entende as skills de planejamento e o porquê de cada uma | Leitura guiada |
| 8. Prototipar | Branch `prototype/<N>-<slug>` no fork, prints, PR rascunho | Você faz; ele testa na tela |
| 9. Abrir o card | Issue no repositório do time, no formato do PRD do diretor | Você escreve e cria; ele aprova o texto antes |
| 10. Arquivo de apoio | O arquivo na pasta do card no `hospital-arquivos` e o link no card | Você guarda e comenta; ele diz qual arquivo e qual card |
| 11. A Tarefa do diretor | O card no nome dele respondido, devolvido ou fechado | Você lê, escreve e devolve; ele decide e aprova o texto |

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
cd ~ && gh repo fork Vitta-Share/hospital-reunioes --clone --default-branch-only
cd ~/hospital-reunioes && git remote -v   # origin = fork dele, upstream = Vitta-Share
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

A lista de plugins vem de `.claude/skills/setup-maquina/references/plugins.txt`; se ela mudar, siga a lista. Nenhum MCP: tudo o que ele faz passa por `gh`, `git`, `docker` e `supabase`.

Depois dos plugins, grave a trava do merge (ADR 0113, decisão 2): o Claude dele fica proibido de mergear pelo `gh` e pela API. Vai no mesmo `~/.claude/settings.json`, sem apagar o que já está lá:

```bash
CFG="$HOME/.claude/settings.json"; mkdir -p "$HOME/.claude"; [ -f "$CFG" ] || echo '{}' > "$CFG"
jq '.permissions.deny = (((.permissions.deny // []) + ["Bash(gh pr merge:*)", "Bash(gh api *merge*)"]) | unique)' "$CFG" > "$CFG.novo" && mv "$CFG.novo" "$CFG"
```

A trava entra antes do convite (Parte 6): quando ele vira colaborador, o Claude dele já não mergeia. Depois, ele fecha e abre o Claude de novo, e o `conferir.sh` mostra `OK` na linha "trava do merge".

### Parte 6: o convite

Só depois da linha "trava do merge" em `OK`. O Pedro convida o login dele no `Vitta-Share/hospital-reunioes` e no `pedrorezendefig/hospital-arquivos` (mensagem "Conta criada"). Aceite você, pelo `gh`, os convites desses dois repositórios:

```bash
gh api user/repository_invitations --jq '.[] | "\(.id) \(.repository.full_name)"'
gh api -X PATCH user/repository_invitations/<id>      # um por convite, só esses dois repositórios
```

Sem convite na lista: mande a mensagem "Sem convite" de `references/pedro.md`. Pronto quando o `conferir.sh` mostra `OK` em "colaborador do time" e "hospital-arquivos". O código dele continua saindo do fork (Parte 8): colaborador serve para receber, devolver e fechar card e para guardar o Arquivo de apoio.

### Parte 8: o protótipo

1. Atualize a cópia antes de começar (você roda): `gh repo sync <login>/hospital-reunioes --source Vitta-Share/hospital-reunioes && git checkout main && git pull`.
2. Chame a skill `prototype`. A branch é `prototype/<N>-<slug>`, onde `<N>` é o número do card (se o card ainda não existe, abra-o primeiro pela Parte 9 e volte). O código do protótipo é descartável: responde uma pergunta de tela ou de regra, não vira o código final.
3. Dados que a tela precisa: crie no banco local, com nomes inventados.
4. Suba de novo com a skill `atualizar-app --yes` e peça que ele teste na tela. Ajuste até ele dizer que é isso.
5. Prints pelo `playwright-cli` (2x, tela inteira), gravados em `docs/prototipos/<N>/` dentro da branch do protótipo.
6. Commit e push para o fork (`origin`). Confira antes: nada de `local/`, `.env` ou dado real no `git status`.
7. PR rascunho do fork para o repositório do time:

   ```bash
   gh pr create --draft --repo Vitta-Share/hospital-reunioes --head <login>:prototype/<N>-<slug> --base main \
     --title "Protótipo: <título do card>" --body-file <arquivo>
   ```

   O corpo diz o que o protótipo responde, como testar e `Refs #<N>` (nunca `Closes`: o protótipo não fecha o card). Depois, comente no card o link do PR.

   A edição por mantenedores fica ligada (é o padrão do `gh pr create`; nunca use `--no-maintainer-edit`): é por ela que a Vitta continua na mesma branch do fork.

O PR é o ponto de partida (ADR 0113, decisão 3), e ele nunca mergeia. Quando um Desenvolvedor da Vitta assume, põe a label `assumido`, que é o que o check `PR do diretor assumido` espera para deixar de reprovar, continua na mesma branch, completa com teste e leva pela subida.

### Parte 9: o card

1. Escreva o corpo no formato de `references/modelo-do-card.md`, com o que saiu do `/grill-with-docs` e, se houver, do protótipo.
2. Passe o bloco "Para o diretor" e a primeira linha pela skill `humanizer`, em modo embutido (ADR 0071), com a amostra de voz que `references/modelo-do-card.md` indica.
3. Mostre o texto inteiro a ele e espere o "pode criar".
4. Crie no repositório do time, nunca no fork:

   ```bash
   gh issue create --repo Vitta-Share/hospital-reunioes --title "<título curto>" --body-file <arquivo>
   ```

5. A Action `card-do-diretor.yml` põe `needs-triage` e `origem:diretor` e designa o Pedro em segundos. Confira com `gh issue view <N> --repo Vitta-Share/hospital-reunioes --json labels,assignees`. Sem as labels depois de um minuto, o login dele ainda não está em `DIRETOR_LOGINS`: mande a mensagem "Card sem label" de `references/pedro.md`.
6. Dê a ele o link do card e a mensagem "Card novo" de `references/pedro.md`.

O card nasce `needs-triage` porque o Pedro faz o grill técnico (`/grill-with-docs #N`) e só o `/to-prd` dele vira `ready-for-agent`. Não use `/to-prd` nem `/to-issues` aqui: os dois publicam como trabalho pronto para o time.

### Parte 10: o Arquivo de apoio

O arquivo que a Vitta precisa ler na hora do código (ADR 0113, decisão 11) vai para o repositório privado, numa pasta com o número do card. O card, público, leva só o link; nunca anexe o arquivo ao card nem cite o conteúdo dele no comentário.

```bash
[ -d ~/hospital-arquivos ] || gh repo clone pedrorezendefig/hospital-arquivos ~/hospital-arquivos
cd ~/hospital-arquivos && git pull && mkdir -p <N> && cp "<caminho do arquivo>" <N>/
git add <N> && git commit -m "Arquivo de apoio do card <N>" && git push
gh issue comment <N> --repo Vitta-Share/hospital-reunioes --body "Arquivo de apoio: https://github.com/pedrorezendefig/hospital-arquivos/tree/main/<N>"
```

Arquivo acima de 100 MB o GitHub recusa: peça a ele uma versão menor. Pronto quando o link do comentário abre a pasta com o arquivo.

### Parte 11: a Tarefa do diretor

O card no nome dele é a Tarefa do diretor (ADR 0113, decisão 4; os comandos do time estão em `docs/agents/issue-tracker.md`). Pergunta leva `needs-info`; coisa a fazer leva `ready-for-human`; o card `implantacao` é coisa a fazer depois do código, que ele combina com quem faz no hospital.

1. O que está no nome dele: `gh issue list --repo Vitta-Share/hospital-reunioes --assignee @me --state open --json number,title,labels,url`.
2. Leia o card escolhido com `gh issue view <N> --repo Vitta-Share/hospital-reunioes --comments` e explique em palavras simples o que pedem, com as opções e a recomendação de quem pediu.
3. Escreva a resposta com ele, mostre e espere o "pode mandar". Publique com `gh issue comment <N> --repo Vitta-Share/hospital-reunioes --body-file <arquivo>`. Arquivo que a resposta precisa vai pela Parte 10, e o comentário leva o link.
4. Pergunta (`needs-info`): devolva o card a quem perguntou, o autor do comentário que menciona o login dele, com `gh issue edit <N> --repo Vitta-Share/hospital-reunioes --remove-assignee @me --add-assignee <login de quem perguntou>`. As labels ficam com a Vitta, que grava a decisão e volta o card a `ready-for-agent`.
5. Coisa a fazer (`ready-for-human` ou `implantacao`): com o "terminei" dele, `gh issue close <N> --repo Vitta-Share/hospital-reunioes --comment "<o que foi feito>"`. O bloqueio nativo solta as fatias que esperavam.

Nunca mexa em card que não está no nome dele, nunca troque label de estado e nunca feche pergunta: quem fecha é quem perguntou.

## Dia a dia, depois do setup

Quando ele voltar com uma ideia:

1. Rode o `conferir.sh`. Docker parado: peça que ele abra o Docker Desktop. Supabase parado: `supabase start`.
2. Atualize a cópia (Parte 8, passo 1) e suba o app (skill `atualizar-app --yes`).
3. `/grill-with-docs` com ele sobre a ideia.
4. Protótipo se a ideia mexe em tela ou em regra que ele quer ver funcionando; senão, direto ao card.
5. Card (Parte 9) e mensagem ao Pedro.

Quando ele perguntar o que está no nome dele, siga a Parte 11; quando mandar um arquivo, a Parte 10. Quando ele contar um bug, aponte o Assistente do app (regras do modo diretor).

## Conferência

```bash
bash .claude/skills/setup-diretor/scripts/conferir.sh
```

Uma linha por item, `OK` ou `FALTA` com o conserto ao lado: Homebrew, git, `gh` logado, Node 22.12 ou mais, `pnpm@9` pelo corepack, `uv`, Supabase CLI, Docker respondendo, o clone com `origin` no fork e `upstream` no repositório do time, o `.env` local ignorado pelo git e sem endereço de produção, Supabase local no ar, app em `:8000` e `:3000`, `playwright-cli`, os plugins, a trava do merge no `settings.json`, colaborador do time e acesso de escrita ao `hospital-arquivos`. O script nunca imprime valor de chave.

## O que esta skill nunca faz

- Nunca toca produção, Coolify, Vercel nem 1Password.
- Nunca pede, lê ou grava senha, código de verificação ou chave de API.
- Nunca usa `sudo`: o que pede a senha do Mac ele faz no Terminal.
- Nunca commita `.env`, nada de `local/` nem dado real.
- Nunca mergeia, nunca tira PR de rascunho, nunca roda a subida.
