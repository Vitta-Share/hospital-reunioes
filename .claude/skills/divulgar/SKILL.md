---
name: divulgar
description: Demonstração de uma entrega (PRD ou issue sem PRD) para o diretor e o usuário funcional, numa página na Vercel que explica o que mudou, no design do app, com o link gravado na issue. Sintaxe `/divulgar <N>`. Fonte em docs/comunicacao/<contexto>/<N>-<slug>/.
---

# Divulgar

Fecha uma entrega para o diretor e para o usuário funcional numa **página de divulgação** (HTML na Vercel): uma explicada leve no que mudou, num link compartilhável. Sem vídeo: o Estúdio de Vídeos antigo saiu. A página não tem passo a passo, stepper, réplica de tela nem simulação.

**O que isto NÃO é:** changelog, PRD, doc de arquitetura. Não existe "como foi implementado". Se sobrar migration, endpoint, PR, deploy ou RLS em texto visível, a skill falhou (gate anti-técnica).

## Entrada

`/divulgar <N>`. N é uma issue entregue sem PRD (um bug, por exemplo) ou um PRD (issue mãe). PRD agrega as fatias filhas numa demonstração só: o caso de uso completo, não uma por fatia.

Flag antiga no pedido (`--rapido`, `--voz`, `--completo`, `--so-video`, `--so-pagina`): diga numa linha que ela não existe mais e siga a receita inteira.

## Onde cada coisa mora

`docs/comunicacao/<contexto>/<N>-<slug>/` é a casa daquela entrega (ADR 0045):

- `index.html`: a página de divulgação. Versionada. Referencia `logo-hsm.png` e `HPSimplified_Rg.ttf` relativos, que **não ficam na pasta**: o deploy copia os dois.
- `.vercel/`: vínculo com o projeto da Vercel. Fora do git.

Regras da pasta mãe: uma subpasta por contexto de domínio (`reunioes/`, `pops/`, `ouvidoria/`), nome `<N>-<slug>` (número na frente ordena e garante unicidade; slug curto em kebab-case). **Sem data no nome e sem índice paralelo**: pasta e nome são o índice.

**Entregas antigas** (com `video/`, do roteiro e do `meta.json` do Estúdio ou da composição de antes, como `hyperframes.json` ou `cena/`) e a página de módulo (`ouvidoria/modulo/`, com `fase-1.mp4` e `fase-2.mp4`) ficam como estão. Republicar uma delas leva junto cada MP4 que ela embute, do `~/Videos/Hospital/`, com o nome que a página espera. **Nenhum MP4 entra no repositório.**

## Fontes da verdade (nesta ordem, todas obrigatórias)

1. **A issue no GitHub**: `gh issue view <N> --comments`. Para PRD, também as filhas. As user stories e os critérios de aceite viram a matéria de *O que mudou* e de *Na prática*. Não inventar mudança que a issue não aborda.
2. **`docs/spec/snapshots/`** (ROTAS.md, FLUXOGRAMAS.md): o nome real das telas e o caminho de navegação até elas.
3. **`CONTEXT.md` e o CONTEXT do contexto** (ex.: `docs/pops/CONTEXT.md`): vocabulário canônico. Sempre o termo do glossário, nunca sinônimo inventado.

## A página

**Referência de implementação:** `docs/comunicacao/reunioes/272-pendencia-nasce-na-assinatura/index.html`. Página nova = copiar essa como base e trocar o conteúdo, mantendo estrutura e design, e tirar o que é do vídeo: a barra de abas, a aba Demonstração por Vídeo, o CTA e o script das abas. O conteúdo da aba Funcionalidade vira o corpo da página.

**Marca:** antes de compor, carregue a skill `marca-hsm`. Logo, nome e fotos do hospital seguem as regras dela.

**Design system: o do app, sempre.** A página replica o `globals.css` do frontend, não inventa identidade:
- Fonte **HP Simplified** em tudo (fallback `system-ui, -apple-system, sans-serif`), `html { font-size: 17px }`.
- Tokens copiados do `globals.css`: `--color-primary #2B2E7E`, `--color-primary-light #3B6FB6`, `--color-primary-dark #1A1C4E`, texto `#1E293B`, secundário `#64748B`, borda `#E2E8F0`, fundo branco, `--shadow-premium`, radius corporativo (xl 6px, 2xl 8px, 3xl 12px; pill 9999px).
- Antes de compor, conferir o `globals.css` atual: se os tokens mudaram no app, a página segue o app.

**Estrutura fixa:**
1. **Cabeçalho:** logo real do hospital + nome do contexto + selo "em produção".
2. **Hero:** uma frase de título com o valor da entrega + um parágrafo de resumo.
3. **Corpo** (a explicação leve, nada além): *O problema* em um parágrafo; *O que mudou* em cards compactos (título + 1 a 2 frases), um por mudança; *Na prática*, checklist de até 5 itens.
4. **Rodapé:** contexto, mês/ano e versão do app (de `hospital-reunioes/frontend/package.json`).

**Regras de conteúdo:** linguagem de negócio, vocabulário do `CONTEXT.md`. **Gate anti-técnica:** varrer o texto procurando `migration, endpoint, API, PR, pull request, deploy, RLS, schema, backend, frontend, commit, branch, merge, token, env, SQL, Supabase, Coolify, prompt`; cada ocorrência vira linguagem funcional ou sai. Enxuto de verdade: seção que passa de uma tela de leitura, cortar. pt-BR, sem travessão nem meia-risca (`grep -Pn "\x{2013}|\x{2014}" index.html`). Verificar com o `playwright-cli` (screenshot da página) antes de publicar.

**Humanizer no texto da página (antes de publicar, ADR 0071):** hero, cards de *O que mudou* e checklist passam pela Skill tool com `humanizer` em modo embutido. A amostra de voz é a página de referência (`272-pendencia-nasce-na-assinatura/index.html`): ela manda no tom, o humanizer só tira os cacoetes. HTML, classes e carimbo ficam iguais.

**Publicação (pela CLI, sem pedir ao humano).** Deploy de dentro do repo é BLOQUEADO pela Vercel (`TEAM_ACCESS_REQUIRED`: a CLI anexa o autor git, que não é membro do time). Sempre de uma cópia FORA do repo, só com o que a página precisa:

```bash
P=docs/comunicacao/<contexto>/<N>-<slug>; D=$(mktemp -d)
cp "$P"/index.html "$D"/ && cp -R "$P"/.vercel "$D"/ 2>/dev/null
cp docs/comunicacao/_assets/logo-hsm.png docs/comunicacao/_assets/fonts/HPSimplified_Rg.ttf "$D"/
cd "$D" && npx vercel@latest deploy --prod --yes
```

O link compartilhável é o **alias de produção** (`https://<projeto>.vercel.app`, sem hash): URLs de deployment com hash caem no SSO da Vercel. Grave o link no corpo da issue N, que é o que leva a Demonstração ao card da aba Tecnologia (ADR 0084, decisão 9):

```bash
python3 .claude/skills/divulgar/scripts/marcar_demonstracao.py <N> https://<projeto>.vercel.app
```

O script põe `<!-- demonstracao: <url> -->` no fim do corpo, troca o marcador se ele já existe e só aceita `https`. Republicar é rodar de novo com o mesmo link: o card não avisa o diretor duas vezes. Ajuste depois = editar no repo, recopiar, redeployar. A pasta temporária é apagada depois do deploy.

## Checklist de saída

1. O texto da página sai da issue (no PRD, também das filhas), cobre todos os critérios de aceite, no vocabulário do glossário, pelo `humanizer`; zero jargão, zero travessão, tudo em HP Simplified; logo e nome do hospital pela `marca-hsm`.
2. Página conferida no `playwright-cli` e `index.html` commitado; nenhum MP4 no repositório.
3. Página publicada no alias de produção e marcador da demonstração gravado na issue N.
