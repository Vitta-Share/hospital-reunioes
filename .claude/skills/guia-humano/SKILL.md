---
name: guia-humano
description: 'Guia passo a passo de um card humano (ready-for-human), numa página no design do app publicada em https://guias-hsm.vercel.app/<N>: explicação para leigo, um passo por cartão, botão Copiar em toda mensagem, título e comando, botão que abre a tela certa, aviso de espera quando o passo depende de outra pessoa e "Já fiz este passo". Grava o marcador <!-- guia: <url> --> na issue, que o PedroOS lê para mostrar o status Guia pronto e o botão Abrir guia, e a sessão do card oferece abrir. Use quando o Pedro pedir "guia", "passo a passo em HTML", "/guia-humano <N>", ou quando um card humano depende de gente do hospital. Fonte em docs/comunicacao/guias/<N>/dados.json.'
---

# Guia passo a passo

O card humano que depende de gente do hospital (assinar, mandar texto, aprovar) vira uma página que o Pedro abre, lê e copia: `https://guias-hsm.vercel.app/<N>`. A página é para leigo: cada passo diz onde clicar, o que digitar e o que aparece na tela, e todo texto para colar tem o botão Copiar.

## Onde cada coisa mora

No repositório (público), em `docs/comunicacao/guias/`:

- `modelo.html`: a página, no design do `globals.css` do app (o mesmo da Apresentação do PRD). Mudou o design? Muda aqui e vale para todos os guias.
- `site/`: o que vai junto em todo deploy (`index.html` da raiz e `vercel.json` sem índice de busca).
- `<N>/dados.json`: o texto do guia daquele card. É a fonte da página; o HTML não é versionado.

Fora do repositório, `~/.config/guias-hsm/site/.vercel` (ou `$GUIAS_HSM_DIR`): o vínculo com o projeto `guias-hsm` da Vercel, gravado sozinho no primeiro `publicar`.

O repositório e a página são públicos: dado que o card guarda fora do git (texto em `local/`, nome de pessoa da especificação, senha) não entra no `dados.json`. Entra o comando que copia ou abre o arquivo no Mac do Pedro.

## Passo a passo

1. **Ler o card**: `gh issue view <N> --comments`, o PRD pai e a tela real que o guia cita (rótulos de botão e campo no código da `main`, nunca de memória). Confira se algum passo já foi feito.
2. **Escrever `docs/comunicacao/guias/<N>/dados.json`** (molde: `1961/`). Campos:
   - `issue`, `contexto` (o módulo, como no menu do app), `titulo_aba`, `descricao`, `estado` (o status do topo, ex.: "Depende do hospital"), `selo`, `titulo` e `destaque` (o título em duas metades; a segunda sai em azul), `resumo` (o que é e por que, em três frases).
   - `numeros`: três contadores (`valor`, `rotulo`), ex.: passos, esperas, tempo do Pedro.
   - `quem`: `nome` e `faz` de cada um (o Pedro como "Você", as pessoas do hospital e "O agente").
   - `passos`: `titulo`, `texto` (lista de parágrafos curtos, um clique por frase), e se houver `espera` (o passo depende de outra pessoa), `copias` (`rotulo`, `copiar`, `comando: true` para comando do Terminal, `como` com o jeito de usar), `abrir` (`rotulo`, `url`: a tela exata) e `ver` (o que aparece quando deu certo).
   - `acabou` (os critérios de aceite do card, em linguagem de tela) e `ajuda` (o que fazer se travar).
   - Rótulo de botão ou campo da tela vai entre `[[...]]` e sai desenhado como botão.
3. **Texto pelo humanizer**: passe a prosa (tudo menos `copiar` e `url`) pela skill `humanizer` em modo embutido (ADR 0071). A amostra de voz é o `1961/dados.json`: segunda pessoa, frase curta, um clique por frase. A mensagem pronta no `copiar` segue a seção 3 do CLAUDE.md global e não muda.
4. **Montar e conferir**: `guia.py montar <N> --saida "$TMPDIR/guias"` recusa travessão em qualquer campo e número de issue ou palavra técnica da `/divulgar` na explicação. Sirva a pasta com `python3 -m http.server` (o `playwright-cli` não abre `file://`), copie a logo e a fonte de `docs/comunicacao/_assets/` e confira no `playwright-cli` em 1280 px e 390 px: o Copiar copia e o "Já fiz este passo" conta no topo.
5. **Publicar**: `python3 .claude/skills/guia-humano/scripts/guia.py publicar <N>`. Monta o site inteiro (todo `<N>/dados.json`, porque cada deploy troca o projeto todo) numa pasta fora do repositório, roda `npx vercel@latest deploy --prod --yes` e, depois do deploy que deu certo, grava no fim do corpo da issue a linha do guia e o marcador `<!-- guia: https://guias-hsm.vercel.app/<N> -->` (uma vez só, sem mudar outro byte). Guia publicado sem marcador: `guia.py marcar <N>`.
6. **Subir a fonte**: o `dados.json` vai para a `main` pelo `/subir "<descrição>" --from-diff` (classe ferramenta, só merge).

## O que o marcador liga

O coletor do PedroOS lê `<!-- guia: -->` do corpo: o card humano ganha o status Guia pronto e o botão Abrir guia, e a sessão aberta pelo card oferece abrir a página antes de remontar o guia.
