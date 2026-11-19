# Reuniões

O módulo de Reuniões é o que o aplicativo faz desde o começo: transforma uma reunião em ata, e a ata em tarefas com dono e prazo. É onde a diretoria registra o que foi decidido e acompanha o que ficou combinado.

Quem conduz uma reunião e responde pela ata é o facilitador, e é ele quem entra no aplicativo. Quem só foi citado numa reunião, ou ficou responsável por alguma coisa, não entra: recebe e-mail e links diretos para o que é dele.

## Os dois jeitos de montar a ata

**Por transcrição.** O facilitador traz o texto da reunião e a inteligência artificial monta a ata: tópicos, decisões e ações. Essa ata vira PDF e pode ir para assinatura digital.

**Ata guiada.** Para a reunião operacional que não teve transcrição, o facilitador monta a ata conversando numa tela própria, por escrito ou por voz: de um lado o chat, do outro a ata tomando forma, já com o visual da ata final. O agente pergunta o que falta, principalmente quem faz e até quando, e o facilitador pode apontar uma seção e corrigi-la pela conversa. Essa ata não gera PDF e não vai para assinatura.

Uma reunião tem no máximo uma ata, por um dos dois caminhos.

## Quem faz o quê, e até quando

Os nomes citados na reunião são casados com o cadastro de pessoas do hospital. Quem está no cadastro vira responsável de verdade e passa a ser cobrado; quem é de fora fica só como nome, sem cobrança. Quando o agente não tem certeza de quem é, ele pergunta.

Cada ação combinada vira uma pendência, com responsável e prazo, e desde o primeiro segundo ela é cobrada de verdade: aparece no painel, vence e atrasa. Prazo estourado vira atrasado, e o caminho normal é repactuar: a mesma pendência fica sem prazo, marcada como a repactuar, até alguém marcar a data nova.

## Assinar ou finalizar sem assinar

Depois de revisar a ata, o facilitador escolhe um de dois caminhos, e os dois são definitivos:

- **Enviar para assinatura.** A ata vira PDF e segue para assinatura digital, na ClickSign, que é quem manda o e-mail para cada pessoa assinar. As pendências vão nascendo conforme as pessoas assinam.
- **Finalizar sem assinatura.** As pendências nascem na hora e a ata fica aprovada, sem passar pela assinatura.

Não existe "assinar depois": escolhido o caminho, ele vale.

Quando a assinatura não se completa (alguém recusa, ou o processo é cancelado), quem faltava e ficou com alguma ação recebe um e-mail com link, lê a ata inteira e clica em "li e aceito". Esse aceite vale como o "assinou" dele e faz nascer as pendências dele, mas não é assinatura digital: a formalidade continua sendo só do caminho da assinatura.

A coleta de assinaturas também tem prazo: são 30 dias. Vencido o prazo, a ata é finalizada com as assinaturas que tiver, a tela mostra quantos de quantos assinaram, e as pendências que faltavam nascem nesse momento.

## As reuniões do Núcleo de Segurança do Paciente

As reuniões do Núcleo de Segurança do Paciente ficam no módulo Segurança do Paciente, no item Reuniões, e não são marcadas pela tela de Reuniões. São de quatro tipos: ordinária mensal, análise de evento, apresentação à Diretoria e reunião rápida de segurança. Depois de criada, a reunião do Núcleo segue o mesmo caminho das outras até a ata. A reunião rápida de segurança é só um registro de três linhas, sem transcrição nem ata.

Só quem é do Núcleo vê essas reuniões. Para quem é de fora, elas não aparecem na lista de reuniões, no calendário, nas pendências, nos números do painel, no sino nem no que o Claude da diretoria consulta. Isso vale também para quem administra o aplicativo.

## O Início

O Início é a tela de cada pessoa, com o que ela tem para entregar. É o primeiro item do menu para todos, menos a Secretária, que continua com a tela dela e não vê pendência. Depois de entrar com a senha, todo mundo cai no Início, inclusive quem só usa Ouvidoria, POPs, o Núcleo ou Contas médicas; quem chegou ao login por um link (o de um caso da Ouvidoria, por exemplo) volta para esse link. A Secretária cai na tela de agendamento dela, e abrir o endereço do Início a leva de volta para lá. O logo do menu também leva ao Início. A antiga capa do aplicativo, com dois botões, não existe mais: o endereço principal leva ao Início quem já entrou e ao login quem não entrou. O painel de Reuniões continua no menu, no mesmo endereço.

No topo, uma frase escrita pelo próprio aplicativo, a partir dos números e sem inteligência artificial, diz quantos prazos venceram e há quantos dias o mais antigo espera. Quem não tem nada vencido lê que está em dia e qual é o próximo prazo. Enquanto houver prazo vencido, o topo fica numa faixa azul-marinho escura, e o vermelho aparece só no texto.

Nada na tela pisca. O título da aba do navegador mostra o número de prazos vencidos, e só "Início" quando não há nenhum. Os prazos vencidos entram uma vez, quando a tela abre; para quem pediu ao sistema menos movimento, nada se move. Os três números do topo levam à parte correspondente da lista. Ao passar o mouse numa linha, ou chegar nela pelo teclado, a linha ganha um fundo suave, o botão fica preenchido e aparece uma linha com o andamento e o dia em que o item abriu; no celular essa linha fica sempre à vista. No celular a tela fica em uma coluna, e o Início é o primeiro item da barra de baixo. Com leitor de tela, a frase do topo é anunciada quando chega e cada botão diz o que abre.

Embaixo vem a lista, do prazo mais vencido para o mais distante, em três partes: passou do prazo, vence em até 48 horas e próximos 7 dias. O prazo de um dia só vence quando esse dia acaba, no horário de Brasília. O atraso é contado pela data: uma pendência aberta com o prazo vencido está atrasada mesmo antes de o aplicativo marcá-la como atrasada.

Nesta primeira versão a lista traz as pendências abertas em que a pessoa é responsável ou divide a responsabilidade, inclusive o lembrete da Agenda regulatória do Núcleo, que antes não aparecia na lista de ninguém. Cada linha mostra os dias de atraso ou a data, de onde a pendência veio e um botão: a pendência de reunião abre no quadro de pendências já destacada, e o lembrete do Núcleo abre a Agenda regulatória. Se uma parte da tela não carregar, ela mostra um aviso só daquela parte e o resto continua. O caso da Ouvidoria que espera a resposta do setor também aparece, para o titular, o substituto e o gestor do setor, e quem tem o perfil da Ouvidoria vê uma linha à parte com o tamanho da fila (o texto do módulo Ouvidoria explica). POPs, o Núcleo e Contas médicas entram no Início nas próximas etapas.

Além das pendências, a ata que falta assinar aparece no Início de cada signatário, num grupo sem prazo, no fim da lista, com há quantos dias ela espera. O botão abre a reunião, e a ata sai da lista assim que a pessoa assina ou dá o "li e aceito". A ata em validação aparece só para o facilitador da reunião: até o terceiro dia ela fica no grupo sem prazo, e a partir do quarto dia, como prazo vencido, passa para "passou do prazo". O que está sem prazo não entra na conta da frase do topo. Ao lado da lista fica o trilho, com as próximas reuniões da pessoa, como facilitador ou participante, com dia, hora e o link para a reunião, e a reunião cancelada não aparece. As reuniões do Núcleo só aparecem, na lista e no trilho, para quem o Núcleo deixa ver.

## O que ele não faz

- Não grava a reunião: o aplicativo não capta o que se fala na sala. O áudio que ele recebe é o ditado, quando o facilitador prefere falar a digitar na ata guiada: esse áudio sobe, é transcrito ali mesmo e descartado. Áudio nenhum fica guardado.
- Não gera PDF da ata guiada, e não a manda para assinatura.
- Não desfaz uma ata finalizada pelo caminho normal: quem administra o aplicativo consegue apagar ou corrigir uma ata já finalizada, com motivo obrigatório e registro de quem fez, e isso é exceção pedida caso a caso, não botão de uso corrente.

## O que já foi decidido

- Uma reunião tem no máximo uma ata, feita por transcrição ou pela ata guiada.
- A ata guiada não gera PDF e não vai para assinatura.
- Depois de revisar a ata, o facilitador escolhe entre enviar para assinatura e finalizar sem assinatura, e a escolha é definitiva.
- No caminho da assinatura, a pendência de cada pessoa nasce quando ela assina, ou quando dá o "li e aceito" pelo link, sem esperar as outras.
- A coleta de assinaturas dura até 30 dias, e depois disso a ata fecha com as assinaturas que tiver.
- A inteligência artificial pergunta quando não tem certeza de quem é o responsável, e quem liga a ação a uma pessoa do cadastro é o aplicativo.
- Quem é de fora do cadastro fica na ata só como nome, sem cobrança.
- A lista de participantes da ata é proposta pela inteligência artificial uma vez só, e daí em diante só o facilitador mexe nela.
- O aplicativo não grava a reunião, e o áudio do ditado é descartado assim que vira texto.
- As notas avulsas e a importação de atas antigas foram retiradas do aplicativo.
- O papel interno de cada facilitador é uma etiqueta da administração, e a própria pessoa não vê o dela.
- Os títulos e subtítulos do PDF da ata saem em caixa alta, inclusive os tópicos escritos pela inteligência artificial, e o resto do texto continua com maiúscula e minúscula.
- As reuniões do Núcleo de Segurança do Paciente ficam no módulo Segurança do Paciente e não aparecem para quem não é do Núcleo, nem para quem administra o aplicativo.

## O que costuma virar Demanda

- Ata saindo com erro de conteúdo, ou perdendo uma decisão que foi tomada (Defeito).
- Nome citado que casou com a pessoa errada, ou não casou com ninguém (Defeito).
- Campo novo na ata, ou mudança no texto do e-mail de cobrança (Ajuste).
- Mudança em quem assina, ou na ordem das assinaturas (Decisão).
