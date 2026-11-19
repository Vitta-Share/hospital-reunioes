---
status: accepted
amends: 0083, 0096
---

# Apresentação do PRD com o estado real, link no card, e Envio aos desenvolvedores pela Conversa da Demanda

Decisão do Pedro (19/11/2026, grill no terminal). Dois incômodos do mesmo fluxo com o diretor. Primeiro, a Apresentação do PRD guardava o "Plano validado" só no navegador de quem clicou: o Pedro abria a página de um plano já validado e via "Plano para validar", sem a observação. E o card da Demanda não tinha atalho para a página. Segundo, a resposta do diretor na Conversa da Demanda só chegava aos Desenvolvedores quando uma sessão do terminal rodava `conversa.py ler`: o diretor não tinha como dizer "terminei, podem pegar", e nada avisava o Pedro.

## Decisões

1. **A Apresentação lê o estado do GitHub quando abre.** Uma função nova da Vercel (`api/estado.js`, com o `GITHUB_TOKEN` que o Validar já usa) devolve se o PRD tem a label `validado:diretor` e, do último comentário `<!-- validacao-diretor -->`, a data, a hora e a observação. Com a label, o formulário dá lugar ao cartão "Plano validado" com a data e a observação (ou "Sem observação"); sem a label, a página pede validação, mesmo que exista comentário antigo, porque a validação vale só para a versão que o diretor viu. O `localStorage` fica só como reserva quando a função falha. Rejeitado: republicar a página no clique do Validar (uma função fazendo deploy na Vercel).

2. **O card ganha o atalho "Ver o plano", sem o código de validação.** O `apresentar.py publicar` grava no PRD o marcador `<!-- apresentacao: <url> -->`; a sincronização leva o link ao card, como faz com a Demonstração (ADR 0084). No Quadro, um botão quadrado no canto do card, no formato do botão da Demonstração, com o ícone de apresentação e um check quando o plano está validado; no Documento do card, um cartão "Plano". No PedroOS, o Selo "Validado pelo diretor" vira link para a mesma página. Os cinco planos já publicados recebem o marcador uma vez. Rejeitado: o link com o código montado pelo backend (o `SEGREDO` no app e qualquer admin podendo validar no lugar do diretor) e o app montar o endereço sozinho para todo PRD com a label.

3. **A Conversa da Demanda ganha o Envio aos desenvolvedores, por clique do diretor.** Só quem é do lado do hospital (quem não é Desenvolvedor) vê o botão, em toda Demanda que já tem issue. O agente lê as mensagens do diretor desde o último envio, mais o card e a última mensagem do Desenvolvedor como contexto, e mostra "Entendi assim:" em tópicos, com "Enviar" e "Corrigir". Só com o "Enviar" nasce o Ajuste do plano. A conversa ganha a linha "Enviado aos desenvolvedores" com a data e os tópicos aprovados; o que vem depois começa um envio novo. O custo do modelo fica gravado como o das outras conversas. Rejeitado: envio automático a cada mensagem (várias tarefas para uma ideia, e IA sem clique humano).

4. **O envio abre o Ajuste do plano, e o Pedro é avisado.** O Ajuste é o mesmo do Validar: sub-issue `ready-for-human` do Pedro na issue-raiz, que trava pelas dependências as fatias iniciais (abertas, `ready-for-agent`, sem `in-progress` e sem bloqueio aberto). O PedroOS mostra o Selo do Ajuste e manda o aviso no celular, como na baixa de uma onda. Rejeitado: só um comentário no PRD (ninguém vê) e o Ajuste sem travar (a onda começaria em cima de um plano que mudou).

5. **No GitHub entra só a interpretação do agente.** O corpo do Ajuste diz o que o diretor quer mudar e o que muda em cada card, com o número, sem citar a fala dele e sem dado de paciente. Vale também para o Validar: a observação passa pelo mesmo agente, e o comentário e o Ajuste levam a interpretação; o texto original fica no app. Isso reforça a decisão 8 da ADR 0083 e emenda a decisão 6 da ADR 0096: a resposta do diretor continua sem ir para o GitHub, e agora chega aos Desenvolvedores também pelo Envio, além da leitura pelo terminal. Rejeitado: copiar as mensagens na íntegra para o Ajuste (o repositório é público).

## Consequências

- A função da Vercel passa a chamar o app para guardar a observação original e pedir a interpretação; essa parte fica numa fatia própria, depois do Envio.
- O `conversa.py ler` continua valendo para a sessão que espera uma resposta específica.
- A Conversa da Demanda passa a guardar o envio (quando, quem, os tópicos aprovados e o número do Ajuste), para saber de onde começa o próximo.
