---
status: accepted
amends: 0098
---

# O Início é a tela de cada pessoa, e a Minha Fila junta todos os módulos

Decisão do Pedro (18/11/2026, grill em duas rodadas com protótipo, todas as recomendações aceitas), a partir da reunião com o diretor no mesmo dia. O diretor disse que os gestores ainda não usam o app, que cobrar nos grupos não funciona e que a cobrança precisa sair do próprio app: quem entra vê primeiro o que deve entregar, com o caminho para resolver. Hoje o login manda todos para o painel de Reuniões, inclusive quem só tem Ouvidoria, Núcleo ou Contas médicas, e cada módulo guarda a sua lista. A ADR 0099 já tinha deixado esta tela para uma decisão própria. O protótipo está na branch `prototype/tela-inicial`, que não entra na main.

## Decisões

1. **O Início é uma tela nova, e o login cai nela.** Rota própria, primeiro item do menu, destino de todos menos a Secretária, que continua na tela dela e não vê Pendência (decisão 53 do diretor no PRD #1757). A capa com dois botões sai: quem não está logado vai para o login. O painel de Reuniões continua no endereço de hoje.

2. **A Minha Fila sai do painel de Reuniões e vira a lista do Início.** Emenda a decisão 10 da ADR 0098: o painel fica com cards, gráfico por setor, ranking e evolução; o alerta e a fila passam para o Início, com todos os módulos. A #1868 passa a entregar o cálculo e os cards.

3. **Uma fila só, por urgência.** Três grupos: Passou do prazo, Vence em até 48 horas (a antecedência que o diretor escolheu para o alerta) e Próximos 7 dias. O módulo é etiqueta na linha. Cada linha diz de onde veio e leva à tela dona, já no item. Só o que é um clique sem Anotação se resolve ali mesmo (Verificação realizada, presença em capacitação).

4. **O servidor monta a fila a partir de fontes.** Um endpoint chama uma função por módulo, a fonte. Todas devolvem o mesmo formato (título, origem, prazo, área, ação e destino), já recortado para quem pede. Fonte que falha não derruba a tela. Módulo novo entra como fonte nova.

5. **O Início não espera o PRD #1757.** O atraso é calculado pela data (item aberto com prazo vencido), que é a regra da ADR 0098 e já funciona no modelo de hoje. A primeira versão lê o que existe: Pendências (com o co-responsável e o lembrete do Núcleo sem Reunião, que hoje não aparecem na lista de ninguém), Atas a assinar, Atas paradas do Facilitador, próximas Reuniões, caso da Ouvidoria do setor, POP na etapa da pessoa, o que o Núcleo tem na Fase 1 e a conta na fila do faturista. Rotina, Contestação e casos do Núcleo entram quando a fatia de cada um subir.

6. **A fila de um papel é uma linha de resumo.** A fila do ouvidor, as contas sem dono e a triagem do Núcleo não têm responsável nomeado. Aparecem num bloco à parte, uma linha por fila, fora da contagem da frase.

7. **A frase é escrita por regra.** O topo diz quantos prazos venceram e há quanto tempo o mais antigo espera, a partir dos números, sem chamar IA (ADR 0082). Quem não tem nada vencido lê "Você está em dia", o próximo prazo e o que entregou nos últimos sete dias.

8. **A atenção vem do peso, não do movimento.** Faixa escura no topo enquanto há prazo vencido, o número de dias em destaque, vermelho contido só em texto e o contador no título da aba do navegador. Uma entrada ao abrir, nada piscando, e tudo parado para quem pediu menos movimento. O sino continua para o que aconteceu e não ganha aviso de prazo.

9. **"Quem responde a você" segue a regra do vínculo até o organograma.** O Super admin vê todas as pessoas com item, e o Facilitador vê os responsáveis das Reuniões dele (ADR 0098, decisão 7). Sinais: vencidos agora, em aberto, entregas em 90 dias no prazo e fora, Rotinas do ciclo e último acesso. Clicar na linha abre o que venceu e não foi entregue. A #1910 troca a regra de quem aparece quando o organograma chegar. Cada pessoa vê, no Início dela, os próprios números de 90 dias.

10. **O app registra o dia em que a pessoa abriu o Início.** Uma marca por pessoa por dia, sem trilha de cliques, guardada por 90 dias. Só aparece para quem já vê os itens da pessoa.

## Por que é surpreendente

- A Minha Fila, que o PRD #1757 pôs no painel de Reuniões, não mora lá.
- O login deixa de cair no `/dashboard`.
- O diretor pediu "piscando" e "a IA cobrando". A tela não pisca e a frase não usa IA.
- Existe um dado de acesso por pessoa, que o app não tinha.
- O Início lê Pendências antes de o ciclo novo delas estar no ar.

## Alternativas descartadas

- **Cards por módulo, ou a fila separada por área.** Vira um mapa do sistema, e o diretor pediu "o que você tem que entregar".
- **Tomar o lugar do `/dashboard`.** Quebra link, teste e o endereço do painel de Reuniões sem ganho.
- **A #1868 seguir como está e o Início repetir a fila.** Duas filas com a mesma regra, em dois lugares.
- **Esperar o PRD #1757 inteiro.** O problema é adoção agora, e as primeiras fatias dele estão paradas.
- **Piscar enquanto houver atraso.** Vira ruído em uma semana e atrapalha quem usa leitor de tela.
- **Frase gerada por IA a cada acesso.** Custo por abertura, texto que muda sem o estado mudar e nada para testar.
- **Hierarquia provisória pelo `role` e pelo setor.** A ADR 0033 trata o `role` como etiqueta interna, e ele não diz quem lidera quem.
- **Usar o `last_sign_in_at` do Supabase.** Marca o login, e a sessão dura dias.
- **Pôr cada item da fila comum na Minha Fila de todos do papel.** Infla o número de cada um com o que não é dele.
- **Prazo vencido também no sino.** Dois avisos para o mesmo prazo.

## Consequências

- O `CONTEXT.md` ganha Início, Quem responde a você, Registro de acesso e Fila do papel, e a Minha Fila muda de lugar e de alcance.
- A #1868 é reescrita para entregar o cálculo e os cards. A mudança de lugar do alerta e da fila vai ao diretor na Apresentação do PRD do Início; o PRD #1757 mantém a validação.
- Uma migration nova, a do Registro de acesso.
- O item "Início" do menu de Segurança do Paciente muda de nome, para não haver dois.
- Ficam com o diretor: quem vê o último acesso e como as pessoas são avisadas de que ele é registrado, e a confirmação de que cada um vê os próprios números.
