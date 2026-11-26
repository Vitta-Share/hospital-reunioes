# A aba Tecnologia

A aba Tecnologia é onde a diretoria acompanha o que a Vitta (a empresa que cuida dos sistemas do hospital) está fazendo nos sistemas. Ela só informa: mostra a fase de cada pedido e o que foi entregue, e nada se pede nem se responde por ela. Desde 25/11/2026, o que pede uma ação sua chega no GitHub, num lugar só: o card no seu nome, a menção num comentário e a notificação do próprio GitHub.

Só quem tem acesso de administrador do aplicativo enxerga a aba. Ela tem duas abas no alto: **Quadro**, com a fase de cada pedido, e **Entregas**, o que já foi entregue. Não há mais chat com a IA, botão de pedido novo, lista "Esperando você" nem conversa dentro do pedido.

Melhoria você pede pelo seu Claude, no seu computador: ele faz as perguntas, monta o protótipo e abre o card no GitHub, e o card aparece sozinho no Quadro com o selo **Pedido do diretor**. Bug você relata pelo robozinho do canto inferior direito, o Assistente do app (veja abaixo). Dúvida de uso também vai para o robozinho.

Na tela do computador, o **Quadro** mostra os pedidos em colunas pela Etapa: Registrada, Em análise, Planejada, Em desenvolvimento e Entregue. A Etapa muda sozinha conforme a Vitta trabalha, e ninguém arrasta card. No alto de cada coluna ficam o nome da Etapa e quantos pedidos ela tem, e esse cabeçalho continua à vista enquanto você rola a página. A coluna Entregue junta o que foi entregue e o que já está Em produção nos últimos 30 dias e mostra os 8 mais recentes; o número no alto conta todos. Os pedidos que não serão feitos ficam fora das colunas. Para vê-los, ligue **Mostrar as que não serão feitas**, na barra de filtros, e eles aparecem numa coluna Não será feita, no fim do Quadro. No pé da coluna Entregue, o **Ver todos nas Entregas** abre a aba Entregas, que guarda o histórico inteiro, inclusive o que foi entregue há mais de 30 dias. Em cada coluna, o pedido mais novo vem primeiro. O card mostra o número da Demanda, o título, o selo **Bug** ou **Melhoria**, as iniciais de quem cuida, as partes entregues quando o pedido tem partes, a versão quando ele já está Em produção e os selos **Tem demonstração** e **Envio falhou**. A barra de filtros do Quadro não tem o campo de Etapa, porque a Etapa já é a coluna, e o **Limpar filtros** também desliga o Mostrar as que não serão feitas.

O clique num card abre o pedido num painel ao lado do Quadro, que continua à vista atrás dele. O painel tem a data de abertura e o documento do pedido, só para ler: não tem conversa, nem os botões Apagar, Revisar, Reenviar ou Designar de novo. O painel fecha pelo X ou pela tecla Esc. O botão **Ampliar** leva o pedido para a tela toda, e o **Voltar ao quadro** traz as colunas de volta. O link de um aviso antigo do sino ou do e-mail continua abrindo o pedido no painel do Quadro; o aviso de uma pergunta antiga abre a aba Tecnologia.

No celular, e em telas menores que a do computador, no lugar do Quadro fica a lista dos pedidos, com o título, a Etapa e o selo **Bug** ou **Melhoria** de cada um, do mais recente para o mais antigo. No alto da lista há uma busca pelo título, que acha o pedido sem diferenciar maiúscula e acento, e os filtros Tipo, Etapa, Origem e Projeto, que combinam entre si e com a busca. O clique num pedido abre o documento dele ao lado da lista; o **Ampliar** abre em tela cheia, e o **Voltar à lista** traz a lista de volta. No celular a lista abre primeiro, e o mesmo botão leva de volta a ela.

A aba junta os pedidos de cada Projeto: o **Aplicativo do Hospital**, a **Ana**, a agente de atendimento do hospital, e os outros projetos da Vitta. Os pedidos da Ana aparecem ali, no Quadro e na lista do celular, ao lado dos do aplicativo, e cada um traz um selo pequeno com o nome do Projeto. Para ver só um deles, escolha no campo **Projeto**, na barra de filtros: Todos, que é como a aba abre, Aplicativo do Hospital, Ana ou outro projeto. O Projeto combina com os outros filtros, e o **Limpar filtros** volta o campo para Todos. O pedido de um projeto novo da Vitta, que o aplicativo não acompanha, mostra o nome do projeto e o link do plano, marcado como **Vitta**, e não muda de Etapa sozinho. O mesmo plano nunca abre dois pedidos, e com o primeiro pedido o filtro Projeto passa a listar esse projeto.

## O que é uma Demanda

Uma Demanda é um pedido sobre um dos sistemas: um bug ou uma melhoria. Ela é o espelho, no aplicativo, de um card no desenvolvimento da Vitta: o card que você abre pelo seu Claude, o que a Vitta abre e o bug que o robozinho manda.

Cada Demanda tem um número, que aparece como "Demanda 42", sem cerquilha, e não muda. Aparece no topo do documento do pedido aberto e, menor, em cada card do Quadro. É o jeito curto de combinar com a Vitta de qual pedido se está falando: basta dizer "a Demanda 42".

Para mandar um pedido a alguém, use o botão **Copiar link**, no documento do pedido aberto. O botão copia duas linhas prontas para colar no WhatsApp: na primeira, o número e o título, como "Demanda 42: Levar o selo ao card"; na segunda, o link que abre aquele pedido no aplicativo. Depois de copiar aparece o aviso "Link copiado". Se o celular ou o navegador não deixar copiar sozinho, o texto aparece numa caixa, já selecionado, para você copiar à mão. Quem recebe o link precisa entrar no aplicativo e só abre o pedido se tiver acesso a ele.

Os cards que a Vitta abre pelo desenvolvimento, sem passar por você (uma melhoria ou um bug do aplicativo que ela mesma decidiu fazer), também viram Demanda e aparecem no Quadro marcados como **Vitta**, com a Etapa e o documento. Os ajustes internos da Vitta, que não mudam nada no aplicativo que você usa (as ferramentas e a documentação dela), não aparecem. O card que você abre pelo seu Claude, com a label `origem:diretor`, também vira Demanda sozinho: ele aparece no Quadro com o selo **Pedido do diretor** e a Etapa em que está, e a Etapa muda sozinha conforme a Vitta trabalha nele.

Quando a Vitta precisa de uma decisão, de um dado ou de uma ação sua num pedido, ela abre um card no seu nome no GitHub (uma pergunta ou uma tarefa) e o GitHub avisa você. Você responde com um comentário no próprio card. Nada disso passa mais pela aba Tecnologia.

Não chame de pendência, tarefa nem chamado. Pendência é outra coisa no aplicativo: é o compromisso operacional que sai de uma reunião do hospital, e mora em outro lugar.

## Os anexos da Demanda

Os anexos são prints de tela guardados junto da Demanda, para quem vai resolver ver o que você viu. O print entra pelo botão de anexo do robozinho, no **Relatar um bug**, em .png, .jpg, .jpeg ou .webp, de até 3,75 MB, e fica guardado na hora em que você manda. São até 10 anexos por Demanda.

Os anexos ficam só dentro do aplicativo. Eles nunca vão para o material público do desenvolvimento, porque um print do hospital pode ter nome de paciente ou de colaborador: o pedido diz só quantos há, por exemplo "Anexos: 2 imagens na Demanda", e quem desenvolve busca os arquivos pelo aplicativo.

Os arquivos são apagados 30 dias depois de a entrega ficar **Em produção**, o que dá tempo de conferir a correção com o print na mão. Se a entrega fica **Não será feita**, eles são apagados logo, em até uma hora. Fica o registro de que existiram (o nome, quem mandou e quando), marcado como apagado.

## Quem vê

Todo administrador do aplicativo vê todas as Demandas, com ou sem login do GitHub no cadastro: as suas, as de outra pessoa da diretoria e os cards que a Vitta abriu pelo desenvolvimento, com o nome de quem pediu em cada card. Assim você e a Vitta olham a mesma tela e falam do mesmo pedido pelo mesmo número. Cada pedido traz o selo da **Origem**: **Pedido do diretor**, quando nasceu do card que você abriu pelo seu Claude, **Vitta**, quando a Vitta o abriu, ou **Relato no app**, quando veio do robozinho. No pedido que já virou card, o documento do pedido mostra a todos o número e o link do card e o número de cada parte.

Em cada pedido que já virou card aparece o **Responsável**, a pessoa que cuida dele, no Quadro e no pedido aberto. Ele vem de quem está com o card no desenvolvimento, e pode ser alguém da Vitta ou da diretoria, inclusive você. O login do GitHub no cadastro só serve para dar nome ao **Responsável**: quando o card está com alguém que tem esse login no cadastro, aparece o nome da pessoa; quando não, aparece o login. Quando a Vitta passa o pedido para outra pessoa, o nome muda sozinho na sua tela; você não precisa fazer nada, e no aplicativo não há como trocar quem cuida.

Quem desenvolve na Vitta é o **Desenvolvedor**: um administrador do aplicativo que tem o login do GitHub no cadastro. Ele vê o mesmo que você. A lista dele abre em **Para mim**, os pedidos de que ele é o Responsável, e tem também **Minhas**, os pedidos que ele mesmo fez, e **Todas**. Ele tem também os filtros **Responsável** e **Envio falhou**, que combinam com os de todo mundo. **Para mim**, Minhas, Todas, Responsável e Envio falhou só aparecem para o Desenvolvedor: a lista do diretor já traz todas as Demandas.

O endereço da página acompanha o pedido aberto: ao recarregar a página, o mesmo pedido volta aberto. Se o link é aberto num celular ou computador que ainda não entrou no aplicativo, ele pede o login antes e, depois do login, a tela abre no pedido do link, e não no painel inicial. Se o filtro que você estava usando esconde o pedido do link, os filtros voltam a mostrar tudo e o pedido abre. Se o link é de um pedido que não existe mais ou com o endereço errado, aparece "Você não tem acesso a esta Demanda", sem o título nem o número do pedido.

## A Etapa

Quando o pedido vira trabalho de desenvolvimento, ele ganha uma **Etapa**, que conta em que pé está a entrega, em palavras de quem pediu:

- **Registrada**: o pedido ainda não virou card, como o bug do robozinho antes do Enviar à Vitta.
- **Em análise**: a Vitta está entendendo o que precisa ser feito.
- **Planejada**: já se sabe o que fazer, o trabalho está na fila.
- **Em desenvolvimento**: está sendo feito agora.
- **Entregue**: está pronto, mas ainda não chegou ao aplicativo que você usa.
- **Em produção**: já está no ar, e dá para usar. A lista diz desde qual versão do aplicativo.
- **Não será feita**: decidiu-se não fazer.

A Etapa nunca é digitada à mão: ela é lida do planejamento da Vitta e aparece sozinha na lista. Quando a entrega tem partes, a lista mostra quantas já foram entregues. Assim que a Vitta começa a construir, a Etapa passa sozinha para Em desenvolvimento, e quando a versão nova do aplicativo sobe, passa para Em produção. Quando a entrega é dividida em partes, o pedido fica Em desenvolvimento desde o começo da primeira parte até a entrega da última, mesmo nos dias em que nenhuma parte está sendo feita, e não volta para Planejada no meio do caminho. O pedido que ainda não começou continua Planejada.

Ao abrir um pedido que já foi para a Vitta, ele aparece como um documento curto, em quatro partes:

- **Em uma frase**: o que muda, numa frase só.
- **O que muda**: o que aquela entrega acrescenta, em linguagem de quem usa, em até cinco tópicos. Se houver mais, o botão **Ver tudo** mostra os outros.
- **Partes**: quando a entrega é feita em partes, elas aparecem agrupadas por Onda: **Onda 1**, **Onda 2** e assim por diante, mesmo quando há uma parte só. As partes da mesma Onda entram juntas, e a Onda 1 vem primeiro. Cada parte mostra o número dela, com cerquilha na frente ("#N"), em que pé está e quando ficou pronta. Enquanto outra parte que ela espera não fica pronta, ela mostra **Espera a #N**, uma linha para cada; quando a outra não é parte deste pedido, a linha diz "Espera a #N, de outro pedido". A Onda vem da ordem que a Vitta combinou no desenvolvimento, e ninguém a digita.
- **Datas**: quando o pedido foi criado, quando foi entregue e quando entrou em produção.

No topo do documento, ao lado de "Demanda 42", aparece o número do pedido inteiro no desenvolvimento, também com cerquilha na frente. Esses números não são link: servem para você e a Vitta saberem de que pedido e de que parte estão falando.

Quando a Vitta grava um vídeo mostrando a entrega funcionando, o documento ganha também a seção **Demonstração**, num cartão próprio, com o link para assistir, e o pedido aparece na lista com o selo **Tem demonstração**. Sem vídeo, nem o selo nem a seção aparecem. Se a Vitta troca o vídeo, o link novo substitui o antigo; depois de chegar ao pedido, o vídeo não some sozinho.

O que o hospital precisa fazer para começar a usar uma entrega vira um card de implantação no seu nome no GitHub, ligado ao card da entrega. Você passa para quem vai fazer e fecha o card quando o hospital terminou, tudo pelo GitHub. O card da entrega ganha a parte Implantação no documento, logo depois de O que muda: cada card de implantação com o que é, com quem está e se está feito ou aberto, e quantos já foram feitos. Cada card de implantação fechado conta como feito. No Quadro, o card mostra o selo "Implantação 1 de 3" enquanto falta algum, e o selo some quando todos estão fechados. A conta anda sozinha quando um card de implantação fecha no GitHub. O card de implantação não conta como parte da entrega: ele fica fora do "partes entregues", e a entrega fecha sem esperar por ele. Por isso a entrega fica Em produção mesmo com a implantação por fazer: o que falta para usar não segura a entrega. Entrega sem card de implantação não mostra a parte Implantação.

Quando a Vitta publica o plano de um pedido para você validar, o card do Quadro ganha o botão quadrado **Ver o plano**, com o ícone de apresentação, que abre a página do plano em outra aba. Depois que você valida, o botão ganha um check pequeno. Se o card também tem vídeo, o botão do vídeo fica no canto e o do plano ao lado. Ao abrir o pedido, o documento mostra o cartão **Plano**, com o link para a mesma página. Para validar, use o botão Validar da própria página do plano: o botão do card só abre a página. Não chega aviso no sino nem e-mail quando o plano aparece no card.

Depois que você valida o plano pela página, o pedido aberto mostra, ao lado da Etapa, o selo verde **Plano validado em** com a data, por exemplo "Plano validado em 16/11/2026". Só os pedidos que passaram pela página do plano têm o selo. Se a Vitta publica o plano de novo, o selo sai até você validar a versão nova. Se, ao validar, você escreveu uma observação, o Pedro revê o plano por causa dela, e o documento mostra a faixa "O Pedro está ajustando o plano pela sua observação. As partes que esperam por isso começam depois." Cada parte que espera esse ajuste mostra **Espera o ajuste do plano** no lugar do "Espera a #N". Quando o ajuste termina, a faixa sai, e as partes voltam a mostrar só o que ainda as segura. O ajuste não é uma parte da entrega e não conta nas partes entregues. A sua observação não volta para a tela: ela fica guardada junto do plano, no desenvolvimento. O Quadro, as Entregas e a lista do celular continuam como estavam.

Quando o pedido entra em produção, e quando o vídeo de demonstração fica pronto, chega um aviso no sino e por e-mail. No seu pedido, o aviso vai para você; nos pedidos que a Vitta abriu, vai para a diretoria. O e-mail traz a frase e os tópicos do documento, e o link dele, como o clique no sino, abre o pedido. Cada coisa avisa uma vez só: o mesmo vídeo de novo não gera outro aviso.

Esse texto vem do planejamento da Vitta e não se edita no aplicativo. Enquanto a Vitta não escreve o resumo, o documento mostra "Descrição em preparação".

## As Entregas

A aba **Entregas**, ao lado do Quadro, mostra o ritmo do trabalho: quantos pedidos chegam e quantas entregas saem por semana. A semana começa na segunda-feira, e o dia conta pelo horário do hospital. Cada pedido conta uma vez, mesmo quando foi feito em partes.

No alto ficam dois números: os **pedidos** que chegaram e as **entregas** que saíram nas últimas 4 semanas, contando a semana de hoje. Embaixo de cada um, uma frase compara com as 4 anteriores, por exemplo "+6 contra as 4 anteriores". Passar o mouse num número mostra do que ele é feito: nos pedidos, quantos são bugs e melhorias; nas entregas, quantas são G, M e P. O pedido conta na semana em que o card nasceu: no pedido do diretor, o dia em que o card nasceu; no da Vitta, o dia em que ela abriu o card no desenvolvimento.

Abaixo dos números, o gráfico das últimas 12 semanas mostra, em cada semana, a barra dos pedidos e a das entregas lado a lado. A barra das entregas se divide em G, M e P, do azul mais escuro para o mais claro. Passar o mouse numa semana mostra o que saiu nela, com o título e o tamanho de cada entrega.

O **Tamanho da entrega** diz quanto trabalho a entrega levou, pelo número de partes em que a Vitta dividiu o pedido: **P** é o pedido de até 1 parte, **M**, de 2 a 5, e **G**, de 6 partes em diante. O aplicativo calcula o tamanho sozinho, pelo desenvolvimento, e ninguém estima nem digita nada.

Embaixo do gráfico fica a lista do que já foi entregue nas últimas 12 semanas, agrupada por semana, com a mais nova em cima. O cabeçalho de cada semana diz quantas entregas saíram e de que tamanho, por exemplo "Semana de 09/11: 3 entregas (1 G, 2 P)". Cada linha mostra o tamanho, o título, se é bug ou melhoria, a versão que está em produção e a data de entrega, o dia em que o pedido ficou pronto. Quando a entrega tem vídeo de demonstração, a linha mostra também um ícone de vídeo, que abre o vídeo em outra aba.

Clicar numa semana do gráfico (no celular, tocar) mostra na lista só as entregas daquela semana, e a tela desce até ela. A barra da semana fica marcada, e no alto da lista aparece o botão "Semana de 09/11, mostrar todas". Clicar de novo na barra, ou nesse botão, volta à lista inteira. Se naquela semana nada foi entregue, a lista diz "Nenhuma entrega nesta semana."

No fim da lista, o botão **Ver semanas anteriores** traz as 12 semanas mais antigas, embaixo das que já estão na tela, e pode ser clicado de novo para ir mais longe. Ele some quando não há entrega mais antiga. Os filtros também valem para essas semanas.

Cada entrega abre com o que mudou quando você para o mouse em cima dela, e fecha quando o mouse sai. O texto é o mesmo do Documento do card. O clique deixa a entrega aberta, e no celular é só tocar. Fica uma entrega aberta por vez. Aberta, ela mostra três botões: **Demonstração**, só quando há vídeo, abre a página do vídeo em outra aba; **Abrir o card** mostra o Documento do card, com as partes e as datas de cada uma; e **Copiar link** copia o link do pedido para mandar a alguém. A entrega que ainda não tem o texto do que mudou mostra "Descrição em preparação".

Os filtros são **Bug** ou **Melhoria**, a Origem (**Pedido do diretor** ou **Vitta**), o Responsável e o **Projeto** (Todos, Aplicativo do Hospital, Ana ou outro projeto da Vitta). Eles combinam entre si, por exemplo as melhorias da Vitta, e valem para os números, o gráfico e a lista. Com Ana escolhido, você vê só o ritmo da Ana; com Todos, que é como a aba abre, todos juntos. O pedido de um projeto novo da Vitta conta como pedido, mas nunca como entrega, porque o aplicativo não acompanha o trabalho desse projeto. Cada entrega traz um selo pequeno com o nome do Projeto, na lista e no que aparece ao passar o mouse numa semana do gráfico. A entrega da Ana sai sem versão, porque a Ana ainda não tem a etapa Em produção: a linha dela mostra o tamanho, o título e a data de entrega. Ali entram os mesmos pedidos que você vê no Quadro: os seus e os que a Vitta abriu. Pedido apagado não aparece. O que fechou como Não será feita conta como pedido, mas nunca como entrega.

A aba é só para acompanhar: nada se move por ali. Ninguém muda a Etapa nem o Responsável pelas Entregas.

## O manual

O aplicativo tem um manual, e ele fica dentro do próprio aplicativo. Para abrir, clique em **Manual**, com o ícone de livro, no canto inferior esquerdo da tela, logo acima do Recolher menu. O item está no menu do aplicativo e também no da Administração. No celular, ele fica no fim do menu que abre pelo botão do alto.

O manual tem duas abas. A aba **Aplicativo do Hospital** tem uma página para cada parte do aplicativo (Reuniões e Pendências, POPs, Ouvidoria, Contas médicas, Central de Comando, Dados do Atendimento e Tecnologia), com as tarefas em passo a passo, prints de tela e fluxogramas. Cada pessoa vê só as páginas das partes do aplicativo que ela já usa. As páginas vão chegando aos poucos, uma parte de cada vez. A aba **Ana** mostra como a Ana funciona por dentro e só aparece para quem é Super admin; por enquanto ela diz "Em preparação".

Os prints do manual usam pessoas e dados inventados, nunca de paciente ou de funcionário.

## O Assistente do app

No canto inferior direito da tela fica um robozinho, o Assistente do app, para todo mundo que entra no aplicativo, em qualquer parte dele e também na Administração. O clique no robô abre um painel com as sugestões **Relatar um bug** e **Tirar uma dúvida** e um campo livre para escrever a pergunta do seu jeito.

Ele responde dúvidas de uso: como uma tela funciona, onde fica um botão, como fazer uma tarefa. Para responder, lê as páginas do manual das partes do aplicativo que a pessoa já usa (as mesmas que ela vê no Manual) e este material da Vitta, e diz de onde tirou a resposta. Se o material não responde, ele avisa que não sabe. Ele não lê o código do aplicativo e não muda nada nele.

A dúvida não vira pedido para a Vitta: a conversa fica só no painel e some quando a página é recarregada. O Manual continua no canto inferior esquerdo, como antes.

Em **Relatar um bug**, o robô faz cinco perguntas, uma por vez: onde aconteceu, o que aconteceu, o que você esperava, como fazer o problema acontecer de novo e, se você tiver, o print da tela. Dá para pular qualquer uma, e o que você não respondeu aparece como "não informado". O print fica guardado no aplicativo, junto do pedido, e nunca vai para o GitHub. No fim, o robô mostra o resumo do que você disse, e o bug só vai para a Vitta quando você clica em **Enviar à Vitta**. Até lá, ele fica guardado no aplicativo como um pedido Registrado. O bug de quem é Super admin entra direto na fila da Vitta; o das outras pessoas passa antes por uma conferência. No Quadro da Tecnologia, ele aparece com o selo **Relato no app**. Se o envio falhar, o robô mostra o motivo e o botão **Tentar de novo**, e nada é reenviado sem esse clique.

## O que já foi decidido

- A aba mora dentro do aplicativo e só quem é Super admin a vê.
- A aba Tecnologia só informa, com o Quadro e as Entregas, e desde 25/11/2026 saíram dela o chat com a IA e o Novo pedido, a Conversa da Demanda, a lista Esperando você, os cartões de Pergunta, Passo a passo e Pedido, o Me explique, o seletor de modelo e os botões Revisar com o código de hoje, Apagar, Envio aos desenvolvedores, Designar de novo e Reenviar, com os pedidos guardados no banco.
- Melhoria nasce do Claude do diretor, que abre o card no GitHub; bug se relata pelo robozinho, o Assistente do app; o que pede ação do diretor chega como card no nome dele no GitHub, com a notificação do próprio GitHub.
- O link de um aviso antigo abre o pedido no Quadro.
- O manual mora dentro do aplicativo, no item Manual do canto inferior esquerdo, com a aba Aplicativo do Hospital para todos e a aba Ana só para Super admin.
- As Entregas mostram o ritmo da semana, os pedidos que chegam e as entregas que saem, e não movem nada.
- O Tamanho da entrega sai do número de partes do pedido (P até 1 parte, M de 2 a 5, G de 6 em diante), calculado pelo aplicativo e nunca estimado.
- O pedido nasce do card que o diretor abre pelo Claude dele, do bug do robozinho ou de um card do aplicativo que a Vitta abre pelo desenvolvimento, que aparece no Quadro com o selo Vitta; os ajustes internos da Vitta não aparecem.
- O card com card de implantação mostra a parte Implantação no documento e o selo "Implantação 1 de 3" no Quadro, contando os cards de implantação fechados no GitHub, e o selo some quando todos estão fechados; o card de implantação não conta como parte, e a entrega fica Em produção mesmo com a implantação por fazer.
- Quem troca o Responsável é a Vitta, no desenvolvimento, e a tela acompanha; o aplicativo não troca o Responsável.
- O Quadro e a lista do celular mostram todos os pedidos, e a Etapa de cada um vem do desenvolvimento, sem ninguém escrever à mão.
- A lista tem busca pelo título e filtros que combinam (Bug ou Melhoria, Etapa, Origem, Projeto, e para o Desenvolvedor também Responsável, Envio falhou e Para mim), e o pedido abre ao lado dela, com o Ampliar para a tela cheia.
- No Quadro, os pedidos que não serão feitos aparecem só com o interruptor da barra, numa coluna no fim, e o histórico completo das entregas fica na aba Entregas.
- O endereço da página aponta para o pedido aberto, e o link de um pedido que não existe ou com endereço errado mostra "Você não tem acesso a esta Demanda", sem título nem número.
- O link de um pedido aberto sem estar no aplicativo pede o login e volta para ele depois do login.
- O Copiar link do documento do pedido copia o número, o título e o link que abre o pedido, para todos que veem o pedido, em qualquer Etapa; o compartilhar do celular fica de fora.
- Todo administrador do aplicativo vê todas as Demandas, com ou sem login do GitHub, com o número e o link do card e o número de cada parte; o login do GitHub no cadastro só dá nome ao Responsável, que pode ser da Vitta ou da diretoria.
- Uma Demanda se liga a um trabalho de desenvolvimento só, e a Etapa é lida de lá, nunca digitada.
- No documento do pedido, as partes aparecem agrupadas por Onda, com o número de cada uma e o "Espera a" enquanto outra parte, ou outro pedido, a trava; a Onda vem das dependências do desenvolvimento, e o Quadro, as Entregas e a lista do celular não mudam.
- O vídeo de demonstração de uma entrega vem do desenvolvimento da Vitta, só por link seguro (https), e aparece no pedido com o selo Tem demonstração e a seção Demonstração.
- O plano de um pedido aparece no card do Quadro com o botão Ver o plano e no documento com o cartão Plano, só quando a Vitta publicou a página do plano; o check no botão diz que o diretor já validou, e validar continua sendo pela página do plano.
- O pedido validado pela página do plano mostra ao lado da Etapa o selo Plano validado em, com a data, que sai quando o plano é publicado de novo; com o Ajuste do plano aberto, o documento mostra a faixa do ajuste e as partes que o esperam dizem Espera o ajuste do plano; o ajuste não conta como parte, e o número dele aparece para todos.
- Quando o pedido entra em produção ou o vídeo de demonstração fica pronto, chega um aviso no sino e por e-mail, uma vez só: para quem pediu, no pedido do diretor, e para a diretoria, no pedido da Vitta.
- O texto que sai da Demanda para o material público do desenvolvimento passa por uma peneira que esconde CPF, telefone, nome e outros dados pessoais.
- Os prints ficam só dentro do aplicativo e são apagados 30 dias depois de Em produção, ou logo quando a entrega fica Não será feita.
- Títulos, botões e abas aparecem em caixa alta só na tela, e o título de cada Demanda aparece como foi escrito.
