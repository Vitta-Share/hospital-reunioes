# Passar um card ao diretor

A regra é a da ADR 0113, decisão 4: o que só o diretor ou o hospital resolvem vira card no nome dele. Pergunta leva `needs-info` (ele responde e devolve a quem perguntou); coisa a fazer leva `ready-for-human` (ele faz, ou passa a quem faz no hospital, e fecha). Ele fica sabendo pela notificação do GitHub, nunca por mensagem.

## O que passa e o que não passa

Passa: uma decisão de negócio do hospital (quem faz o quê lá dentro, uma regra que só a diretoria define, escolher entre opções que a Vitta já levantou), um dado que só o hospital tem (o organograma, um nome para um cargo), um acesso que só ele dá, cobrar alguém do hospital, o teste de aceite.

Nunca passa: card que apaga dado, sobe código, mexe no servidor ou pede senha da Vitta.

## O rascunho

Um JSON, com o texto já passado pela skill `humanizer` (o diretor lê; a amostra de voz é o bloco "👔 Para o diretor" das issues do Hospital). Sem nome de paciente, de colaborador nem protocolo: o card é público. Sem travessão.

```json
{
  "tipo": "needs-info",
  "por_que": "Uma ou duas frases: o que parou e por que só ele resolve.",
  "preciso": "O que ele responde ou faz, numa frase que ele entende sem abrir mais nada.",
  "opcoes": ["Opção 1, com o efeito dela no dia a dia", "Opção 2, idem"],
  "recomendacao": "A opção que o Pedro recomenda e por quê, em uma ou duas frases.",
  "devolver": "Responda aqui com 1 ou 2 e devolva o card ao Pedro."
}
```

Na coisa a fazer, `opcoes` vira a lista dos passos e `recomendacao` pode ficar vazia. Na pergunta com mais de uma opção, a recomendação é obrigatória.

## Onde o rascunho mora e quem manda

No `/pareamento`, o rascunho de cada card que dá para passar vai para `local/pareamento/passagens.json`, com a `versao` do card (a mesma do `descricoes.json`). A Ala Pareamento do PedroOS mostra o rascunho no card, o Pedro ajusta se quiser e clica em "Mandar ao diretor"; o clique, com a confirmação da Ala, é o "pode" dele. Numa sessão, com o "pode" do Pedro no turno:

```bash
python3 .claude/skills/pareamento/scripts/passagem.py --repo <dono/repo> --numero <N> --rascunho <arquivo.json>
```

O script faz três coisas, nesta ordem:

1. Escreve no começo do corpo a seção `## 🔁 Por que este card passou para você` (De, Por quê, O que preciso de você, As opções ou Os passos, Minha recomendação, Como devolver), seguida de `---`. Uma seção de passagem anterior sai.
2. Comenta, com `<!-- automacao -->` na primeira linha, mencionando o diretor e apontando a seção.
3. Passa o card: o diretor entra, quem roda sai, a label de estado vira a do `tipo` e as outras de estado saem.

O Claude do diretor (`/setup-diretor`, Parte 11) lê essa seção primeiro quando ele pergunta "o que está no meu nome?".

## A volta

Pergunta respondida: o diretor comenta e reatribui o card a quem perguntou, sem mexer em label. O `/pareamento` mostra esse card em "Voltou do diretor", e a sessão do botão grava a decisão no corpo e troca `needs-info` por `ready-for-agent`. Coisa a fazer: ele fecha o card, e o bloqueio nativo solta o que esperava.
