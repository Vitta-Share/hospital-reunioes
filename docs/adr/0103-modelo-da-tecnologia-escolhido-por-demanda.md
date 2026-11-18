---
status: accepted
amends: 0075, 0077
---

# O diretor escolhe o modelo de cada Demanda da Tecnologia: Sonnet 5.5 ou Opus 5.5

Decisão do Pedro em 18/11/2026, na issue #1921. A aba Tecnologia rodava num modelo só, o da variável `LLM_MODEL_PLANEJAMENTO`, com padrão `claude-opus-5-5` (ADR 0075, decisão 7; ADR 0077, decisão 9). De 10 a 18/11 ela gastou US$ 66 dos US$ 150 de IA do app. O Sonnet 5.5 custa metade do Opus 5.5 (US$ 2 e US$ 10 contra US$ 4 e US$ 20 por milhão de tokens de entrada e saída).

## Decisões

1. **O modelo é da Demanda.** Mora em `tecnologia_planejamentos.modelo`, a coluna que já existia (migration 123), sem migration nova. Toda chamada de IA da Demanda roda nele: a pergunta, o resumo, a Revisão com o código de hoje e o chat da aba, que passa pela mesma porta (`chamar_o_modelo`). O custo segue por chamada em `tecnologia_chamadas_ia.modelo`, com o modelo que de fato rodou. Emenda a decisão 7 da ADR 0075 e a decisão 9 da ADR 0077.

2. **Dois modelos, lista fechada.** `claude-sonnet-5-5` e `claude-opus-5-5`, os dois da tabela de preço do código. Outro valor volta 422. Modelo novo entra na lista junto com o preço dele.

3. **O Sonnet 5.5 é o padrão.** A Demanda nova nasce no modelo de `LLM_MODEL_PLANEJAMENTO`, cujo padrão no código passa a `claude-sonnet-5-5`. O primeiro turno do chat, antes da linha existir, roda nesse padrão. A Demanda que já existe mantém o modelo gravado.

4. **O seletor fica na conversa.** "Modelo: Sonnet 5.5 | Opus 5.5" mostra o modelo atual e troca com um clique, no cabeçalho da conversa, no resumo da melhoria e no pedido já enviado (de onde sai a Revisão). Troca quem abre a conversa da Demanda, com a regra da leitura: a Demanda de outro autor responde 404. A troca vale da próxima chamada em diante, não chama a IA e não mexe no `atualizado_em`, para não derrubar com 409 o turno que estava no ar.

5. **A estimativa da Revisão usa o modelo escolhido** (ADR 0082): a faixa em dólar e o nome do modelo no diálogo mudam com a troca.

## Rejeitado

- Opus em tudo, como era: paga o dobro no que não pede mais raciocínio.
- Trocar só pela variável do Coolify: troca para todas as Demandas de uma vez, e o diretor não decide.
- Modelo livre, digitado: modelo fora da tabela de preço grava custo zero, e nome errado derruba todo turno.
