---
status: accepted
supersedes: 0079, 0096, 0103, 0106, 0109, 0110
amends: 0056, 0069, 0077, 0083, 0084, 0108, 0111
---

# Tecnologia vira espelho: o diretor prototipa e age pelo GitHub, e o agente do app fica só com manual e bug

Decisão do Pedro (25/11/2026, grill no terminal em três rodadas). Desde 24/11 o diretor tem Claude Max e planeja e prototipa no Mac dele, numa cópia local do app, em vez de usar a aba Tecnologia, que custava cerca de US$ 0,21 por pergunta na API (a skill `/setup-diretor`, PR #2243, sem ADR). Faltava decidir o que acontece com tudo o que o app e o PedroOS faziam para falar com ele: o Assistente de Tecnologia criando card, a Conversa da Demanda, a Mensagem pelo terminal, os Pedidos da Vitta e o bloco de mensagens do PedroOS. Quase toda essa conversa era com o diretor, e ele agora está no GitHub. A regra: o que só informa fica no app; o que age passa a ser card, comentário e atribuição no GitHub.

## Decisões

1. **O diretor é prototipador.** Melhoria só nasce do Claude Code dele: ele faz o grill, prototipa e abre o card (o PRD, com a label `origem:diretor`) e o PR rascunho. A Vitta refina, fatia e desenvolve. Rejeitado: manter o Planejamento da Demanda no app em paralelo (dois caminhos para a mesma melhoria, e o caro é o do app).

2. **O diretor vira colaborador do repositório, sem poder mergear.** Colaborador é o único jeito de ele receber card, fechar o card que a Vitta abriu e pôr card no nome de quem vai desenvolver. Duas travas seguram o merge: o `/setup-diretor` nega no Claude dele o merge pelo `gh` e pela API, e um check obrigatório do CI reprova o PR aberto por ele até um Desenvolvedor assumir (uma label). O PR dele continua saindo do fork. Vale também para o repositório da Ana. Emenda a decisão de 24/11 (fork sem ser colaborador). Rejeitado: só a instrução ao Claude dele (não segura o botão verde, e a `main` pede zero aprovações); continuar só no fork (ele só comentaria, e quem fecha o card seria sempre a Vitta).

3. **O PR rascunho do diretor é ponto de partida.** Quem assume continua na mesma branch do fork (edição por mantenedores), completa com teste e leva pela subida. Rejeitado: o PR só como referência, com a fatia refeita do zero; subir o PR como está.

4. **Tarefa do diretor no meio de um PRD é um card atribuído a ele.** Pergunta leva `needs-info`; coisa a fazer leva `ready-for-human`. Ele devolve com um comentário (e o link dos arquivos, decisão 11). Na pergunta, reatribui a quem pediu e o card volta a `ready-for-agent`; na tarefa, fecha o card, e o bloqueio nativo solta as fatias. Ele fica sabendo pela notificação do GitHub (atribuição e menção). Rejeitado: label nova `diretor` no lugar do dono; aviso também por WhatsApp.

5. **O Refino do card do diretor reconhece o card pela label `origem:diretor`.** O formato do Refino continua (Leitura, Veredito, Escolhas, gravados na issue). As "Perguntas para o diretor" viram um comentário com menção a ele e `needs-info`, com o card atribuído a ele. Rejeitado: o card dele pelo grill comum, sem o formato do Refino.

6. **A aba Tecnologia fica só com informação: Quadro e Entregas.** O card abre o Documento do card. O que cada pessoa vê não depende mais de login do GitHub: acaba a visão separada do Desenvolvedor (ADR 0083, decisão 3). O espelho cria a Demanda de toda issue-raiz de produto, e a Origem "Pedido do diretor" vem da label `origem:diretor`. O Responsável continua derivado do dono da issue. Rejeitado: ficar só com as Entregas (some a Etapa de cada Demanda, que é o que o diretor quer acompanhar).

7. **Saem do app as telas e as rotas que agem.** O chat do Assistente de Tecnologia com o Planejamento da Demanda e o "Criar o card", a Revisão com o código de hoje, o "Me explique", a Conversa da Demanda, o Envio aos desenvolvedores, o Pedido da Vitta (Pergunta, Passo a passo e a lista Esperando você), o Apagar a Demanda, o seletor de modelo e as rotas de escrita da ponte de automação. As tabelas ficam no banco, sem migration que apague. Rejeitado: congelar as telas só para leitura do histórico; apagar as tabelas (não tem volta e não ganha nada agora).

8. **O agente vira o Assistente do app, um widget de manual e de bug.** Um ícone de robô no design do Hospital, no canto inferior direito, para todo usuário logado, que abre com sugestões ("Relatar um bug", "Tirar uma dúvida") e o campo livre. Responde dúvida de uso pelo Manual e pelo Kit de conhecimento e conduz o Roteiro do bug. Não planeja melhoria. Roda fixo no Sonnet 5.5, sem ler o código e sem seletor de modelo. O bug de Super admin nasce `ready-for-agent`; o dos demais, `needs-triage`. Sem nome próprio. Rejeitado: só para Super admin (o agente de manual só serve se todos veem); manter a leitura do código (custo, e quem lê o código é a sessão do desenvolvedor); nome próprio (compete com a Ana).

9. **O Pedido de implantação vira o Card de implantação.** É o card `implantacao` atribuído ao diretor, que delega e fecha quando o hospital terminou. O PRD fecha sem esperar por ele (continua a decisão 5 da ADR 0111), e o app mostra "Implantação 1 de 3" lendo esses cards. Emenda as decisões 4, 6, 7, 8, 9 e 10 da ADR 0111. Rejeitado: o PRD esperar a implantação.

10. **O Validar da Apresentação do PRD grava só no GitHub.** A label `validado:diretor`, o comentário e, com observação, o Ajuste do plano. Sai a rota `/validacoes` do app, que chamava a IA. Emenda a ADR 0108. Rejeitado: aposentar a página (é o jeito mais claro de ele ver as partes).

11. **Arquivo de apoio mora num repositório privado.** Especificação, planilha ou memória de cálculo que o diretor quer que a Vitta consulte vai para o repositório privado `hospital-arquivos` (diretor e sócios), numa pasta por card; o card, público, leva só o link. O card não leva anexo. Rejeitado: pasta no Google Drive (o Claude do terminal não lê PDF de lá sem baixar à mão); o arquivo pelo WhatsApp, que hoje fica no `local/` do Mac dele e nunca chega à Vitta.

12. **As mensagens saem do PedroOS.** O `mensagem_a_enviar.py`, o bloco Mensagens da Ala Hoje, o Canal (app ou WhatsApp), o `checar-respostas`, a faixa Novidades e o "Mandar ao hospital" deixam de existir. O que era mensagem ao diretor é a tarefa da decisão 4; o resto o Pedro manda por fora, sem o OS saber. As pessoas de cada Projeto (login, nome e papel, sócio ou diretor) passam a morar no `.claude/fluxo.json` do Projeto, e o OS de cada sócio lê dali o Filtro de pessoa, o "O que é meu" e o resumo por pessoa. O diretor fica fora do "Acesso dos sócios". Rejeitado: o diretor nas quatro listas fixas do OS, cada uma com um nome diferente para a mesma pessoa.

13. **O que está aberto hoje passa por triagem na última fatia.** Cada Pedido aberto no app e cada card de comunicação (`com:*`) aberto no GitHub vira card atribuído ao diretor, se ainda vale, ou fecha como não planejado com um comentário do motivo. Rejeitado: fechar tudo às cegas (solta bloqueio que ainda segura fatia).

## Consequências

- A `card-do-diretor.yml` deixa de designar sempre o dono do repositório: respeita o dono que o diretor já escolheu.
- O `/setup-diretor` muda: colaborador, as travas de merge, o arquivo de apoio no `hospital-arquivos` e o modelo do card que o Refino reconhece.
- O `prd_do_diretor.py` e o `conversa.py` mudam de canal; o `conversa.py` sai com a Conversa da Demanda.
- A regra "só Sonnet 5.5 nos agentes do app" sai da memória e entra no código, com o seletor de modelo fora.
- O trabalho do PedroOS vira cards no repositório do OS; a regra da seção 3 do `CLAUDE.md` global do Pedro e a ADR 0017 do repositório Pedro mudam: a mensagem do Hospital, da Ana e do Reuniões abre no Obsidian, como as outras.
- As seis labels `com:` do diretor saem junto com os cards de comunicação.
