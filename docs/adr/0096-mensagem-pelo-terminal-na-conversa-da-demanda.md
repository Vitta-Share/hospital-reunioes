---
status: superseded
amends: 0069, 0083
amended_by: 0106, 0108, 0109
superseded_by: 0113
---

# Mensagem pelo terminal: a sessão do desenvolvedor escreve e lê na Conversa da Demanda, pela ponte de automação

Decisão do Pedro (16/11/2026, grill no terminal em duas rodadas). Quando uma sessão do terminal para numa decisão que é do diretor (a baixa de uma onda num PRD que ele planejou, ou as perguntas do Refino), a pergunta hoje sai como mensagem de WhatsApp que o Pedro copia e cola. O diretor responde fora do app, o Pedro repassa à sessão e nada fica junto da Demanda. A Conversa da Demanda (ADR 0083) já avisa por sino e por e-mail; faltava a sessão do terminal conseguir escrever nela no perfil de quem a roda.

## Decisões

1. **A ponte de automação ganha a escrita e a leitura da Conversa da Demanda.** As rotas novas ficam no mesmo router da ponte (`/automacao/tecnologia`), com a mesma chave (`TECNOLOGIA_AUTOMACAO_API_KEY`) e o mesmo teto por endereço. Emenda a decisão 2 da ADR 0069, que deixava a ponte só com a leitura dos anexos. Rejeitado: token pessoal novo gerado numa tela (tela, tabela e revogação para dois usuários que já têm a chave) e login com usuário e senha do app pelo script (a senha na mão do agente).

2. **A mensagem sai no perfil de quem roda a sessão.** O pedido traz o login do GitHub de quem roda; o app só aceita se ele for um Desenvolvedor ativo com esse login no cadastro, e grava a mensagem com o id dessa pessoa. Rejeitado: autor fixo no servidor (`GITHUB_LOGIN_DONO`), que poria a mensagem do sócio no perfil do Pedro.

3. **A tela mostra a mensagem como de quem a escreveu, sem selo; o banco guarda a origem.** A mensagem da conversa ganha a origem (`app` ou `terminal`). Quem lê não vê diferença, porque o texto é do Desenvolvedor, aprovado por ele na sessão. Rejeitado: selo "enviada pelo terminal" na conversa e só o log do servidor (some no deploy, não serve de auditoria).

4. **O aviso da mensagem pelo terminal segue a regra dos avisos de entrega.** No card da Origem Vitta, avisa a diretoria (os Super admins ativos sem login do GitHub); no card do diretor, avisa quem abriu a Demanda. Sino e e-mail, como qualquer mensagem da conversa. O terminal não manda nome de ninguém. Emenda a decisão 8 da ADR 0083, que sem menção avisava o autor da Demanda (no card da Vitta, o próprio Desenvolvedor). Rejeitado: menção por nome vinda do script.

5. **Nada sai sem o "aprovo" de quem roda a sessão.** A onda de fundo escreve o rascunho na baixa e espera; a mensagem só vai para a conversa depois da aprovação no terminal. Com Demanda vinculada, a mensagem vai pelo app; sem Demanda, segue pelo WhatsApp, como hoje. Nunca pelos dois.

6. **A resposta do diretor é lida pela ponte e não vai para o GitHub.** A sessão lê as mensagens que chegaram depois da sua e mostra só no terminal. Quem roda a sessão confirma a escolha, e o corretor recebe a decisão escrita pelo agente, sem a fala do diretor (a decisão 8 da ADR 0083 continua: a conversa vive só no app). Enquanto espera, a issue troca `ready-for-human` por `needs-info`; com a resposta lida e confirmada, volta para `ready-for-agent`.

7. **As perguntas do Refino usam o mesmo canal.** As "Perguntas para o diretor" do `/grill-with-docs #N` saem pela conversa da Demanda do Refino, com as mesmas regras.

## Consequências

- O tom é o das mensagens do Pedro ao grupo (abre com "E aí", lembra o que o diretor escolheu, conta o que aconteceu, dá as opções e a recomendação).
- A migration só acrescenta à tabela da conversa a coluna da origem, com default `app`: as mensagens que já existem continuam como estão.
- A chave da ponte passa a escrever. Quem tem a chave (os Desenvolvedores, no `tokens/.env`) consegue escrever no perfil de qualquer Desenvolvedor cadastrado; o teto por endereço e a checagem do login limitam o estrago, e trocar a chave no Coolify revoga tudo de uma vez.
