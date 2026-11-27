# Labels de triage

As skills falam em **5 papéis canônicos** de triage. Esta tabela mapeia cada papel para a label real no GitHub deste repo. Mantemos os nomes técnicos em inglês (identificadores estáveis que as skills aplicam); o significado é descrito em pt-BR.

| Papel (mattpocock/skills) | Label no nosso tracker | Significado |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Precisa de avaliação antes de virar trabalho |
| `needs-info` | `needs-info` | Aguardando mais informação de quem reportou |
| `ready-for-agent` | `ready-for-agent` | Especificada por completo; um agente AFK pega sem precisar de contexto humano |
| `ready-for-human` | `ready-for-human` | Precisa de implementação/decisão humana (HITL) |
| `wontfix` | `wontfix` | Não será tratada |

Quando uma skill mencionar um papel (ex.: "aplique a label de AFK-ready"), use a label correspondente da coluna do meio.

## Labels de apoio ao paralelismo

| Label | Significado |
| --- | --- |
| `in-progress` | Uma sessão deu claim e está trabalhando — sai da fila `ready-for-agent` |

> **Aposentada:** a label `blocked` (e a convenção `Bloqueada por: #X` no corpo) saiu de uso em 13/07/2026. Bloqueio entre issues agora é a **dependência nativa** do GitHub ("blocked by"); a fila filtra com `-is:blocked` e o destravamento é automático. Ver ADR 0068 e `docs/agents/issue-tracker.md`.

## Label do loop do revisor (ADR 0068)

| Label | Significado |
| --- | --- |
| `revisor-comentou` | Um login de `REVIEWER_LOGINS` comentou na issue, ou o app espelhou a resposta de um revisor sem login (marcador `<!-- revisor-app`); curadoria pendente: o agente lê, classifica e age (HITL), e remove a label ao final |

Aplicada automaticamente pela Action de higiene (`.github/workflows/higiene-issues.yml`) em `issue_comment.created`, por **dois gatilhos**: o login do autor estar em `REVIEWER_LOGINS`, ou o corpo do comentário **começar** pelo marcador `<!-- revisor-app autor="Pessoa do hospital" demanda="id" -->` em linha própria (ADR 0054, decisão 4 e emenda de 11/09: nome civil nenhum sai para o GitHub), que vale independente do login. Citar o marcador no meio de um texto não acende a label (issue #680): só o app o escreve como primeira linha, e o texto do autor chega com `<!--` neutralizado. O caminho do marcador não fica sem filtro: o `if:` do job só deixa passar comentário com `author_association` OWNER, MEMBER ou COLLABORATOR, e o comentário espelhado pelo app sai pelo token de um colaborador. A Action **só sinaliza**, nunca reabre nem edita. Comentários de automação não disparam o loop: a Action ignora comentários em PRs e, nos comentários **sem** o marcador de revisor, os que trazem o disclaimer do `/triage` ou o marcador `<!-- automacao -->`. O protocolo de curadoria vive na skill `/triage`; o acesso do revisor e a config `REVIEWER_LOGINS` estão em `docs/agents/issue-tracker.md`.

## Label de origem (ADR 0083)

| Label | Significado |
| --- | --- |
| `origem:diretor` | O diretor criou o card pelo "Criar o card" da aba Tecnologia, bug ou melhoria. O app aplica sozinho, junto com uma frase de resumo na primeira linha do corpo e o link para a Demanda; o Hospital OS lê os três para o selo, o Aviso e o Resumo da manhã |

Desde 24/11/2026 o diretor também abre o card pelo Claude dele (skill `/setup-diretor`), de um fork, sem acesso de escrita. Aí quem aplica é a Action `.github/workflows/card-do-diretor.yml`: quando a issue abre por um login da variável `DIRETOR_LOGINS`, ela põe `needs-triage` e `origem:diretor` e designa o dono do repositório. Esse card não tem Demanda, então a primeira linha é o resumo e não há link para a Demanda nem o marcador `demanda-vitta`.

Descreve de onde a issue veio, não o estado dela: convive com as labels de triagem e de tipo, e ninguém a tira na curadoria.

## Label do PR do diretor (ADR 0113)

| Label | Significado |
| --- | --- |
| `assumido` | Um Desenvolvedor assumiu o PR rascunho que o diretor abriu: continua na mesma branch do fork, completa com teste e leva pela subida. Sem ela, o PR do diretor não mergeia |

O diretor é colaborador para receber e fechar card, sem poder mergear (ADR 0113, decisão 2). A Action `.github/workflows/pr-do-diretor.yml` reprova o check `PR do diretor assumido` em todo PR aberto por um login de `DIRETOR_LOGINS` enquanto o PR não tem `assumido`, e roda de novo quando a label entra ou sai e a cada push. PR de sócio passa direto. Quem põe a label é a sessão do Desenvolvedor que assume: o `/pegar-issue` da fatia que tem o PR na seção "Protótipo" faz o checkout da branch do fork e põe a label (`pr_do_diretor.py`, #2300). A label só vale se quem a pôs não está em `DIRETOR_LOGINS`: o check lê no histórico da issue quem pôs a última `assumido`, e a posta pelo diretor reprova. O check é obrigatório no ruleset da `main` desde 26/11/2026.

Desde a mesma ADR, a `card-do-diretor.yml` respeita o dono que o diretor escolheu ao abrir o card: só designa o dono do repositório quando a issue nasce sem ninguém. A `dono-do-card.yml` deixa o card do diretor com ela.

## Label de implantação (ADR 0111)

| Label | Significado |
| --- | --- |
| `implantacao` | Card humano que vem depois do código e não segura nenhuma fatia: teste de aceite, configuração, abertura, treinamento. É o Card de implantação, no nome do diretor, que delega e fecha quando o hospital terminou (ADR 0113, decisão 9) |

A regra (ADR 0111, decisão 2): a label vai só no card humano que vem depois do código e não segura nenhuma fatia. O card humano que segura código continua sem ela: chave no Coolify, decisão sobre migration, layout aprovado antes do desenvolvimento. Na dúvida, pergunte se alguma fatia espera esse card (o `blocked_by` nativo de uma fatia aponta para ele): se espera, não é implantação.

- Vai: "Testar o acesso e o anonimato do Canal de Conduta", depois que as fatias do canal subiram e nenhuma espera o teste.
- Não vai: "Criar a chave da API no Coolify", que a fatia de integração espera para subir.

Quem põe é o `/to-issues`, ao criar a fatia humana já no nome do diretor, e o `/triage`, que põe ou tira pela mesma regra e passa o card para ele. O app e o PedroOS só leem a label (o "Implantação 1 de 3" do card). Ela convive com `ready-for-human` e com as labels de tipo; o PRD pai não espera o card com ela para fechar (ADR 0111, decisão 5).

## Tarefa do diretor (ADR 0113)

O que o diretor precisa responder ou fazer no meio de um PRD é um card no nome dele (o assignee), com menção ao login no comentário que pede: ele fica sabendo pela notificação do GitHub. Não há label própria; o estado diz o que é.

| Estado | O que é | Como ele devolve |
| --- | --- | --- |
| `needs-info` | Pergunta: a fatia espera uma decisão dele | Responde comentando, devolve o card a quem perguntou, e o card volta a `ready-for-agent` |
| `ready-for-human` | Coisa a fazer: teste, configuração, arquivo de apoio | Fecha o card quando terminou; o bloqueio nativo solta as fatias que esperavam |

O Card de implantação (acima) é a Tarefa do diretor que vem depois do código. O login dele mora na variável `DIRETOR_LOGINS` do repositório. Os comandos estão em `docs/agents/issue-tracker.md`.

## Labels de tamanho de fatia (Plano vivo)

Família **descritiva de tamanho** (não de estado), aplicada pelo `/to-issues` no momento da quebra do PRD — uma por fatia, nunca no PRD pai:

| Label | Significado |
| --- | --- |
| `fatia:P` | Pequena — poucas horas, escopo contido (1 camada dominante, poucos critérios) |
| `fatia:M` | Média — meio período típico (fatia vertical completa, escopo conhecido) |
| `fatia:G` | Grande — dia cheio ou mais; maior risco/incerteza (muitas camadas, UI nova, integração externa) |

A `/onda-enxuta` escolhe por esses labels o esforço do implementador. Tempo típico, lead time por tamanho e caminho crítico saíram com o Plano (ADR 0068).

## Labels ortogonais (mantidas do fluxo anterior)

Estas convivem com as de triage — descrevem **o que** é a mudança, não o estado dela:

- `type:feature` · `type:fix` · `type:chore` · `type:refactor` · `type:docs`: natureza da mudança (alimenta o tipo do PR e do commit).
- `area:backend` · `area:frontend` · `area:supabase` · `area:infra` · `area:docs` · `area:skills` · `area:spec` — onde a mudança incide.
