---
status: accepted
amends: 0073
---

# Contas médicas: a faturista vê a Esteira inteira, e a conta concluída se arquiva por Competência

Decisão do Pedro (18/11/2026, grilling) sobre o pedido do Diretor Executivo na reunião do mesmo dia. Emenda a decisão 3 da ADR 0073, e com ela o que restava da decisão 10 da ADR 0070 ("Faturista vê só as contas em que é `faturista_id`").

## Contexto

- O módulo passou de 90 contas numa semana e caminha para 150 a 200. São três faturistas, cada uma com dois monitores: o MV num, o módulo no outro. Uma jovem aprendiz sobe os PDFs.
- O diretor pediu três coisas que esbarram em regra, não só em tela: uma busca pelo número do atendimento ("o 2775 gritar na frente dela"), um filtro "Todas / Minhas", e arquivar por mês as contas concluídas, "pra sair da esteira", com o aviso de que arquivar quer dizer que a conta já foi tratada no MV.
- Pela ADR 0073, a faturista enxerga a Fila (as livres), as que ela puxou e as que ela concluiu. A conta que está com a colega não aparece para ela em lugar nenhum: buscar o número dela não acharia nada. A própria 0073 registra que "faturista vê só as dela" nunca foi regra de sigilo entre faturistas.
- A aba Concluídas mostra as 100 mais recentes para sempre. Não existe arquivar nem mês de referência; a Conta tem período (início e fim), data de envio e data de conclusão.
- O banco guarda do paciente só o rótulo e a idade (decisão 8 da ADR 0070). O diretor pediu "o nome do paciente" ao lado do número.
- A Ouvidoria já arquiva caso a caso e em lote, com desarquivar; é o padrão do app.

## Decisões

1. **Quem analisa vê a Esteira inteira.** As contas em análise e as concluídas de todas as faturistas aparecem na lista e na busca, cada uma com o nome de quem está com ela. "Minhas" passa a ser um filtro sobre essa lista, não uma lista separada. Emenda a decisão 3 da ADR 0073.
2. **Ver não é abrir.** A faturista continua abrindo só a conta livre e as dela; a de outra faturista aparece na lista, mas o Guia segue recusado para ela (403). Quem tem "painel completo" continua abrindo qualquer uma, sem virar dona.
3. **Abrir conta livre continua sendo pegar.** A regra da decisão 1 da ADR 0073 fica: o primeiro clique ganha, devolver à fila zera a dona, na produção conta quem concluiu. Muda o nome do botão da conta livre, que passa a dizer "Pegar".
4. **A busca é pelo número do atendimento e pelo rótulo do paciente, em todas as etapas**, inclusive Arquivadas, e diz onde a conta está e com quem. O número da conta não entra na busca.
5. **O nome na tela é o rótulo.** Ao lado do número aparece o rótulo que já existe ("Antônia F."), sem a palavra "Atendimento" na frente de cada um. A decisão 8 da ADR 0070 não muda: o nome inteiro continua fora do banco.
6. **Competência é o mês do fim do período da Conta.** A Conta sem período cai no mês em que foi concluída. É calculada, sem coluna.
7. **Arquivar é um carimbo, não uma situação.** A Conta Concluída ou Concluída com pendência ganha a data e a pessoa que arquivou; a situação fica como está. Painel, Retorno e reenvio continuam lendo a situação. Dá para desarquivar.
8. **Quem arquiva.** A faturista arquiva as dela, uma a uma ou todas as dela de uma Competência. Quem tem "painel completo" arquiva qualquer uma e a Competência inteira. Não entra permissão nova na Habilitação.
9. **O lote leva as Concluídas com pendência**, e a confirmação diz quantas são. A Conta arquivada que recebe Retorno da Validação volta sozinha para a Esteira.
10. **O Painel não muda com o arquivar.** Ele soma pela data de conclusão, com ou sem carimbo.

## Por que é surpreendente

- Quem ler a decisão 3 da ADR 0073 ou a decisão 10 da ADR 0070 vai esperar que a rota da fila filtre por `faturista_id`. Ela deixa de filtrar a leitura; o filtro que sobra é o de abrir o Guia.
- "Arquivada" parece uma situação da Conta e não é. Quem procurar o valor no CHECK de `situacao` não acha.
- O diretor pediu o nome do paciente e a tela mostra o rótulo. Não é esquecimento: o nome inteiro pede emendar a decisão 8 da ADR 0070 e não dá para preencher nas contas antigas, porque o PDF é apagado em 7 dias.

## Consequências

- A busca não cabe só no navegador: as Arquivadas não vêm na carga da tela, então a busca vai ao servidor.
- Pede uma migration em `cm_conta` (quando e quem arquivou), que só acrescenta.
- A aba Concluídas deixa de ter o teto das 100 mais recentes como única limpeza: quem limpa a Esteira é o arquivar.
- Três pontos esperam a confirmação do diretor e, se ele mudar, esta ADR ganha emenda: o rótulo no lugar do nome inteiro (decisão 5), a Competência pelo fim do período (decisão 6) e a faturista arquivar as próprias contas (decisão 8).

## Alternativas descartadas

- **Faturista continua vendo só as dela, e a busca só acha as dela e as livres.** A busca responderia "nenhuma conta" para a que está com a colega, que é o caso em que ela mais precisa da resposta.
- **Faturista abre a conta da colega só para leitura.** Abre uma segunda regra de acesso ao Guia para um ganho pequeno; saber com quem está resolve.
- **Abrir só mostra, e um botão "Pegar esta conta" dentro do Guia atribui.** Põe um clique a mais em toda conta e muda o "Concluir e abrir a próxima".
- **Gravar o nome inteiro do paciente.** Desfaz a desidentificação do banco inteiro (eventos e evidências passam a ter dono com nome) e deixa as contas antigas sem nome.
- **Competência pelo mês da conclusão no app ou pelo mês do envio.** São datas do módulo, não do faturamento: a conta de outubro concluída em novembro iria para o mês errado.
- **"Arquivada" como situação nova.** Obriga Painel, Retorno, reenvio e Concluídas a aprender um valor a mais, e desarquivar teria de lembrar qual das duas Concluídas a conta era.
- **Só quem tem "painel completo" arquiva.** Quem abre o ciclo novo de trabalho são as faturistas.
