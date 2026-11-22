---
status: accepted
amends: 0109
amended_by: 0111
---

# Pedido da Vitta: Pergunta ou Passo a passo, e o Passo a passo concluído fecha o card no GitHub

Decisão do Pedro (22/11/2026, grill no terminal em duas rodadas, a partir da #1961). A ADR 0109 levou para o app a pergunta que a Vitta faz a uma pessoa do Hospital. Ficou de fora o card humano que pede para *fazer* alguma coisa (publicar o Regimento do NSP, cadastrar a suplente): o passo a passo vivia só no corpo da issue e no terminal, o diretor não via o que estava com ele nem com a Vitta, e o card só fechava quando o Pedro conferia à mão.

## Decisões

1. **O registro da ADR 0109 passa a se chamar Pedido da Vitta, com dois tipos: Pergunta e Passo a passo.** A Pergunta continua igual. O Passo a passo traz os passos do card e fecha com um check. Os dois dividem a tabela, o cartão, o lembrete de 3 dias e a lista, que passa a se chamar Esperando você. Rejeitado: um registro novo só para o Passo a passo (duplica ponte, lista e lembrete) e um botão "Concluí" na Pergunta (pergunta não é tarefa). O nome continua não sendo Pendência (ADR 0109, decisão 2).

2. **Vira Pedido todo card `ready-for-human` ligado a uma Demanda.** O Destinatário pode ser o diretor ou um Desenvolvedor. A Vitta também aparece na lista: o diretor passa a ver o que está com ela. Rejeitado: só os cards que dependem de alguém do hospital.

3. **O Pedido só chega ao app pelo clique do Pedro no PedroOS.** Quem grava é a sessão que leu o card e escreveu o passo a passo (a ADR 0109, decisão 10, vale para os dois tipos). Rejeitado: o app criar o Pedido sozinho quando o card ganha `ready-for-human` (o webhook só teria o corpo cru).

4. **Cada passo tem um check, e o "Como saber que acabou" é o último.** O cartão tem também um campo de resposta opcional e o botão Concluir, que só libera com todos os checks marcados. Cada check guarda quem marcou e quando, num histórico que só cresce. Os checks são os critérios de aceite do card. Rejeitado: um Concluir só, sem check por passo.

5. **Passo a passo concluído fecha a issue na hora.** O app comenta e fecha o card no GitHub, e o bloqueio nativo solta as fatias que ele travava. A Pergunta respondida continua esperando a leitura da Vitta, porque uma resposta muitas vezes muda o plano. Emenda a decisão 6 da ADR 0109, que passa a valer só para a Pergunta. Rejeitado: fechar também a Pergunta na resposta, e não fechar nenhum dos dois. Uma sessão de IA conferindo sozinha cada conclusão foi descartada porque dispararia custo sem clique humano.

6. **Conclui o Destinatário, ou um Desenvolvedor no lugar dele.** O nome de quem marcou fica em cada check, como na resposta da Pergunta (ADR 0109, decisão 5). Rejeitado: só o Destinatário.

7. **O Pedido acompanha o GitHub.** Issue fechada como feita: o Pedido vira concluído "pelo GitHub". Fechada como não planejada: vira cancelado. Reaberta: o Pedido volta a ficar aberto, com os checks zerados. Rejeitado: o app ignorar o GitHub depois que o Pedido nasce.

8. **Falha no GitHub aparece no cartão.** O Pedido fica concluído no app, o cartão mostra "Não chegou ao GitHub" com o motivo, e o botão Reenviar tenta de novo. Nunca há reenvio automático (o mesmo do Envio falhou). Rejeitado: tentar de novo sozinho até conseguir.

9. **Os passos são escritos para quem os faz.** Para o diretor, só cliques e telas do app, com o link inteiro. Comando de terminal só aparece quando o Destinatário é Desenvolvedor. Rejeitado: copiar o passo a passo do card como está.

10. **O comentário na issue leva só o fato e os checks.** "Concluído no app em DD/MM às HH:MM, pelo Destinatário (Diretoria)" ou "(Desenvolvedor)", mais a lista dos checks marcados, sem o texto da resposta e sem nome de pessoa (o repositório é público; ADR 0083, decisão 8). Rejeitado: levar a resposta junto. O que a próxima fatia precisa saber vai como Pergunta.

11. **Card com passos de duas pessoas vira dois Pedidos.** Cada Pedido tem um Destinatário. A parte do outro vira um Pedido separado, que trava este pelo bloqueio nativo do GitHub. Rejeitado: um Pedido com passos de várias pessoas.

12. **O PedroOS ganha a faixa Novidades.** Fica no topo da Ala Hoje, uma linha por evento, com o horário: Passo a passo concluído, Pergunta respondida e "Não chegou ao GitHub". A linha fica até o Pedro dispensar, e o clique abre a Sessão da mensagem. Rejeitado: só o filtro Respondida do bloco Mensagens.

## Consequências

- Migration: a tabela da Pergunta ganha a coluna do tipo e os passos, e nasce a tabela dos checks, com RLS default-deny. A ponte de automação ganha a criação do Passo a passo; o webhook do GitHub passa a mexer no Pedido (decisão 7).
- O fechamento pelo app usa a escrita no GitHub que o app já tem para o Criar o card.
- No PedroOS, o `mensagem_a_enviar.py` ganha o tipo Passo a passo (os passos e o Destinatário), o `checar-respostas` passa a ler as conclusões, e o coletor alimenta a faixa Novidades.
- O trabalho vira um PRD no Hospital, com os cards do PedroOS no repositório dele.
