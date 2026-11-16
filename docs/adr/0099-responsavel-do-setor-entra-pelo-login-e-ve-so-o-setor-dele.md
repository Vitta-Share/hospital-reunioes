---
status: accepted
amends: 0034
---

# O Responsável do setor entra pelo login, vê só os casos do setor dele e responde pelo app

Decisão do Pedro (16/11/2026, grill a partir do áudio do diretor). Um médico cadastrado como responsável de setor entrou no app com a senha dele, abriu a Ouvidoria e viu os casos de todos os setores. Só conseguia responder pelo link do e-mail. O diretor tinha pedido o contrário na especificação dele (`Especificacao_Modulo_Ouvidoria.md` v1.0, seção 10): `responsavel_setor` vê e responde apenas as manifestações do seu setor. A ADR 0034 trocou isso pelo link sem login (decisão 4) e deu o índice de todos os casos a todo papel de Reuniões (decisão 8), com a nota "revisita se o uso provar necessidade". O uso provou.

## Decisões

1. **O login vira Responsável do setor pelo e-mail.** O e-mail de quem entrou é casado, sem diferenciar maiúsculas, com as linhas vigentes do cadastro de responsáveis. Não nasce coluna nem perfil novo: o vínculo vem do cadastro que o ouvidor já mantém (ADR 0055). A tela do cadastro mostra, em cada linha, se aquele e-mail tem login no app, para o ouvidor achar o e-mail digitado errado.

2. **O responsável vê os casos do setor, não os do hospital.** Titular, substituto e gestor vigentes veem os casos acionados para os setores em que estão vigentes: primeiro "A responder" (o caso aguardando a área, com o prazo) e embaixo o histórico do setor já respondido, só para leitura. O recorte é pelo setor, e não pelo e-mail recebido, para cobrir o e-mail perdido, o substituto e o gestor que recebe o escalonamento. O conteúdo sai pelas mesmas guardas da Tela do responsável: caso com sigilo reforçado só com a nota da ouvidoria, caso anônimo sem identificação de quem manifestou.

3. **O índice geral fica com quem mantém a fila.** Emenda a decisão 8 da ADR 0034. O índice de todos os casos (sem relato, como hoje) fica com o Perfil da Ouvidoria, a Secretária (que mantém a fila, decisão 53 do PRD #1757) e o Super admin. Quem tem login e não é nenhum desses nem responsável vigente deixa de ver a Ouvidoria: o item some do menu e o servidor não devolve caso nenhum.

4. **Responder pelo app abre a mesma Tela do responsável.** Emenda a decisão 4 da ADR 0034. O botão RESPONDER na linha do caso abre a Tela do responsável, com a mesma ordem da RN-59, os mesmos botões (responder, solicitar prorrogação, devolver à Ouvidoria) e as mesmas guardas. Muda só a porta: o login no lugar do token. O link do e-mail continua sendo o caminho de quem não entra no app.

5. **Titular, substituto e gestor vigentes podem responder.** A trilha do caso registra quem respondeu.

6. **Uma resposta por caso, por qualquer porta.** Responder, devolver ou pedir prorrogação pelo app consome o link do e-mail, como já acontece quando se usa o link. Usar o link tira o botão do app.

## Por que é surpreendente

- O cadastro de responsáveis, que só servia para mandar e-mail, passa a decidir o que alguém vê no app.
- Médico, Facilitador e Colaborador comuns, que viam a fila inteira da Ouvidoria, deixam de ver o item no menu.
- A Tela do responsável, desenhada para abrir sem senha a partir de um e-mail, passa a abrir também por dentro do app.

## Alternativas descartadas

- **Coluna `participante_id` no cadastro, com o ouvidor escolhendo a pessoa.** Pede migration e recadastro de todos os setores; o e-mail já é único em `participantes`.
- **Recorte pelo e-mail de acionamento recebido.** Quem perdeu o e-mail, o substituto e o gestor ficariam sem o caso.
- **Ninguém fora do Perfil da Ouvidoria vê o índice.** Tiraria a fila da Secretária, que a mantém, e o apoio do Super admin.
- **Tela nova de resposta dentro da Ouvidoria.** Abriria um segundo caminho para o sigilo e o anonimato vazarem, com outra ordem de leitura para testar.
- **Só titular e substituto respondem.** O gestor recebe o escalonamento justamente para destravar o caso.
- **Portas independentes.** O mesmo caso poderia receber duas respostas, uma pelo link e outra pelo app.

## Consequências

- Os verbetes Responsável do setor, Perfil da Ouvidoria e Tela do responsável do `CONTEXT.md` mudam.
- O endpoint da fila da Ouvidoria passa a recortar por papel, e nasce uma porta autenticada para as ações da Tela do responsável, ao lado das rotas com token.
- A tela inicial com o que está pendente para cada pessoa (reunião, ouvidoria, rotina) fica fora desta decisão. Depois que esta subir, o caso a responder entra na Minha Fila do painel (#1868) por Demanda própria.
