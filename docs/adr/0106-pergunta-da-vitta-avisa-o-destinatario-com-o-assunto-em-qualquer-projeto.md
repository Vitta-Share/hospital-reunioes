---
status: accepted
amends: 0093, 0096
amended_by: 0109
---

# Pergunta da Vitta na Conversa da Demanda: avisa o Destinatário com o Assunto, em qualquer Projeto

Decisão do Pedro (18/11/2026, grill no PedroOS, PRD #1964). A Mensagem pelo terminal (ADR 0096) já escreve na Conversa da Demanda e avisa por sino e por e-mail. Faltavam três coisas para o PedroOS mandar por ali toda pergunta que espera o diretor ou outra pessoa do Hospital: escolher quem é avisado (a regra das entregas não sabe quem precisa responder), dizer no aviso que a mensagem pede resposta e do que se trata, e ter onde morar a pergunta de um Projeto da Vitta que não é o Aplicativo do Hospital nem a Ana.

## Decisões

1. **A mensagem pela ponte ganha três campos opcionais: Destinatário, Assunto e "pede resposta".** O Destinatário é o id do participante; o Assunto é um texto curto; "pede resposta" é sim ou não. Sem os três, tudo segue como na ADR 0096.

2. **Com Destinatário, o aviso vai só para ele, em qualquer Origem.** Sino e e-mail, no card do diretor e no card da Vitta, e não pela regra dos avisos de entrega. Emenda a decisão 4 da ADR 0096, que continua valendo para a mensagem sem Destinatário. Destinatário inativo ou inexistente é recusado com motivo, antes de gravar a mensagem: a pergunta nunca fica na conversa sem ninguém avisado. Rejeitado: menção por nome no texto (a decisão 4 da 0096 já recusou, e o nome não identifica a pessoa).

3. **Com "pede resposta", o aviso diz isso e o Assunto.** O título do sino é "Pede sua resposta" e a linha é o Assunto; o assunto do e-mail é "<Nome> pede sua resposta: <Assunto>", e o corpo leva o Assunto, o título da Demanda e o link que abre a Demanda com a conversa. "Pede resposta" sem Assunto é recusado. Sem "pede resposta", o texto de hoje, mesmo com Assunto.

4. **A ponte lista quem pode ser Destinatário.** Rota de leitura, com a mesma chave e o mesmo teto, que devolve os participantes ativos (id e nome), sem e-mail nem telefone. O PedroOS sabe por ela se a pessoa tem login no app e escolhe o caminho.

5. **Projeto deixa de ter só dois valores: a ponte cria a Demanda de um Projeto novo.** Emenda a decisão 1 da ADR 0093 (Aplicativo do Hospital e Ana). Pelo par projeto mais número da issue, a ponte cria uma Demanda de Origem Vitta com o nome do Projeto, o título e o link do PRD; se ela já existe, devolve a mesma. Essa Demanda não entra no espelho nem na conferência de hora em hora, porque o app não lê o repositório desse Projeto: ela mostra a conversa e o link. O filtro Projeto do Quadro passa a listar os Projetos que têm Demanda. Rejeitado: a pergunta de outro Projeto seguir pelo WhatsApp, longe de tudo o mais.

## Consequências

- A regra "nada sai sem o aprovo" (decisão 5 da ADR 0096) continua: no PedroOS, o envio é um clique do Pedro.
- A chave da ponte passa a escolher quem é avisado. Quem tem a chave consegue avisar qualquer participante ativo; o teto por endereço e a recusa do inativo limitam o estrago, e trocar a chave no Coolify revoga tudo de uma vez.
- Sem migration para os campos da mensagem: o Destinatário e o Assunto decidem só o aviso e não ficam gravados na conversa.
