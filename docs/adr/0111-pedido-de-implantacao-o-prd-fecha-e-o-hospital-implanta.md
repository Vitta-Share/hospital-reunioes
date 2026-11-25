---
status: accepted
amends: 0110
amended_by: 0113
---

# Pedido de implantação: o PRD fecha com o código, e o que o hospital faz depois vira uma lista no card

Decisão do Pedro (22/11/2026, grill no terminal em três rodadas, a partir da #1853, o teste de acesso e de anonimato do Canal de Conduta). Os cards humanos que vêm depois do código (teste de aceite, configuração, abertura, treinamento) seguravam o PRD aberto, e quem os faz são as pessoas do hospital, não o Pedro. O desenvolvimento parte do princípio de que entregou certo: o PRD fecha com a última fatia de código, e o que falta para pôr a entrega em uso fica visível no card da Demanda.

## Decisões

1. **O Pedido da Vitta ganha um terceiro tipo, o Pedido de implantação.** Tem passos com check, como o Passo a passo, e aparece numa seção nova do Documento do card, "Implantação". O nome não é Pendência, que é a Ação da Ata (ADR 0109, decisão 2). Rejeitado: o Passo a passo com uma marca "depois da entrega" (o diretor não distinguiria o que trava código do que é uso) e Pendência da Demanda (o nome repetido confunde as duas telas).

2. **Só vira Pedido de implantação o card que vem depois do código e não segura nenhuma fatia.** Teste de aceite, configuração, abertura e treinamento. O card humano que segura código (chave no Coolify, decisão sobre migration, layout aprovado antes do desenvolvimento) continua sendo o Passo a passo da ADR 0110. Rejeitado: todo card `ready-for-human` ligado a uma Demanda.

3. **O fluxo marca o card com a label `implantacao`.** Quem põe é o `/to-issues`, ao criar a fatia, e o `/triage`. O PedroOS só lê a label. Rejeitado: o PedroOS adivinhar pelo título e pelo corpo.

4. **O Pedido de implantação nasce pelo clique "Mandar ao hospital" no PedroOS, que cria o Pedido e fecha a issue como concluída.** A issue ganha o comentário "virou Pedido de implantação no app". O clique do Pedro continua sendo o portão (ADR 0110, decisão 3). Rejeitado: o `/to-issues` parar de criar o card e a subida criar os Pedidos sozinha.

5. **O PRD fecha com a última fatia de código.** Pedido de implantação aberto não segura o PRD. A Etapa vai para Em produção, e o card mostra "Implantação 1 de 3" no Documento do card e como selo no Quadro. Rejeitado: o PRD esperar todos os Pedidos de implantação.

6. **O Destinatário continua sendo o diretor ou um Desenvolvedor.** Quem recebe escolhe quem faz (o primeiro passo diz isso) e marca os checks quando a pessoa devolve. A permissão da aba Tecnologia não muda. Rejeitado por agora: qualquer usuário do app como Destinatário, com tela própria fora da aba Tecnologia.

7. **O Pedido de implantação não acompanha o GitHub.** A issue já está fechada desde o clique. Concluir só comenta na issue fechada (o fato e os checks, sem nome de pessoa, como na ADR 0110, decisão 10) e não reabre nada. Emenda as decisões 5 e 7 da ADR 0110, que passam a valer só para o Passo a passo. Rejeitado: reabrir e fechar a issue de novo para registrar a conclusão.

8. **Um Pedido de implantação pode esperar outro.** O app guarda "espera o Pedido X", e o Concluir só libera com o anterior concluído. A abertura de um canal espera o teste dele. O bloqueio nativo do GitHub some quando as duas issues fecham, por isso a ordem passa a viver no app. Rejeitado: a ordem só no texto do passo.

9. **Problema achado vira Demanda de bug, e o PRD não reabre.** O Pedido tem o botão "Achei um problema", que abre o Assistente de Tecnologia já com o contexto. A Demanda de bug diz de qual PRD veio. O Pedido continua aberto, com "Espera a Demanda N", e depois da correção a pessoa refaz só o item que falhou. Rejeitado: reabrir o PRD com uma fatia nova, fechar o Pedido como reprovado e a Vitta abrir o bug à mão a partir da resposta.

10. **O lembrete é o mesmo do Pedido: um só, aos 3 dias.** O selo no Quadro deixa o que falta à vista. Rejeitado: um lembrete por semana.

11. **A mensagem de PRD entregue diz o que falta para usar.** O `/mensagem-prd` ganha a linha "Para começar a usar, falta: ..." com os Pedidos de implantação abertos. Rejeitado: a mensagem sem mudança, que deixaria o diretor achar que já pode usar.

12. **Os cards abertos de hoje entram pela última fatia.** Depois que a funcionalidade sobe, a última fatia põe a label `implantacao` nos cards abertos que cabem na decisão 2 e lista quais são, e o Pedro manda cada um. Os primeiros são os do Canal de Conduta (#1853, #1854 e #2135). Rejeitado: valer só para cards novos.

## Consequências

- Migration: a tabela do Pedido ganha o tipo novo e a referência "espera o Pedido", e o Pedido ganha a ligação com a Demanda de bug aberta pelo "Achei um problema".
- A Demanda pode estar Em produção com implantação aberta. As Entregas contam a entrega quando o PRD fecha, mesmo com a implantação por fazer.
- O PedroOS ganha o botão "Mandar ao hospital" para os cards com a label `implantacao`, e as skills do fluxo (`/to-issues`, `/triage`, `/mensagem-prd`) mudam no repositório do OS e na cópia do Hospital.
- O trabalho vira um PRD no Hospital.
