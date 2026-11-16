---
status: accepted
amends: 0030, 0011
---

# Pendência nasce no envio para assinatura, toda mudança pede anotação e o histórico não se apaga

Decisão do diretor na Demanda #1757 (91 decisões de negócio, planejadas na aba Tecnologia) e do Pedro no Refino (16/11/2026, três rodadas). O diretor quer cobrar e avaliar os responsáveis com dado confiável. Hoje a Pendência muda de estado sem registro, espera a assinatura para existir, perde o prazo ao ser repactuada, e o "fluxo contínuo" nunca atrasa. Esta ADR fixa as decisões difíceis de desfazer. Ela entra no código pelas seis ondas do PRD #1757; até cada onda subir, o código segue a ADR 0030.

## Decisões

1. **A Pendência nasce no clique de enviar para assinatura.** No mesmo ato a Reunião vai para `AGUARDANDO_ASSINATURA` e nascem todas as Pendências do quadro. A ClickSign roda em seguida; se falhar, fica o "Reenviar", sem voltar o estado. A assinatura passa a ser ciência da Ata. Emenda a decisão 1 da ADR 0030 (gatilho incremental por assinatura) e a frase da ADR 0011 que dava o estado terminal como única porta. O caminho sem assinatura (`APROVADA`, ADR 0003) não muda. Depois do envio, reprocessar e corrigir a Ata ficam bloqueados, e o PDF é gerado de novo a partir do quadro final antes de criar o Envelope.

2. **O Aceite interno continua, só como ciência.** Com o Envelope morto (recusa ou cancelamento), o Signatário ainda recebe o "Li e aceito", mas o aceite não cria Pendência. A Reunião fecha quando todos deram ciência. Emenda a decisão 3 da ADR 0030, que fechava a Reunião quando toda ação tinha Pendência.

3. **A reconciliação diária cria o que falta.** O job das 5h30 passa a criar as Pendências de toda Ata em `AGUARDANDO_ASSINATURA`. A criação é idempotente por ação (ADR 0030, decisão 6), então a primeira execução faz a carga das Atas que já estavam em assinatura e as seguintes protegem contra envio que falhou no meio.

4. **Quatro estados gravados; atraso e repactuação são calculados.** O banco guarda `PENDENTE`, `EM_PROGRESSO`, `CONCLUIDO` e `CANCELADO`. Atrasada é a Pendência aberta com prazo vencido. Repactuada é a que tem Repactuação no histórico. A Repactuação troca o prazo na hora e conta como atraso só quando feita depois do vencimento. O job que marcava `ATRASADO` sai.

5. **Toda mudança pede anotação e grava um evento.** O histórico é uma tabela só de inserção, com trigger no banco que recusa UPDATE e DELETE, porque o backend usa a chave de serviço (ADR 0002) e a aplicação sozinha não garante nada. A regra (quem pode, qual transição, se conta atraso) é uma função pura em Python; a gravação é uma função do Postgres que atualiza a Pendência e insere o evento na mesma transação. A API é um comando por ato (`POST /pendencias/{id}/acoes`); o `PATCH` genérico e as rotas force saem.

6. **Nada apaga Pendência.** O apagar físico vira cancelamento com anotação, e a Reunião deixa de apagar Pendências em cascata.

7. **Quem vê e quem age sai do vínculo, sem perfil novo.** Responsável e co-responsável veem e atualizam as Pendências deles. O Facilitador é quem consta como facilitador da Reunião: vê as Pendências dela, cancela, reabre e repactua. O Super admin vê e faz tudo, com a exceção das Reuniões do Núcleo (ADR 0095). Quem só participou da Reunião deixa de ver as Pendências dos outros. O Conector (ADR 0085) herda o recorte. A ADR 0007 segue valendo: `access_profile` não ganha valor novo.

8. **Link pessoal só para quem nunca entrou.** Toda pessoa cadastrada com e-mail já tem conta. Quem nunca entrou recebe, no e-mail, um link com token para atualizar as próprias Pendências, com validade e revogação, no padrão do portal do setor da Ouvidoria. Os outros recebem link comum para o app.

9. **Rotina e Processo não são Pendência.** Cada linha do quadro da Ata ganha um tipo: Ação (vira Pendência), Rotina ou Processo. A Rotina substitui o "fluxo contínuo", vive em tabela própria e tem uma Verificação por ciclo de calendário (semana, quinzena de 1 a 15 e de 16 ao fim do mês, ou mês). A Verificação é calculada pela data; a linha só é gravada quando alguém marca. O Processo vai para a lista de definições de processo do setor da Reunião, sem responsável e sem cobrança.

10. **O painel é calculado no servidor, e a semana é fotografada.** Um endpoint lê a base inteira e devolve alerta, fila, cards, gráfico e ranking já recortados para quem pede. O job de segunda grava os números da semana, que alimentam a evolução e a comparação com a semana anterior. O e-mail de segunda sai desse mesmo job, com guarda por pessoa e por semana, e não chama IA (ADR 0082).

## Por que é surpreendente

- A Pendência passa a existir antes de qualquer assinatura. `AGUARDANDO_ASSINATURA` convive com o quadro inteiro já cobrado.
- A Reunião entra em `AGUARDANDO_ASSINATURA` antes de a ClickSign confirmar o Envelope. O estado deixa de garantir que há Envelope.
- `ATRASADO` e `REPACTUADA` somem do banco. Quem procurar o estado gravado não acha: a situação vem calculada.
- Nem o Super admin apaga Pendência ou linha do histórico, e o trigger vale também para a chave de serviço.
- O Colaborador entra no app. O glossário dizia que só o Facilitador logava, e o código já criava conta para todos.

## Alternativas descartadas

- **Nascer no fim do fluxo da ClickSign, junto com a troca de estado de hoje.** Falha no meio deixava a Ata em validação, editável, com Pendências dependendo de um reenvio, e um duplo clique criava dois Envelopes.
- **Aposentar o Aceite interno.** O diretor não pediu, e apagaria rotas, página e e-mails que já colhem a ciência de quem não assinou.
- **Manter os seis estados e consertar o job de atraso.** O atraso continuaria dependendo de um job em memória, que se perde num deploy, e a Repactuada seguiria sem poder atrasar.
- **Histórico protegido só pela aplicação.** Com a chave de serviço, qualquer rota nova poderia editar o passado sem ninguém notar.
- **Perfil novo de responsável em `access_profile`.** A ADR 0007 já recusou esticar esse campo, e o vínculo dispensa cadastro.
- **Link com token para todo mundo.** Mais links com poder de escrita circulando em e-mail encaminhado, sem ganho para quem já entra no app.
- **Rotina como tipo de Pendência, com uma Pendência nova por ciclo.** Rotina não tem prazo, Repactuação nem Contestação; toda regra da Pendência ganharia exceção.
- **Verificação criada por job no primeiro dia do ciclo.** Voltaria a depender de job ter rodado para alguém estar atrasado.
- **Recalcular as semanas passadas pelo histórico.** O número de uma semana passada mudaria quando a regra mudasse.

## Consequências

- O verbete Pendência, a Repactuação, o Colaborador, a Secretária e o Aceite interno do `CONTEXT.md` mudam, e entram Anotação, Histórico da Pendência, Reabertura, Contestação, Rotina, Verificação, Processo, Minha Fila e E-mail de segunda.
- Uma migration por onda. A da onda 2 restaura o prazo das Pendências antigas atrasadas ou "a repactuar" pelo quadro da Ata; onde não der, usa a data da última mudança e grava um evento "migração".
- `reunioes` ganha setor obrigatório ao agendar, e o Super admin ganha uma tela para acertar Reuniões e responsáveis sem setor.
- Os lembretes do Núcleo (Pendência sem Reunião) passam pelo mesmo módulo, com o resultado registrado valendo de anotação.
- Ficam para pedido próprio, por decisão do diretor: organograma, visão da equipe e rascunho e revisão de POP.
