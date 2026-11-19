---
status: accepted
amends: 0095, 0088
---

# Núcleo de Segurança do Paciente, Fase 2: notificação, triagem e prazos

Decisão do Pedro no grill de 18/11/2026, sobre a especificação da Diretoria Executiva na versão 1.1 (e-mail de 18/11/2026: seção 7, Anexos A, B e F, art. 26 do Regimento). A Fase 1 está em produção (PRD #1764), então a regra da decisão 1 da ADR 0095 está cumprida. Aqui ficam as decisões técnicas que a especificação deixa abertas e as regras antigas que elas mudam.

## Decisões

1. **Confirmar a triagem grava os prazos legais já na Fase 2.** Confirmar calcula todos os prazos do art. 26 e cria uma linha mínima de notificação externa, com o sistema de destino (VigiMed para medicação, NOTIVISA para o resto) e o prazo legal, que aparece na faixa "o que exige ação hoje". O texto para a vigilância e a fila de notificação externa ficam para a Fase 4. A designação do investigador e as referências temáticas ficam para a Fase 3, com a página de investigação. Nas faixas A e B, confirmar cria a reunião de análise de evento como Programada na data-limite, menos na lesão por pressão dos itens 8 a 10 sem óbito, que vai para a ordinária seguinte.

2. **Prazo legal fica no código; prazo interno fica na tabela.** O Núcleo tem tabela de prazos própria (faixa e marco), com histórico que só cresce, sobre o cálculo puro da Ouvidoria, que ganha a unidade de dias corridos e a regra do 15º dia útil do mês seguinte. Os prazos legais (72 horas corridas, 15º dia útil do mês seguinte, 60 dias corridos) não são editáveis e não param. Os internos são editados pela Presidência e pelo Acesso pleno, sem retroagir.

3. **O protocolo é sequencial por ano** (NSP-AAAA-NNNN), como a especificação pede. Diferente do Canal de Conduta (ADR 0097, decisão 8), o Núcleo não tem rota secreta que deixe buraco visível na sequência, e o número circula em reunião e em ata.

4. **O suplente responde pela Presidência por período registrado.** A Presidência ou o Acesso pleno registram o início e o fim da ausência, com trilha. Dentro do período, o suplente confirma triagem e vê a identidade de quem notificou. Fora dele, é membro. A regra da ata da Fase 1, em que o suplente conduz quando a Presidência falta à reunião, continua valendo.

5. **A Diretoria lê os casos das faixas A e B** sem a identidade de quem notificou e sem editar, e recebe o alerta imediato de "grave ou houve morte". O e-mail leva protocolo, setor e link, nunca o relato.

6. **O formulário público não guarda nem usa IP.** O limite de envios usa uma chave embaralhada com sal em memória trocado a cada 24 horas, e as rotas do módulo saem do log sem endereço. É a peça da decisão 10 da ADR 0097, construída aqui como serviço comum, para o Canal de Conduta reusar. O anexo (até 3 arquivos, somando menos de 9 MB, abaixo do corte de 10 MB do proxy do Next) vai para um bucket privado do Núcleo, nunca para a IA.

7. **A ponte da Ouvidoria cria a notificação, e o relato sai do link sem senha (emenda a decisão 7 da ADR 0088).** Confirmar o envio ao Núcleo na Ouvidoria cria, na mesma operação, a notificação de origem `ouvidoria`, com o relato integral, a justificativa técnica e o vínculo à manifestação, sem a identidade de quem manifestou. A ciência continua existindo, mas o e-mail passa a abrir o caso dentro do módulo, com login, e abrir a triagem marca o recebido. A página por token deixa de mostrar o relato. O selo "Em análise pelo NSP" mostra o estado do caso numa palavra. Os casos confirmados antes da Fase 2 não são importados.

8. **Os e-mails do Núcleo têm registro próprio, e a Ouvidoria não muda.** O registro de avisos da Fase 1 vira o registro único de e-mail do módulo, com caso, estado, tentativas e retentativa espaçada, reusando as funções puras de janela e de espera da Ouvidoria. O encaminhamento à Segurança do Trabalho e à queixa técnica usa um link de uso único próprio do Núcleo, no mesmo padrão do da Ouvidoria, endereçado ao titular vigente do cadastro de responsáveis, com um reenvio sem degraus. O encaminhamento à Ouvidoria, nesta fase, é um e-mail ao ouvidor com protocolo, motivo e relato. A criação automática da manifestação fica para a Fase 4 (seção 9.1 da especificação).

9. **Os 144 casos de teste entram no repositório (emenda a decisão 8 da ADR 0095).** A Diretoria confirmou que são fictícios. O teste de aceite continua sendo um comando manual, fora do CI: 144 casos, três vezes cada (432 chamadas), com as metas do Anexo F e o resultado no corpo do PR.

10. **Sombra, lote e recalibração entram na Fase 2.** O app mede a concordância por eixo desde o primeiro dia. Aos 30 e aos 60 dias de operação nasce a pendência "Recalibrar o agente do NSP" para quem tem Acesso pleno, pela porta de pendência sem reunião que a Fase 1 já usa, com a tela dos itens do Anexo F que já têm dados. Os itens que dependem das Fases 3 e 4 aparecem como "sem dados nesta fase". A aprovação em lote das faixas D e E nasce desligada.

11. **A cota diária do agente do Núcleo é separada da cota da Ouvidoria.** São 100 chamadas por dia (ADR 0095, decisão 5), contadas à parte, para o volume de um canal não tirar o agente do outro. A resposta a uma pergunta de esclarecimento roda o agente de novo só enquanto a triagem não foi confirmada.

## Alternativas consideradas

- **Designar o investigador já na Fase 2**: rejeitada. O e-mail mandaria a pessoa para uma página de investigação que só nasce na Fase 3.
- **Tabela de prazos inteira editável**: rejeitada. O Anexo A diz que prazo interno pode ser mais rígido que o legal, nunca mais frouxo, e um prazo legal editável deixa perder o prazo pela tela.
- **Reaproveitar a tabela de prazos, o registro de e-mail e o link da Ouvidoria abrindo os CHECKs**: rejeitada. Os três estão presos à manifestação por chave estrangeira, e mexer neles é mexer na Ouvidoria em produção sem ganho para ela.
- **Manter a página por token sem senha com o relato**: rejeitada. Com o caso dentro do módulo, o risco aceito na ADR 0088 deixa de ser necessário.
- **Suplente com poderes da Presidência o tempo todo**: rejeitada. A identidade de quem notificou ficaria com duas pessoas sem necessidade.
- **Usar o limitador da Ouvidoria como está**: rejeitada. Ele embaralha o IP com sal que não gira, e o aceite pede que nada guarde o IP.
- **Criar a manifestação na Ouvidoria já na Fase 2**: adiada para a Fase 4. Hoje a criação está espalhada por quatro rotas, e o volume não justifica extrair agora.

## Consequências

- O cálculo de prazos da Ouvidoria ganha duas regras novas (dias corridos e 15º dia útil). A Ouvidoria não usa nenhuma delas, mas os testes dela precisam continuar verdes.
- A partir da Fase 2, o link de ciência do Núcleo pede login. Quem recebe o e-mail precisa ter acesso ao módulo.
- O Canal de Conduta herda o limitador sem IP pronto e não constrói o dele.
- Mudar o prompt ou a base de conhecimento do agente exige rodar o teste de aceite de novo (Anexo F, seção 6).
