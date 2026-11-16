---
name: divulgar
description: Demonstração de uma entrega (PRD ou issue sem PRD) para o diretor e o usuário funcional. Um vídeo curto das telas reais, feito pelo Estúdio de Vídeos no Estilo Nova Feature (só no Mac do Pedro), e a página na Vercel com o vídeo embutido, no design do app, com o link gravado na issue. Sintaxe `/divulgar <N>`. Fonte em docs/comunicacao/<contexto>/<N>-<slug>/, MP4 em ~/Videos/Hospital/.
---

# Divulgar

Fecha uma entrega para o diretor e para o usuário funcional em dois passos, um comando:

1. **Vídeo** (MP4 com música e legenda, sem voz): o diretor vê o sistema funcionando nas telas reais, sem ler nada. Sai do Estúdio de Vídeos do PedroOS (ADR 0028 do PedroOS), no Estilo Nova Feature.
2. **Página de divulgação** (HTML na Vercel): uma explicada leve no que mudou, com o vídeo embutido, num link compartilhável.

**Divisão de trabalho fixa:** o vídeo demonstra, a página explica. A página não tem passo a passo, stepper, réplica de tela nem simulação; se a explicação precisar "mostrar", ela aponta para a aba do vídeo.

**O que isto NÃO é:** changelog, PRD, doc de arquitetura. Não existe "como foi implementado". Se sobrar migration, endpoint, PR, deploy ou RLS em texto visível, a skill falhou (gate anti-técnica).

## Entrada

`/divulgar <N>`. N é uma issue entregue sem PRD (um bug, por exemplo) ou um PRD (issue mãe). PRD agrega as fatias filhas numa demonstração só: o caso de uso completo, não uma por fatia.

Flag antiga no pedido (`--rapido`, `--voz`, `--completo`, `--so-video`, `--so-pagina`): diga numa linha que ela não existe mais e siga a receita inteira.

## Onde cada coisa mora

`docs/comunicacao/<contexto>/<N>-<slug>/` é a casa daquela entrega (ADR 0045):

- `video/roteiro.md`: o texto do vídeo (a Dor, os passos, o Resultado). Versionado.
- `video/meta.json`: o Estilo, o id do trabalho no Estúdio e o nome do MP4, gravados pelo `video_do_estudio.py`. Versionado.
- `index.html`: a página de divulgação. Versionada. Referencia `logo-hsm.png`, `HPSimplified_Rg.ttf` e `<N>-<slug>.mp4` relativos, que **não ficam na pasta**: o deploy copia os três.
- `.vercel/`: vínculo com o projeto da Vercel. Fora do git.

Fora do repositório: a gravação das telas (em `$TMPDIR`, apagada depois do pedido) e o **vídeo final**, `~/Videos/Hospital/AAAA-MM-DD-<N>-<slug>.mp4`. Refazer o vídeo gera `-v2`, `-v3`: nunca sobrescreve. **Nenhum MP4 entra no repositório.**

Regras da pasta mãe: uma subpasta por contexto de domínio (`reunioes/`, `pops/`, `ouvidoria/`), nome `<N>-<slug>` (número na frente ordena e garante unicidade; slug curto em kebab-case). **Sem data no nome e sem índice paralelo**: pasta e nome são o índice.

**Entregas antigas** (`video/` com a composição de antes, como `hyperframes.json` ou `cena/`) e a página de módulo (`ouvidoria/modulo/`, com `fase-1.mp4` e `fase-2.mp4`) ficam como estão. Republicar uma delas leva junto cada MP4 que ela embute, do `~/Videos/Hospital/`, com o nome que a página espera.

## Fontes da verdade (nesta ordem, todas obrigatórias)

1. **A issue no GitHub**: `gh issue view <N> --comments`. Para PRD, também as filhas. As user stories e os critérios de aceite viram os passos do vídeo e a matéria de *O que mudou* e de *Na prática*. Critério de aceite fora do vídeo = vídeo incompleto. Não inventar mudança que a issue não aborda.
2. **O app rodando** na stack local da main: o vídeo é a gravação dele, não réplica de memória.
3. **`docs/spec/snapshots/`** (ROTAS.md, FLUXOGRAMAS.md): o nome real das telas e o caminho de navegação até elas.
4. **`CONTEXT.md` e o CONTEXT do contexto** (ex.: `docs/pops/CONTEXT.md`): vocabulário canônico. Sempre o termo do glossário, nunca sinônimo inventado.

## O vídeo

### 1. Gravação

**A stack da main, sem rebuild.** Todas as demonstrações gravam da mesma stack local, que roda a main. **Não rode o `apply.sh`**: rebuildar troca a stack embaixo das outras sessões. Confira a versão no rodapé do app contra a da entrega: o `app_version` do deploy que cita a issue ou o PRD (em `prds` ou no `raw_subject`) no `docs/spec/deploy/history.json` da origin/main. Stack atrás da entrega: avise o Pedro numa linha e faça só a página (atualizar a stack é um passo à parte).

**O cenário do módulo.** Os dados de exemplo de cada contexto ficam em `docs/comunicacao/<contexto>/cenario.md`: o roteiro fixo e idempotente (login, pessoas, registros, a faixa de id do módulo, comandos exatos) que deixa o banco local pronto. Se o arquivo existe, rode o roteiro. Se não existe, monte os dados (fictícios e verossímeis, nunca reais: o repositório é público) e grave o `cenario.md` com o que você fez. Cada módulo usa uma faixa de id só dele. Login com a senha do `DEFAULT_USER_PASSWORD` do `.env` local, nunca a de produção.

**A gravação.** Siga o caso de uso nas telas reais com o `playwright-cli`, um clique por passo, na ordem do caso real, cobrindo todos os critérios de aceite, em **até 60 segundos**:

```bash
G=$TMPDIR/<N>-<slug>.webm
playwright-cli open http://localhost:3000/<rota>
playwright-cli resize 1920 1080
playwright-cli video-start "$G" --cursor
playwright-cli snapshot                # refs para clicar e preencher
playwright-cli click <ref>             # ou fill <ref> "<texto>"
playwright-cli video-stop
```

Ensaie antes de gravar (o caminho e as refs), para a gravação não ter espera nem clique errado.

### 2. Texto

O roteiro curto, em `video/roteiro.md`:

- **A Dor:** um gancho de até 8 palavras, a situação do dia a dia que a entrega resolve. Nunca uma dor inventada.
- **Os passos:** uma frase por ação da gravação (até 70 caracteres), na mesma ordem, com nome de botão e de tela igual ao do app.
- **O Resultado:** uma frase e até 3 ganhos.

**Gate anti-técnica:** varrer o texto procurando `migration, endpoint, API, PR, pull request, deploy, RLS, schema, backend, frontend, commit, branch, merge, token, env, SQL, Supabase, Coolify, prompt`; cada ocorrência vira linguagem funcional ou sai. Sem travessão nem meia-risca.

**Humanizer (ADR 0071):** a Dor, os passos e o Resultado passam pela Skill tool com `humanizer` em modo embutido. A amostra de voz é o `video/roteiro.md` da entrega mais recente em `docs/comunicacao/` (na falta, a página de referência): ela manda no tom, o humanizer só tira os cacoetes.

### 3. Pedido ao Estúdio

```bash
python3 .claude/skills/divulgar/scripts/video_do_estudio.py --pasta docs/comunicacao/<contexto>/<N>-<slug> --gravacao "$G"
```

O script liga o Estúdio pelo PedroOS (`POST /api/estudio/ligar`, com a porta e o token de `~/.pedroos/sessao.json` no cabeçalho `x-pedroos-token`), espera o `GET /api/estudio` dizer `ligado` e chama o comando do PedroOS:

```
python3 ~/PedroDev/OS/scripts/estudio/pedir_video.py --estilo profitize-estreia --texto <roteiro> --gravacao <gravação> --saida ~/Videos/Hospital/AAAA-MM-DD-<N>-<slug>.mp4 --formato longo --obs "Sem narração: música e legenda."
```

`profitize-estreia` é o Estilo Nova Feature (o item `estreia` da Biblioteca). O comando espera o Estúdio por até 2 horas: rode o script em segundo plano e escreva a página enquanto ele trabalha. A decisão é pelo código de saída:

- **Saída 0:** o MP4 está pronto; o caminho vem na última linha. A página leva o vídeo.
- **Saída 1:** o Estúdio deu erro. **Saída 2:** o Estúdio está desligado e não ligou, ou o comando não existe neste Mac (outro computador). Nos dois casos, a página sai só com a explicação.
- **Saída 3:** o tempo acabou. O trabalho segue no Estúdio, nada foi cancelado; a página sai só com a explicação e o id do trabalho fica no `video/meta.json`.

Fora da saída 0, o script imprime uma linha `Só a página: <motivo>`: repita essa linha ao Pedro (na saída 3, com o id do trabalho) e siga para a página. Apague a gravação depois do pedido.

## A página

**Referência de implementação:** `docs/comunicacao/reunioes/272-pendencia-nasce-na-assinatura/index.html`. Página nova = copiar essa como base e trocar o conteúdo, mantendo estrutura e design:

- **Com vídeo (saída 0):** a página fica com a barra de abas no rodapé, a aba Funcionalidade, o CTA para o vídeo e a aba Demonstração por Vídeo, com um parágrafo de contexto (o exemplo seguido; o vídeo tem música e legenda, então funciona com ou sem som), `<video controls preload="metadata" src="<N>-<slug>.mp4"></video>` e a linha de carimbo (`PRD #N · retrata o app em vX.Y.Z · gerado em DD/MM/AAAA`).
- **Só a página (saídas 1, 2 e 3):** tire a barra de abas, a aba Demonstração por Vídeo, o CTA e o script das abas. O conteúdo da aba Funcionalidade vira o corpo da página.

**Marca:** antes de compor, carregue a skill `marca-hsm`. Logo, nome e fotos do hospital seguem as regras dela.

**Design system: o do app, sempre.** A página replica o `globals.css` do frontend, não inventa identidade:
- Fonte **HP Simplified** em tudo (fallback `system-ui, -apple-system, sans-serif`), `html { font-size: 17px }`.
- Tokens copiados do `globals.css`: `--color-primary #2B2E7E`, `--color-primary-light #3B6FB6`, `--color-primary-dark #1A1C4E`, texto `#1E293B`, secundário `#64748B`, borda `#E2E8F0`, fundo branco, `--shadow-premium`, radius corporativo (xl 6px, 2xl 8px, 3xl 12px; pill 9999px).
- Antes de compor, conferir o `globals.css` atual: se os tokens mudaram no app, a página segue o app.

**Estrutura fixa:**
1. **Cabeçalho:** logo real do hospital + nome do contexto + selo "em produção".
2. **Hero:** uma frase de título com o valor da entrega + um parágrafo de resumo.
3. **Corpo** (a explicação leve, nada além): *O problema* em um parágrafo; *O que mudou* em cards compactos (título + 1 a 2 frases), um por mudança; *Na prática*, checklist de até 5 itens.
4. **Abas em barra flutuante no rodapé** (só com vídeo): `Funcionalidade` e `Demonstração por Vídeo`, como na referência, com a aba ativa no hash da URL (`#funcionalidade` / `#video`). Nunca como linha de tabs no topo.
5. **Rodapé:** contexto, mês/ano e versão do app (de `hospital-reunioes/frontend/package.json`).

**Regras de conteúdo:** linguagem de negócio, vocabulário do `CONTEXT.md`, o mesmo gate anti-técnica do texto do vídeo. Enxuto de verdade: seção que passa de uma tela de leitura, cortar. pt-BR, sem travessão nem meia-risca (`grep -Pn "\x{2013}|\x{2014}" index.html`). Verificar com o `playwright-cli` (screenshot de cada aba) antes de publicar.

**Humanizer no texto da página (antes de publicar, ADR 0071):** hero, cards de *O que mudou*, checklist e parágrafo da aba do vídeo passam pela Skill tool com `humanizer` em modo embutido. A amostra de voz é a página de referência (`272-pendencia-nasce-na-assinatura/index.html`): ela manda no tom, o humanizer só tira os cacoetes. HTML, classes e carimbo ficam iguais.

**Publicação (pela CLI, sem pedir ao humano).** Deploy de dentro do repo é BLOQUEADO pela Vercel (`TEAM_ACCESS_REQUIRED`: a CLI anexa o autor git, que não é membro do time). Sempre de uma cópia FORA do repo, só com o que a página precisa. Com vídeo, o MP4 vem do `~/Videos/Hospital/` (o mais novo daquela entrega) com o nome que a página embute:

```bash
P=docs/comunicacao/<contexto>/<N>-<slug>; D=$(mktemp -d)
cp "$P"/index.html "$D"/ && cp -R "$P"/.vercel "$D"/ 2>/dev/null
cp docs/comunicacao/_assets/logo-hsm.png docs/comunicacao/_assets/fonts/HPSimplified_Rg.ttf "$D"/
V=$(ls -t ~/Videos/Hospital/*-<N>-<slug>*.mp4 2>/dev/null | head -1)   # só com vídeo
[ -n "$V" ] && cp "$V" "$D/<N>-<slug>.mp4"
cd "$D" && npx vercel@latest deploy --prod --yes
```

O link compartilhável é o **alias de produção** (`https://<projeto>.vercel.app`, sem hash): URLs de deployment com hash caem no SSO da Vercel. Grave o link no corpo da issue N, que é o que leva a Demonstração ao card da aba Tecnologia (ADR 0084, decisão 9):

```bash
python3 .claude/skills/divulgar/scripts/marcar_demonstracao.py <N> https://<projeto>.vercel.app
```

O script põe `<!-- demonstracao: <url> -->` no fim do corpo, troca o marcador se ele já existe e só aceita `https`. Refazer o vídeo e republicar é rodar de novo com o mesmo link: o card não avisa o diretor duas vezes. Ajuste depois = editar no repo, recopiar, redeployar. A pasta temporária é apagada depois do deploy.

## Checklist de saída

1. A gravação cobre todos os critérios de aceite, na ordem do caso real, em até 60 segundos, nas telas da stack da main.
2. Roteiro e texto da página saem da issue (no PRD, também das filhas), no vocabulário do glossário, pelo `humanizer`; zero jargão, zero travessão, tudo em HP Simplified; logo e nome do hospital pela `marca-hsm`.
3. Pedido feito pelo `video_do_estudio.py`; na saída 0, MP4 em `~/Videos/Hospital/` e nenhum MP4 no repositório; fora dela, a linha `Só a página:` dita ao Pedro.
4. Página conferida no `playwright-cli`; `index.html`, `video/roteiro.md` e `video/meta.json` (quando existe) commitados.
5. Página publicada no alias de produção e marcador da demonstração gravado na issue N.
