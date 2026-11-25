# Modelo do card do diretor

O card que o Claude do Felipe abre segue o formato do card da aba Tecnologia (ADR 0077), para o Pedro tratar os dois do mesmo jeito: o `/grill-with-docs #N` lê o bloco "🛠️ Para o desenvolvedor" e explica o card antes do grill técnico. A diferença é que este card não tem Demanda no app, então não leva o marcador `demanda-vitta` nem a seção "Origem" com o link da Demanda.

Regras:

- Primeira linha: uma frase de resumo do que muda, sem título. O Hospital OS lê essa linha.
- O bloco "👔 Para o diretor" passa pela skill `humanizer` (a amostra de voz é o bloco de um card `origem:diretor` já publicado: `gh issue list --repo pedrorezendefig/hospital-reunioes --label origem:diretor --state all --limit 5`).
- Sem dado real: nada de nome de paciente, de funcionário, número de prontuário, preço de contrato ou print de produção. O repositório é público.
- Decisão do Felipe vai em "Decisões de negócio" como escolha dele, com o porquê. Dúvida técnica que ele não soube responder vai em "Ficou em aberto", nunca chutada.
- Sem labels nem dono no comando: a Action `card-do-diretor.yml` põe `needs-triage`, `origem:diretor` e o Pedro.

```markdown
<Uma frase: o que muda para quem usa o app.>

## 👔 Para o diretor

**O que muda:** <uma frase, em palavras simples>

**O que você precisa saber:**
- <até cinco tópicos curtos>

## 🛠️ Para o desenvolvedor

**O que o diretor quer:** <o pedido, em poucas linhas>

**Por que ele pediu:** <o problema de hoje>

**O que já ficou decidido com ele:** <as decisões de negócio, em prosa curta>

**Onde mexe no código:** <arquivos e telas que o Claude achou, com caminho; "não informado" se não leu o código>

**Cuidados:** <regra do domínio que a ideia toca, ADR que ela contraria, risco>

**Como saber que acabou:** <o que o diretor vê na tela quando estiver pronto>

---

## Problema

<o problema do ponto de vista de quem usa o app>

## Solução

<a solução, do ponto de vista de quem usa o app>

## Histórias de usuário

1. Como <papel>, quero <ação>, para <valor>.

## Decisões de negócio

1. **<a pergunta do grill>**
   Escolha: <o que o Felipe escolheu>
   Por quê: <o motivo>

## Protótipo

<link do PR rascunho e o que ele responde; "sem protótipo" quando não houve>

## Ficou em aberto

- <dúvida técnica para o grill do Pedro; "nada" se não houver>
```
