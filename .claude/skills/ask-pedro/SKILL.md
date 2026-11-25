---
name: ask-pedro
description: Router do pipeline do Hospital Reuniões. Digite /ask-pedro para descobrir qual skill usar agora.
disable-model-invocation: true
---

# Ask Pedro: router do pipeline

Responde "qual skill eu uso agora?" apontando a skill certa e o porquê. Não executa nada; só roteia. Se o pedido do usuário vier junto (`/ask-pedro como subo um fix?`), responda direto com a rota recomendada.

## Qual porta? (antes de tudo)

Nem todo trabalho é PRD. Classifique primeiro; o `/grill-with-docs` faz isso no fechamento, e o `/express` (que fecha o grill em lote) classifica junto com as outras decisões.

| Porta | Quando | Caminho | Por que esse peso |
|---|---|---|---|
| **A. PRD + fatias** | Muda comportamento visível em mais de uma fatia, ou tem migration, ou o diretor precisa saber (bloco "Para o diretor"), ou não cabe numa sessão | `/grill-with-docs` → `/to-prd` → `/to-issues` → `/onda-enxuta` ou `/pegar-issue` | O PRD é o que o diretor lê na aba Tecnologia; a issue é a spec do implementador |
| **B. Issue única, sem PRD** | Uma fatia vertical no app (`hospital-reunioes/`), cabe numa sessão, sem diretor. Várias independentes: `/onda-enxuta --all` ou agentes paralelos na mesma sessão | `/triage` ou `gh issue create` com critérios de aceite → `/pegar-issue N` | PR do app passa pelo `hr-revisor`, e a lente spec × diff precisa dos critérios; os critérios viram os testes do `/tdd`; o funil do OS conta issues |
| **C. PR direto, sem issue** | Ferramenta (`.claude/`, `tools/`, `.github/`, `docs/`) e chore do app que não muda comportamento (texto, lint, config) | Edita na branch → `/ship "<descrição>" --from-diff` → subida. Paralelo: um `Agent` com `isolation: worktree` por mudança, cada um termina no `/ship --skip-review`, e um `fechar_onda.py --prs a b c` no fim | ADR 0068, regra 12: decisão de ferramenta vai no corpo do PR. O OS mostra o PR na aba PRs; sem issue fica fora do funil, e é isso mesmo: o funil é trabalho em aberto |

Teste rápido entre B e C: **alguém precisa conferir que fez o que foi pedido?** Sim: B (precisa de critério escrito). A prova é o diff e o CI: C.

## Fluxo principal (planejar → desenvolver → entregar)

1. **Planejar**: `/grill-with-docs` desafia o plano contra o domínio (uma pergunta por vez, recomendação destacada em cada decisão; atualiza `CONTEXT.md`/ADR via `domain-modeling`). Modo lote (`--lote`, "responde tudo"): todas as lacunas já decididas de uma vez, fecha com "ok" ou "N: correção". No meio do grill, `/express` fecha o resto em lote e publica o painel de aprovação. Dúvida factual de serviço externo no meio do grilling → `/research` em background.
2. **Especificar**: `/to-prd` vira PRD (1 issue `ready-for-agent`, com a seção "Manual: páginas que mudam" em PRD com tela) → `/to-issues` quebra em fatias verticais com label `fatia:P/M/G` e, em PRD com tela, cria a fatia de manual: texto, prints e fluxograma da página do módulo, sem vídeo, bloqueada pelas fatias que mudam a tela (ADR 0094, decisão 6).
3. **Desenvolver**: `/pegar-issue <N>` (claim atômico + branch; sem argumento, lista a fila) → `/tdd` (red → green → refactor). Issue cujo corpo diz "Anexos" traz prints da Demanda, que vivem só no app (ADR 0069): a boca única para baixá-los é `python3 .claude/skills/pegar-issue/scripts/anexos.py <N>` (chave `TECNOLOGIA_AUTOMACAO_API_KEY` no `tokens/.env`), chamada pelo `/pegar-issue`, pelo `hr-implementador` e pelo `hr-corretor`; nenhuma outra skill chama a API do seu jeito, e o `/ship` apaga `local/anexos/<N>/` ao abrir o PR.
4. **Entregar**: `/ship` leva até o **PR verde** (ferramenta, nada em `hospital-reunioes/`: só o CI; app: `hr-revisor` uma vez, com a lente de segurança se o `sensivel.py` acusar e spec × diff se houver issue, mais o CI; must-fix ou CI vermelho chamam o `hr-corretor`) e roda a subida sozinho, sem parada até produção, exceto migration. **Subida única** (ADR 0068): `python3 .claude/skills/onda-enxuta/scripts/fechar_onda.py --prs <N>` mergeia PR a PR pela API (squash), define a versão pelo tipo dos commits sem commit (`APP_VERSION` no Coolify e tag), um build, health e registro gravado pela Action pós-merge (só `history.json` e `state.json`); nenhum push. Serve a um PR avulso ou ao lote de uma onda; quem roda é o `/ship` do autor do PR ou o fechamento da onda. Conflito na subida chama o `hr-corretor` com a `/resolver-conflitos` e conta tentativa; a terceira falha vai para `ready-for-human`. `/deploy` só opera produção (status, rollback, setup Coolify); `/deploy ship` aponta para a subida e sai. O snapshot sai numa Action no push da `main`, depois do registro.

## PRD do diretor (planejado no app)

O diretor faz a metade de negócio do grill no app (ADR 0075). No card aberto de uma Demanda Novo ou Ajuste sem Vínculo, a aba Tecnologia mostra "Planejar com a IA"; o "sim" do resumo cria a issue `needs-triage`, atribuída ao dono (`GITHUB_LOGIN_DONO`), com o PRD do diretor no corpo: bloco "Para o diretor", Problema, Solução, Histórias, Decisões de negócio e "Ficou em aberto". Daí em diante:

1. `/minhas-issues` mostra a issue como "grill técnico pendente". Não há label nova: o script a reconhece pelo marcador da Demanda mais a seção "Ficou em aberto".
2. `/grill-with-docs #N` lista as decisões do diretor como tomadas, sem reperguntar, e grilla só o técnico, começando pelo que ficou em aberto.
3. `/to-prd` completa a mesma issue com as Decisões de implementação e de teste, sem criar outra e sem tocar no bloco "Para o diretor", e troca `needs-triage` por `ready-for-agent`.
4. `/to-issues #N` fatia como num PRD comum; o resto do fluxo principal não muda.

## Modo AFK

- `/minhas-issues [@login]`: check de um minuto antes de escolher o que fazer: semáforo do Actions, o que está em andamento e onde parou, fila por PRD com idade, e plano de até 3 passos com comando pronto (o passo de ondas devolve o `/montar-ondas-enxutas` com recorte), mais o passo a passo de cada `ready-for-human` (por que é humana, o que o agente faz, o que só você faz). "Minha" = atribuída, ou criada sem ninguém atribuído. Não executa nada.
- `/resumo-issues`: visão do time inteiro, sem semáforo nem plano: total de abertas, quantas tem cada pessoa (Pedro, Rib, Lucas, sem responsável) e, por pessoa, os cards agrupados embaixo do título do PRD, cada um com uma linha do que muda. Só leitura.
- `/montar-ondas-enxutas [--exceto #PRD] [--max-sessoes N]`: antes de abrir várias `/onda-enxuta`, monta o plano: inventário que presta contas de toda issue aberta, triagem rápida das `needs-triage` com decisão cravada na issue, pergunta ao humano as decisões de domínio pendentes (2 opções, recomendação na frente) e crava a resposta, agrupamento pela dependência (não pelo arquivo) em sessões sem conflito interno, e um arquivo de prompt mais um comando de lançamento por sessão (sessão de fundo, zero MCP). Para cada PRD que fecha no plano, escreve também o prompt do `/divulgar` e diz quando colar (terminal próprio, nunca dentro da `/onda-enxuta`; a mensagem de WhatsApp sai sozinha da onda que fecha o PRD); entrega a agenda das intervenções humanas no meio das ondas (migration, segredo no Coolify, restart) e termina perguntando "Posso lançar?": com o "pode", lança ela mesma a sessão da onda 1 de cada fila. Fora isso, não executa nada.
- `/onda-enxuta [#PRD | --all] [--paralelo N] [--sessao <nome>] [--onda N]`: esvazia a fila sozinho em ondas, uma sessão de fundo por onda (`scripts/lancar_sessao.sh`), implementador que morre no PR, corretor fresco, merge PR a PR pela API dos PRs verdes de cada lote e um build por onda pelo `fechar_onda.py` (as paradas humanas são as da regra 9 da ADR 0068). A review é do agente `hr-revisor`, disparado pelo orquestrador (ADR 0068). A `/onda` e a `/montar-ondas` originais não existem mais.
- `/retro-onda [<nome>-onda<N> | <id de sessão>]`: o último passo do modo AFK, quando o relatório da onda terminou em `retro: recomendada`. Lê o que a onda deixou (medição em `~/.claude/onda-enxuta/medicoes/`, baixas, comentários do corretor, saída da subida, JSONL da sessão) e propõe mudanças no **ambiente** dos agentes, não no código: ponteiro de navegação, check no CI, lente nova no `hr-revisor`, gatilho no `sensivel.py`, instrução sem efeito para apagar. Mecânico vira check; juízo vira lente. Só propõe; cada candidata aceita vira PR de ferramenta pelo `/ship`.

## On-ramps (como o trabalho entra)

- Ideia pequena, "dá pra fazer X?", print com uma vontade → `/grill-with-docs --lote`: levanta os fatos no código e decide tudo de uma vez; o que cair na porta C sai dali para o `/ship --from-diff` na mesma sessão.
- Grill em andamento que o Pedro quer fechar agora → `/express`: responde o que falta com a recomendação do agente, entrega a tabela no terminal e um painel interativo (Artifact) com Concordo/Discordo por linha e botão de aprovar, espera a aprovação (no painel ou "ok" no terminal) e só então classifica a porta e segue ao `/to-prd`. Não implementa nada.

- `/triage`: criar/triar issues pelos papéis canônicos de label (`docs/agents/triage-labels.md`).
- Bug difícil ou regressão de performance → `/diagnose`.
- Esforço grande demais para caber num grilling de uma sessão (névoa multi-sessão) → `/wayfinder`: mapa de tickets de decisão no GitHub (label `wayfinder:map`), um ticket por sessão, até a rota clarear; o handoff no fim é `/to-prd` + `/to-issues`. A porta da frente do planejamento continua sendo `/grill-with-docs` (ADRs 0027 e 0049).
- Melhorar arquitetura → `/improve-codebase-architecture` (relatório HTML); sanity-check de design → `/prototype`. Vocabulário de módulos em `codebase-design`; glossário e ADRs em `domain-modeling`; RLS, índice e migration pelo checklist da Supabase em `supabase-postgres-best-practices` (skill de referência, cópia fiel do upstream, só travessão trocado).

- PRD fatiado que o diretor precisa validar antes do trabalho → `/apresentar-prd <PRD>`: a Apresentação do PRD, o plano em etapas com o botão Validar, publicada em `https://planos-hsm.vercel.app/<PRD>`; o Validar grava a label `validado:diretor` e um comentário no PRD. Republicar tira a label. O texto do e-mail (link com o código) fica fora do repositório, e a sessão envia o e-mail ao diretor pelo Gmail. Fonte em `docs/comunicacao/planos/` (o segredo fica só no Mac e na Vercel).
- Card humano (`ready-for-human`) que depende de gente do hospital (assinar, mandar texto, aprovar) → `/guia-humano <N>`: o Guia passo a passo, uma página para leigo no design do app com botão Copiar em toda mensagem, título e comando, publicada em `https://guias-hsm.vercel.app/<N>`; o marcador `<!-- guia: <url> -->` no corpo da issue dá ao card do PedroOS o status Guia pronto e o botão Abrir guia, e a sessão do card oferece abrir. Fonte em `docs/comunicacao/guias/`.

## Pós-entrega

- `/divulgar <N>`: a entrega pro diretor: um vídeo curto das telas reais, feito pelo Estúdio de Vídeos no Estilo Nova Feature (só no Mac do Pedro; fora dele, só a página), e a página de divulgação publicada na Vercel com o vídeo embutido, com o link gravado na issue. O MP4 vai para `~/Videos/Hospital/`, nunca para o repositório. A fonte fica numa pasta por PRD em `docs/comunicacao/<contexto>/` (ADR 0045).
- `/mensagem-prd <PRD>`: a mensagem informal de WhatsApp que o Pedro manda ao diretor quando o PRD sobe: o que subiu e o que ele já consegue fazer no app, em tópicos e sem jargão, só o que já está em produção, com o link da página do `/divulgar` quando existir. A `/onda-enxuta` que fecha a última filha do PRD roda sozinha depois da subida e avisa no celular; à mão, para PRD fechado fora da onda. Sai em bloco para copiar e fica registrada como comentário no PRD. O envio é do Pedro.
- `/snapshot`: mapa factual da app (roda sozinho numa Action no push da `main`, depois do registro da subida, ADR 0068).
- `/atualizar-app`: rebuild local docker-compose (não toca produção).
- **Pendência humana pós-ciclo** (import na virada, credencial, ato externo): vira issue `ready-for-human` ligada ao PRD (`/ship` Passo 10); o Pedro acompanha pelo label `ready-for-human` (`/minhas-issues`) e fecha a issue ao concluir.
- **Card de implantação** (ADR 0111 e ADR 0113, decisão 9): o card humano que vem depois do código e não segura nenhuma fatia (teste de aceite, configuração, abertura, treinamento) leva a label `implantacao` e nasce `ready-for-human` no nome do diretor, posto pelo `/to-issues` ao criar a fatia ou pelo `/triage` (regra em `docs/agents/triage-labels.md`). O PRD fecha com a última fatia de código, sem esperar esse card. O diretor delega a quem faz no hospital e fecha o card quando terminou; o `/mensagem-prd` lista os abertos na linha "Para começar a usar, falta".
- **Tarefa do diretor** (ADR 0113, decisão 4): o que o diretor precisa responder ou fazer no meio de um PRD é card no nome dele, com menção: pergunta em `needs-info` (ele responde comentando e devolve o card), coisa a fazer em `ready-for-human` (ele fecha o card, e o bloqueio nativo solta as fatias). A baixa da `/onda-enxuta` que espera o diretor segue a mesma regra (nota `onda-enxuta` do `.claude/fluxo-notas.md`). Comandos em `docs/agents/issue-tracker.md`.

## Máquina nova

- `/setup-maquina [--nivel N] [--env] [--mapa]`: diagnóstico de quem clonou (clone atualizado, binários, gh, plugins, Coolify, tokens) com o conserto ao lado e o item do 1Password de cada chave; `--mapa` explica cada pasta do repo pelo `README.md` da raiz e como se conectar a cada serviço. O app não roda local: nível 2 (deploy) é o alvo. Quem vai publicar a página da `/divulgar` roda `--nivel 4`.
- `/setup-diretor`: o setup do diretor, que planeja e prototipa no Mac dele com o Claude Max desde 24/11/2026 (a aba Tecnologia saiu do refinamento). Guia de leigo, um passo por vez: conta no GitHub, ferramentas, fork do repositório, app local com o seed e IA simulada, a trava do merge no `settings.json` do Claude dele e o convite de colaborador (ADR 0113: recebe e fecha card, não mergeia; o check do PR do diretor espera a label `assumido`), `/grill-with-docs`, `/prototype` em PR rascunho do fork, o card no formato do PRD do diretor, o Arquivo de apoio no `hospital-arquivos` e a Tarefa do diretor. Bug ele relata pelo Assistente do app. A Action `card-do-diretor.yml` põe `needs-triage` e `origem:diretor` e designa o Pedro no card de quem está na variável `DIRETOR_LOGINS`; o grill técnico segue o caminho do PRD do diretor (`/grill-with-docs #N`). Só no Hospital, sem fonte no OS.

## Travessia de sessões

- `/passagem [--bg]`: documento de handoff pra outra janela; `--bg` dispara a continuação em background.
- Conflito de merge/rebase → `/resolver-conflitos`.

## Invariantes (não re-litigar)

- **Subir para prod não espera humano, fora as três paradas da regra 9** (ADR 0068): o gate é CI, revisores agentes, health e rollback automático. O `/ship` e o fechamento da onda rodam a subida (`fechar_onda.py`) sozinhos; ela faz o merge pela API (a `main` é protegida), o deploy e o registro, que a Action pós-merge grava na `main` sem PR. O humano só é chamado nas três paradas da regra 9 da ADR 0068: migration, rollback que a subida não fechou sozinha (`/deploy rollback`) e baixa `ready-for-human`. Cada sócio sobe o próprio PR (ADR 0068).
- ADRs: consuma só `status: accepted`; supersessão bidirecional travada pelo CI `lint-adr`.
- Estado vive nas GitHub Issues + `docs/spec/deploy/*.json`; proibido criar docs paralelos de estado/processo.
- Nada de travessão nem meia-risca em texto visível ao usuário (ADR 0013).
- **Régua de texto: todo texto para fora passa pelo humanizer** (ADR 0071): `/ship`, `/divulgar`, `/mensagem-prd`, `/to-prd` e `/to-issues` chamam a skill `humanizer` em modo embutido antes de gravar ou publicar, na voz da amostra aprovada do canal; o ESLint do front e o teste dos templates do backend travam os cacoetes regexáveis. Texto interno (comentário de código, scratchpad) não passa.

## Manutenção deste router

Criou, renomeou ou apagou skill do pipeline? Atualize este arquivo no mesmo commit (regra no `CLAUDE.md`).

Skill do Matt Pocock (`mattpocock-skills`) entra no pipeline **forkada** em `.claude/skills/`, em pt-BR, apontando `CONTEXT.md` (o upstream renomeou o glossário para `GLOSSARY.md` na v1.3; aqui o nome não muda) e com as fontes e destinos do Hospital escritos. O plugin fica como referência de leitura, não como skill ativa do fluxo; o fork sombreia o nome. Instrução operativa que manda rodar outra skill diz "chame a Skill tool com `nome`", nunca `/nome` em prosa (convenção do upstream: o `/nome` solto é o que mais falha em disparar); `/nome` fica só onde um humano escolhe, como neste router.
