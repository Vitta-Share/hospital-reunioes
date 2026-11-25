# Quando e o que pedir ao Pedro

O Felipe manda estas mensagens ao Pedro pelo WhatsApp. O Claude mostra a mensagem pronta num bloco de código, com o que é específico já preenchido (login, número do card, link), e diz em uma linha por que ela vai agora. O Felipe copia e manda.

| Quando | Mensagem | O que o Pedro faz do lado dele |
|---|---|---|
| Criou a conta no GitHub (Parte 1) | Conta criada | `gh variable set DIRETOR_LOGINS --body "<login>"` no repositório (com o login dos outros diretores, se houver, separados por vírgula) e convida o login como colaborador com escrita no `hospital-reunioes` e no `hospital-arquivos` (ADR 0113). O merge fica travado no Claude dele e no check do PR do diretor |
| Não achou o convite (Parte 6) | Sem convite | Convida de novo nos dois repositórios |
| O card nasceu sem as etiquetas depois de um minuto | Card sem label | Confere a variável `DIRETOR_LOGINS` e põe as labels à mão naquele card |
| Abriu um card (Parte 9) | Card novo | Grill técnico com `/grill-with-docs #N` e, depois, `/to-prd` e `/to-issues` |
| Abriu o PR rascunho do protótipo (Parte 8) | Protótipo pronto | Clica em "Approve and run" no PR para o CI rodar e olha o protótipo junto com o card |
| A ideia precisa de uma decisão que não é dele (contrato, custo, outra área) | Preciso de uma decisão | Responde no card ou chama o Felipe |
| Travou num passo que o Claude não resolveu | Travei | Ajuda pelo WhatsApp ou numa chamada |
| Quer testar com a IA de verdade no app local | IA de verdade | Decide. O padrão é não: a IA simulada basta para o protótipo e chave de API custa por uso |

Merge, migration, subida para produção e chave de produção nunca são pedidos do Felipe: tudo isso acontece do lado da Vitta depois do card. Se ele quiser saber quando a mudança chega ao app, a mensagem é "Card novo" com a pergunta no fim.

## Conta criada

```
Fala Pedro, criei minha conta no GitHub

Login: <login>

Pode liberar pra eu abrir os cards e me convidar pro time? Qualquer coisa me chama.
```

## Sem convite

```
Fala Pedro, o Claude não achou o convite do GitHub

Login: <login>

Consegue me convidar no hospital-reunioes e no hospital-arquivos?
```

## Card sem label

```
Fala Pedro, abri um card e ele ficou sem as etiquetas

Card: https://github.com/pedrorezendefig/hospital-reunioes/issues/<N>

Acho que meu login não tá liberado ainda. Dá uma olhada?
```

## Card novo

```
Fala Pedro, abri um card novo

<título do card>
https://github.com/pedrorezendefig/hospital-reunioes/issues/<N>

Quando der, faz a parte técnica. Qualquer coisa me chama.
```

## Protótipo pronto

```
Fala Pedro, montei o protótipo do card <N>

Card: https://github.com/pedrorezendefig/hospital-reunioes/issues/<N>
Protótipo: https://github.com/pedrorezendefig/hospital-reunioes/pull/<PR>

Tá em rascunho, só pra vocês verem a ideia funcionando.
```

## Preciso de uma decisão

```
Fala Pedro, no card <N> ficou uma dúvida que não é só minha

<a dúvida, numa frase>

Card: https://github.com/pedrorezendefig/hospital-reunioes/issues/<N>

Me fala o que acha.
```

## Travei

```
Fala Pedro, travei no setup do Claude

Parte: <número e nome da parte>
O que aparece: <a mensagem da tela, numa linha>

Consegue me dar uma força?
```

## IA de verdade

```
Fala Pedro, queria testar <a tela> com a IA de verdade no meu Mac

Hoje ela responde simulada. Vale pôr uma chave ou segue assim?
```
