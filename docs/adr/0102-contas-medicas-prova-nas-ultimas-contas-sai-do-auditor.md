---
status: accepted
amends: 0081, 0082
---

# Contas médicas: a prova nas últimas contas sai do Auditor

Decisão do Pedro (18/11/2026, issue #1920). Emenda a decisão 7 e a prova da decisão 13 da ADR 0081, e a prova da decisão 3 da ADR 0082.

## Contexto

- A prova refazia o Passo B nas 10 últimas Contas concluídas da Operadora para mostrar o que mudaria com uma Regra nova ou alterada. Rodava em três lugares: no botão "Provar nas últimas contas" do "Ensinar uma regra nova", em cada item de regra do lote do Auditor (e o ok ficava travado sem ela) e na recomendação do Auditor para o Tema de Regra pendente na Validação.
- Em 30 dias ela custou US$ 117,70 dos US$ 370 gastos com IA, quase tudo no pico de 8 e 9/11 (ADR 0082).
- Ninguém usa a prova hoje, e ela é a parte mais complexa do Auditor: monta a Memória candidata, relê os eventos guardados, refaz os tetos e compara as Linhas conta a conta.

## Decisões

1. **A prova sai inteira (emenda a decisão 7 da ADR 0081).** Sem botão de provar, sem a rota `POST /contas-medicas/operadoras/{sigla}/regras/prova` e sem a prova automática de cada item do lote. O ok do lote aplica um item de regra sem esperar prova.
2. **A recomendação da Validação sai sem prova (emenda a decisão 13 da ADR 0081 e a decisão 3 da ADR 0082).** O Auditor recomenda o Tema de Regra pendente lendo a Memória e o Tema, sem refazer Contas. A estimativa do botão "Pedir recomendação ao Auditor" conta só as recomendações, e o cartão não mostra mais o resumo da prova. O resto da decisão 3 da ADR 0082 continua: o Auditor pedido pelo botão roda em `CM_IA_MODELO_VALIDACAO`.
3. **O resto do Auditor fica.** A conversa da Operadora, o lote, o ok, o "corrige o item N", o "revisar pendentes", o contrato na conversa, o Faltou isto, o segundo agente e a recomendação da Validação seguem como estão.
4. **O banco não muda.** A tabela `cm_prova` e a coluna `cm_validacao_tema.recomendacao_prova_id` ficam paradas, com o histórico. O passo `PROVA` continua valendo no CHECK de `cm_chamada_ia`, e a linha "Provas de regra" do Painel segue lendo as chamadas antigas. As diárias pagas e as cirurgias dos tetos continuam gravadas com a Conta (`faltantes.base_dos_tetos`), sem quem as leia.

## Consequências

- Uma Regra nova ou alterada vale sem que ninguém veja antes o que ela faria nas Contas concluídas. Quem decide confere o texto, o motivo e os conflitos; o efeito aparece nas próximas análises.
- A recomendação da Regra pendente fica mais barata e mais rápida, e perde o sinal de "Linha feita que sumiria".
- Voltar com a prova pede código novo, não migration: os dados antigos e o passo da chamada continuam no banco.
