---
status: accepted
amends: 0077, 0083, 0096, 0106
amended_by: 0110
---

# Pergunta da Vitta vira registro: cartão, lista Esperando sua resposta, Me explique e a Conversa da Demanda reformada

Decisão do Pedro (21/11/2026, grill no PedroOS, ADR 0035 de lá). A ADR 0106 fez a pergunta da Vitta chegar ao Destinatário certo, com o Assunto, pela Conversa da Demanda. Ficou faltando o resto: a pergunta é uma bolha de texto puro, o app não guarda que ela está aberta, o diretor não tem onde ver tudo o que espera por ele, e nada na tela diz o que a pergunta trava nem por que ela precisa dele. No PedroOS, a mesma mensagem ainda aparecia com a logo do WhatsApp, mesmo saindo pelo app.

## Decisões

1. **A Pergunta da Vitta passa a ser um registro do app.** Ligada a uma Demanda, com Destinatário, Assunto e quatro estados: aberta, respondida, resolvida e cancelada. Emenda a consequência da ADR 0106 que dizia "sem migration": o Destinatário e o Assunto passam a ficar gravados, na Pergunta. Rejeitado: seguir como mensagem de chat com visual melhor (sem registro não há lista, nem o que trava, nem sincronia com o card do GitHub).

2. **O nome é Pergunta da Vitta, nunca Pendência.** Pendência é a Ação da Ata (ADR 0050), e a lista na tela se chama Esperando sua resposta. Rejeitado: "Pendência da Demanda", que daria dois sentidos à mesma palavra para o diretor e para os agentes.

3. **O cartão da Pergunta explica a espera em palavras simples.** De qual Demanda e de qual Projeto é, a pergunta, por que precisa da pessoa, o que está parado, o que anda quando ela responder e o que o hospital ganha. O ganho é uma frase, nunca um número de horas ou de dinheiro (número inventado engana). Quem escreve as linhas é a sessão que grava a pergunta, pela ponte.

4. **A pessoa responde no cartão.** A Pergunta pode trazer opções prontas, com uma recomendada, na mesma peça do Planejamento da Demanda, além do campo livre. A resposta também entra na Conversa da Demanda. Rejeitado: responder só dentro da Conversa, onde a pessoa precisa achar o chat certo antes.

5. **A lista Esperando sua resposta fica na aba Tecnologia, com as Perguntas abertas de todos os Projetos.** Todo Super admin vê (ADR 0050). Quem responde é o Destinatário; um Desenvolvedor pode registrar a resposta no lugar dele, com o próprio nome gravado. Rejeitado: qualquer Super admin responder qualquer Pergunta (a resposta solta trabalho e precisa de dono).

6. **A resposta não solta o trabalho sozinha.** Ela volta para a Vitta, que lê e dá o ok no PedroOS. Só então a ponte marca a Pergunta como resolvida, e a Conversa ganha uma linha de sistema com o que foi decidido e o que destravou. A Pergunta que deixou de ser necessária vira cancelada, pelo mesmo caminho. Reforça a decisão 5 da ADR 0096 no sentido contrário: assim como nada sai sem o "aprovo", nada destrava sem a leitura. Rejeitado: destravar na resposta (a resposta do diretor muitas vezes muda o plano).

7. **Um lembrete só.** O cartão mostra há quantos dias a Pergunta espera. Depois de 3 dias sem resposta, o app lembra o Destinatário uma vez, por sino e e-mail. Rejeitado: lembrete repetido e nenhum lembrete.

8. **O Me explique abre o Assistente de Tecnologia em particular.** No cartão, o botão abre o Assistente já com a Demanda e a Pergunta: ele explica, tira dúvida e propõe um rascunho de resposta. Só o que a pessoa envia vai para a Conversa da Demanda. Emenda a ADR 0077: o Assistente deixa de viver só no chat de bug ou melhoria. Rejeitado: o agente como participante da Conversa, visível a todos (a pessoa pergunta menos, e a Conversa enche de texto de agente).

9. **A Conversa da Demanda ganha forma.** A mensagem aceita negrito, lista e link; as mensagens se separam por dia; a Pergunta aparece como cartão em destaque, com o estado; e os eventos da Demanda (travou, destravou, subiu) entram como linha de sistema. Emenda a ADR 0083, em que a mensagem era texto puro. Rejeitado nesta decisão: anexo de arquivo e imagem na Conversa (pede armazenamento e permissão próprios; fica para outra decisão).

10. **Vale para qualquer Projeto, e o envio segue no clique.** A Pergunta de outro Projeto para quem tem login entra na mesma lista, com o nome do Projeto no cartão (ADR 0106, decisão 5). Só quem não tem login recebe pelo WhatsApp. A Pergunta só chega ao app depois do clique do Pedro no PedroOS.

## Consequências

- Migration nova para a Pergunta, e a ponte de automação ganha as rotas para criar, ler, resolver e cancelar. A chave e o teto da ponte são os mesmos.
- A Mensagem pelo terminal sem "pede resposta" segue como na ADR 0096: é mensagem comum, não Pergunta.
- As Perguntas abertas no dia da subida são gravadas no formato novo, com as linhas preenchidas pela sessão.
- O texto do cartão segue a regra do repositório público só no que vai para o GitHub: a resposta da pessoa continua no app e nunca vai para a issue (ADR 0083, decisão 8).
- O custo do Me explique entra na conta do Assistente, no modelo padrão da ADR 0103.
