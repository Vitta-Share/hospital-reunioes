---
status: accepted
amends: 0054, 0084
---

# As Partes do Documento do card mostram o número, o que trava cada uma e a Onda

Decisão do Pedro (16/11/2026, grill em lote depois da entrega do PRD #1883). Na Tecnologia o diretor aprova e acompanha os cards que a Vitta planeja, mas a seção Partes do Documento do card mostra só o bloco "Para o diretor" de cada parte, a Etapa e a data em que fechou. Ele não sabe em que ordem as partes entram, qual espera qual, nem como citar uma parte quando fala com a Vitta. O número ficou de fora de propósito (ADR 0054, decisão 9; issue #676), para nada técnico chegar à tela dele. Na prática o número virou a referência da conversa entre os dois, como já é o número da Demanda (ADR 0093).

## Decisões

1. **O número aparece para todos que veem a Demanda.** Emenda a decisão 9 da ADR 0054. A raiz mostra o número dela ao lado do número da Demanda, e cada parte mostra o seu, no formato "#1886". Sem link: o link do GitHub, as labels e o título técnico da fatia continuam atrás do `github_login`.

2. **A parte diz o que a trava.** Enquanto uma parte tem bloqueio aberto, ela mostra "Espera a #1884", uma bloqueadora por linha. Bloqueadora que não é parte da mesma Demanda aparece como "Espera a #1830, de outro pedido". Sem bloqueio aberto, a linha não aparece. A fonte é a dependência nativa do GitHub (`blocked_by`), a mesma que a onda usa para montar a fila; nada é digitado no app.

3. **As partes aparecem agrupadas por Onda.** A Onda de uma parte é calculada pelas dependências entre as partes da mesma Demanda: Onda 1 é a parte que não depende de outra parte da Demanda; as demais ficam uma Onda depois da maior Onda das que elas esperam. O cálculo conta também os bloqueios já resolvidos, para a sequência não mudar quando uma parte fecha. Bloqueio de outro pedido não muda a Onda. Ciclo de dependência não quebra a tela: as partes do ciclo ficam na Onda 1.

4. **A explicação funcional continua sendo o bloco "Para o diretor".** A parte já mostra o bloco inteiro (O que muda, Por que vale e O que você precisa saber). Não nasce texto novo, nem resumo escrito pelo app.

5. **A leitura é a mesma que já monta a foto.** As dependências de cada parte são lidas junto com as partes, só enquanto a raiz está aberta, e guardadas na lista de partes que a Demanda já guarda. Falha de leitura mantém o último valor. Sem migration.

6. **Só o Documento do card muda.** O Quadro, as Entregas e a lista do celular ficam como estão; o celular abre o mesmo Documento. O Kit de conhecimento da Tecnologia e o manual da Tecnologia mudam no mesmo PR.

## Por que é surpreendente

- O diretor passa a ver número de issue, que a ADR 0054 escondia dele de propósito.
- A palavra Onda, do fluxo de desenvolvimento, chega à tela dele, com o sentido simples de "o que entra junto".

## Alternativas descartadas

- **Número só para o Desenvolvedor, como hoje.** O diretor continuaria sem como citar a parte, que foi o pedido.
- **Ler a sequência do texto "Ondas previstas" do PRD.** O texto é escrito uma vez e envelhece quando uma parte é refeita; a dependência no GitHub é a que a onda usa de verdade.
- **Lista numerada simples, sem grupos.** Não mostra o que entra junto nem o que espera o quê.
- **Link para o GitHub em cada parte.** O diretor não entra no GitHub (ADR 0054) e o repositório é público.
