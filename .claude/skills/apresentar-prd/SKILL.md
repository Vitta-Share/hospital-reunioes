---
name: apresentar-prd
description: 'Apresentação do PRD para o diretor validar o plano antes do trabalho começar: uma página com as Partes em etapas, publicada no projeto planos-hsm da Vercel, com o botão Validar que grava a label validado:diretor no PRD. Irmã da /divulgar, que vem depois da entrega. É a skill do botão "Apresentar ao diretor" do PedroOS. Sintaxe `/apresentar-prd <PRD>`. Fonte em docs/comunicacao/planos/<PRD>/dados.json.'
---

# Apresentar o PRD

Antes de um PRD grande começar, o diretor recebe por e-mail um link para a **Apresentação do PRD**: o plano inteiro, Parte por Parte, na ordem das etapas, em linguagem de uso, e um botão Validar com campo de observação. A validação grava no PRD a label `validado:diretor` e um comentário com o marcador `<!-- validacao-diretor: <ISO> -->`. Se ele escreve uma observação, a função abre antes o **Ajuste do plano** (marcador `<!-- ajuste-do-plano: <PRD> -->`): uma sub-issue `ready-for-human` do Pedro que bloqueia, pela dependência nativa, as Fatias iniciais (abertas, `ready-for-agent`, sem `in-progress` e sem bloqueio aberto). O comentário da validação traz o número do Ajuste, ou avisa para abrir à mão se a criação falhou.

**O que isto NÃO é:** a página de divulgação (a `/divulgar` explica o que já subiu; esta mostra o que vai ser feito). Não tem número de issue, nem palavra técnica, nem "como vamos implementar".

## Entrada

`/apresentar-prd <PRD>`. O PRD é uma issue mãe com Fatias (sub-issues) ainda não entregues. Rodar de novo num PRD já apresentado republica no mesmo endereço e tira o selo `validado:diretor`: o selo vale só para a versão que o diretor viu.

## Onde cada coisa mora

No repositório (público), em `docs/comunicacao/planos/`:

- `modelo.html`: a página da primeira Apresentação (PRD 1757) com marcadores `{{...}}` e `__DADOS__`. Design do `globals.css` do app, uma fonte só (HP Simplified), sem negrito falso, linha do tempo com hover, botão "Ver a ordem das etapas" e o Validar. Mudou o design? Muda aqui e vale para todas.
- `site/`: o que vai junto em todo deploy: `index.html` (a raiz, que só pede o link do e-mail), `vercel.json` (sem índice de busca) e `api/validar.js` (a função do botão).
- `<PRD>/dados.json`: o texto da Apresentação daquele PRD. É a fonte da página; o HTML não é versionado.

Fora do repositório, no Mac do Pedro, em `~/.config/planos-hsm/` (ou `$PLANOS_HSM_DIR`):

- `segredo`: a chave do código do link. O mesmo valor está na variável `SEGREDO` do projeto `planos-hsm` na Vercel, ao lado do `GITHUB_TOKEN` que a função usa. **Nunca** entra no repositório, em comentário nem em transcript. Perdeu o arquivo? Gere outro (`openssl rand -hex 32 > ~/.config/planos-hsm/segredo`), troque a `SEGREDO` na tela da Vercel e reenvie o link dos PRDs ainda sem validação: o código dos links antigos deixa de valer.
- Mudou só a função `api/validar.js`? Suba sem o `publicar`, que tira o selo: monte o site com `montar_site` numa pasta temporária e rode `npx vercel@latest deploy --prod --yes` nela.
- `site/.vercel/`: o vínculo com o projeto da Vercel, copiado para cada deploy.
- `email-<PRD>.txt`: o texto do e-mail com o link e o código, gravado pelo passo 6.

Logo e fonte vêm de `docs/comunicacao/_assets/` na hora do deploy.

## Passo a passo

1. **Coletar.** `python3 .claude/skills/apresentar-prd/scripts/apresentar.py coletar <PRD> > "$TMPDIR/coleta-<PRD>.json"` e leia o arquivo. Ele traz o PRD, as Partes já numeradas pela ordem dos bloqueios (API de dependências do GitHub), a etapa de cada uma, o bloco "Para o diretor" (`muda`, `vale`, `saber`) e os critérios de aceite. Fatia humana já fechada sai do plano e vem em `decididas`, com corpo e comentários: as respostas dela entram em "O que você já decidiu". Os números de issue no arquivo são só para você se achar; na página não entram.
2. **Escrever o `docs/comunicacao/planos/<PRD>/dados.json`.** Se ele já existe, mantenha o que não mudou e só atualize o que o PRD mudou. Use o do `1757/` como molde. Campos:
   - `prd`, `contexto` (o módulo, como no cabeçalho do app), `titulo_aba`, `descricao`, `selo` (ex.: "Plano para validar · Demanda 32").
   - `titulo` e `destaque`: o título da página em duas metades; a segunda sai em azul.
   - `resumo`: quantas Partes, quantas etapas, que nada foi entregue ainda, e como ler a página.
   - `numeros`: os contadores do topo (`valor`, `rotulo`); Partes e etapas sempre, mais um se fizer sentido.
   - `decidido` (opcional): `titulo`, `texto` e `blocos` (`titulo`, `itens`, `numerado`), com as decisões do planejamento e as respostas das Fatias humanas fechadas.
   - `fora` (opcional): `itens` e `texto`, o que o PRD deixou de fora.
   - `etapas`: uma por nível, `nome` curto e `texto` de uma frase.
   - `partes`: copie `id`, `etapa`, `depende`, `muda`, `vale` e `saber` da coleta; escreva `titulo` (até seis palavras) e `pronto` (uma frase "Pronto quando", em linguagem de uso, tirada dos critérios de aceite: o que o diretor vê acontecer, com um exemplo concreto quando der).
3. **Texto da página pelo humanizer.** Passe `titulo`, `destaque`, `resumo`, os textos de `decidido` e `fora`, os nomes e textos das etapas e os `titulo` e `pronto` de cada Parte pela Skill tool com `humanizer` em modo embutido (ADR 0071). A amostra de voz são os blocos "Para o diretor" das Fatias e o `1757/dados.json`: ela manda no tom, o humanizer só tira os cacoetes. Vocabulário do `CONTEXT.md`; logo e nome do hospital pelas regras da `marca-hsm`.
4. **Montar.** `apresentar.py montar <PRD> --saida "$TMPDIR/planos"`. O script recusa travessão, meia-risca, número de issue (`#123`) e as palavras técnicas da `/divulgar` (migration, endpoint, API, PR, deploy, RLS, schema, backend, frontend, commit, branch, merge, token, env, SQL, Supabase, Coolify, prompt) em todo texto da página. Recusou: reescreva o trecho no `dados.json`, nunca afrouxe a lista.
5. **Publicar.** `apresentar.py publicar <PRD>`. Ele tira a label `validado:diretor` do PRD antes de tudo, monta o site inteiro (todo `<N>/dados.json` da pasta, porque cada deploy troca o projeto todo) numa pasta temporária fora do repositório (de dentro, a Vercel recusa o autor do git) e roda `npx vercel@latest deploy --prod --yes`. O endereço é `https://planos-hsm.vercel.app/<PRD>`.
6. **Conferir no `playwright-cli`**, em desktop (1280 px) e em 390 px: título, contadores, "O que você já decidiu", as etapas com as Partes, o hover (ou toque) que acende o que vem antes e o que vem depois, o painel do detalhe com "Pronto quando", o botão "Ver a ordem das etapas" e o Validar, que sem o código no link fica desligado com o aviso "Abra esta página pelo link do e-mail". **Nunca** abra o link com o código nem clique em Validar: isso carimba o PRD de verdade.
7. **Rascunho do e-mail.** `apresentar.py email <PRD>` grava o texto (assunto, link com o código e o pedido para validar) em `~/.config/planos-hsm/email-<PRD>.txt` e imprime o caminho. Se a sessão tem acesso ao Gmail do Pedro, crie com ele um **rascunho** para o diretor com esse texto; nada é enviado sem o Pedro. Sem acesso ao Gmail, diga ao Pedro onde está o arquivo. O código não vai para issue, PR, commit nem resposta da sessão.
8. **Subir a fonte.** O `dados.json` novo ou mudado vai para a `main` pelo `/ship "<descrição>" --from-diff` (classe ferramenta, só merge).

## Checklist de saída

1. Partes, etapas e dependências saem da coleta, não de memória; Fatia humana fechada fora do plano e com as respostas em "O que você já decidiu".
2. Texto pelo `humanizer`; nada de número de issue, travessão ou palavra técnica (o `montar` trava).
3. Label `validado:diretor` tirada e página publicada em `https://planos-hsm.vercel.app/<PRD>`.
4. Página conferida no `playwright-cli` em desktop e 390 px.
5. Rascunho no Gmail (ou o caminho do arquivo dito ao Pedro), sem envio.
6. `docs/comunicacao/planos/<PRD>/dados.json` subindo pelo `/ship`.
