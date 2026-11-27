---
status: accepted
amends: 0082
amended_by: 0097, 0107, 0112
---

# O módulo do Núcleo de Segurança do Paciente: fundação, fases e exceções de IA

Decisão do Pedro no grill em lote de 15/11/2026, sobre a especificação da Diretoria Executiva de 12/11/2026 (módulo Núcleo de Segurança do Paciente, versão 1.0, recebida por e-mail porque passa do limite de 100 mil caracteres do anexo da aba Tecnologia). A especificação fica fora do repositório, que é público: ela traz nomes e registros profissionais dos membros.

## Decisões

1. **Quatro PRDs, um por fase da especificação.** Fase 1 (constituição, documentos e reuniões), Fase 2 (notificação de incidente, triagem e prazos), Fase 3 (investigação, plano de ação e efetividade) e Fase 4 (notificação externa, indicadores, relatório e dossiê). O PRD de uma fase só é escrito com a fase anterior em produção. Os pré-requisitos da especificação entram como primeiras fatias da fase que usa cada um, sem projeto de fundação separado.

2. **O setor canônico é a tabela `setores` do Admin.** O Núcleo nasce apontando para ela por id. A Ouvidoria, que hoje guarda o nome do setor em texto, ganha a coluna de id com preenchimento por nome na Fase 2, e o texto continua como está. Os setores dos POPs e de Contas médicas ficam fora: são outro conceito e nenhum indicador do Núcleo passa por eles.

3. **Colegiado e participação com vigência, só para o Núcleo por enquanto.** Duas tabelas genéricas novas (o colegiado e a participação de uma pessoa nele, com papel, vigência e documento assinado), sobre o cadastro de pessoas que já existe. O cadastro de responsáveis por setor da Ouvidoria não migra agora: está em produção e guarda nome e e-mail sem vínculo com pessoa. A própria especificação aceita esse caminho (seção 2.2), desde que não nasça segunda tabela de setor nem de pessoa.

4. **Acesso pleno ao NSP é um perfil do módulo, e super admin não passa por cima.** O Núcleo ganha um perfil próprio no cadastro da pessoa, como POPs, Ouvidoria e Contas médicas já têm. Ao contrário dos outros módulos, as rotas de conteúdo do Núcleo não liberam o super admin: ele só chega à configuração técnica. A proteção é da aplicação. Quem tem acesso direto ao banco consegue ler, e isso é dito à Diretoria em vez de prometido como impossível.

5. **Exceção à decisão 1 da ADR 0082: a triagem roda sozinha no envio.** O agente de triagem do Núcleo lê toda notificação de incidente quando ela chega e a cada resposta de esclarecimento. Quem dispara é o envio, sem job e sem retentativa em relógio. O teto é de 100 chamadas por dia. Passado o teto, ou com o agente fora do ar, a notificação entra na fila marcada para classificação manual e nunca fica retida. O relato passa pela pseudonimização antes de sair do app (ADR 0034) e não leva o nome nem o contato de quem notificou.

6. **Segunda exceção à ADR 0082: o relatório mensal do Núcleo.** Uma chamada por mês, no dia 1º, porque o aceite da Diretoria pede o relatório entregue mesmo sem revisão. Os outros agentes do módulo (cronologia, ações, conduta, texto para a vigilância, ata, devolutiva) rodam depois de um clique e já cabem na ADR 0082.

7. **Um modelo só.** Todos os agentes do Núcleo usam `claude-sonnet-5-5`. O Opus só entra se o teste de aceite da triagem reprovar com o Sonnet.

8. **O teste de aceite da triagem é um comando manual.** São 104 casos, três vezes cada, com metas que impedem a publicação (nenhum caso grave classificado para baixo). Ele roda à mão antes de publicar e a cada mudança de prompt ou de base, com o resultado no corpo do PR. Fica fora do CI porque cada rodada são 312 chamadas pagas. Os casos ficam fora do repositório até a Diretoria confirmar que são fictícios.

9. **As ações do plano esperam o ciclo novo das Pendências.** A pendência de hoje é presa a uma reunião. A Fase 3, em que toda ação de plano vira pendência com evidência e verificação, só começa com o PRD #1757 em produção. Na Fase 1, a deliberação de reunião do Núcleo vira a pendência que já existe.

10. **A ata do Núcleo é um tipo novo, com prompt próprio.** O pipeline de hoje só passa o tipo da reunião como texto para o prompt. Os dez blocos do Regimento, com quatro deles montados pelo sistema e não pela transcrição, são trabalho novo. Os prazos e a assinatura reusam as funções que já existem, com tabela de prazos e fluxo de envelope próprios do módulo.

11. **Encaminhar ao Canal de Conduta só orienta.** O Canal não existe no app. Até existir, a tela mostra a orientação e nenhum conteúdo é transferido, sem link.

12. **Dados de pessoas ficam fora do repositório.** A carga inicial dos membros é feita pela tela, nunca por migration ou seed versionado.

## Alternativas consideradas

- **Pedir à Diretoria um card novo no app**: rejeitada. O limite do anexo barra o arquivo, e o Planejamento da Demanda refaria perguntas que a especificação já responde.
- **Migrar agora os responsáveis da Ouvidoria e os donos de POP para a participação genérica**: adiada. Três casos de uso justificam o banco genérico, mas mexer em dois módulos em produção antes de o Núcleo existir só aumenta o risco da primeira entrega.
- **Botão "Triar" com estimativa de custo**: rejeitada pelo mesmo motivo da ADR 0087. A sugestão precisa estar na fila quando a Presidência abre o caso.
- **Criptografar a identidade de quem notifica com chave fora do banco**: adiada. A chave ficaria ao alcance de quem opera o deploy, então a garantia seria de aparência.
- **Tabela de ações independente da Pendência**: rejeitada. Seria a segunda cobrança de prazo do app, contra o princípio de reuso da especificação.

## Consequências

- O custo de IA do Núcleo varia com o volume do formulário público, limitado pelo teto diário. A especificação estima de dezenas a poucas centenas de notificações por mês.
- A Fase 3 depende de um PRD de outro módulo. Se o #1757 atrasar, o Núcleo para na triagem.
- Job novo que chame IA continua precisando de ADR que emende a 0082. As duas exceções daqui valem só para a triagem na chegada e para o relatório mensal.
- Perguntas que ficam com a Diretoria: a lista de equivalência dos nomes de setor, a confirmação de que os casos de teste são fictícios e a ciência do limite da proteção frente a quem opera o banco.
