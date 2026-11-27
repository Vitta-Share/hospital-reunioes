# Passo a passo do Felipe

Texto que o Felipe lê, parte por parte. O Claude mostra um passo por vez e espera o "feito". Cada parte fecha com "Como saber que acabou".

## Por que planejar no seu Mac

Até agora você planejava as ideias na aba Tecnologia do app. Cada pergunta ali custava uns 20 centavos de dólar, porque a IA relia o projeto inteiro a cada mensagem. No Claude Max a assinatura já cobre o uso, então você pode conversar o quanto quiser sem conta extra.

Você também vai ter uma cópia do app rodando no seu Mac, com um banco de dados só seu, cheio de dados inventados. Pode clicar, apagar e testar à vontade: nada do que acontece ali chega ao app do hospital nem aos dados de ninguém. Quando a ideia estiver redonda, o Claude abre um card para o time da Vitta, e eles levam a mudança para o app de verdade.

## Parte 0. Claude Max e Claude Desktop

1. Abra no navegador:
   https://claude.ai/upgrade
2. Escolha o plano Max e pague com o cartão.
3. Baixe o Claude para Mac:
   https://claude.ai/download
4. Abra o arquivo baixado e arraste o Claude para a pasta Aplicativos.
5. Abra o Claude e entre com a mesma conta da assinatura.
6. No Claude, abra a área de código (Code) e escolha uma pasta para começar. Pode ser a pasta Documentos.
7. Cole o texto que o Pedro mandou e aperte Enter.

**Como saber que acabou:** o Claude responde em português e pergunta o que você já tem pronto.

## Parte 1. Conta no GitHub

O GitHub é onde fica o código do app e onde o time recebe os cards com os pedidos.

1. Abra:
   https://github.com/signup
2. Digite o seu e-mail, crie uma senha e escolha um nome de usuário (o login). Algo como `felipe-hsm` serve.
3. Resolva o desafio de "não sou um robô" e digite o código que chega no seu e-mail.
4. Se o GitHub perguntar sobre plano, fique no gratuito (Free).
5. Ligue a verificação em duas etapas. Abra:
   https://github.com/settings/security
   Clique em "Enable two-factor authentication" e siga a tela com o aplicativo autenticador do celular. Guarde os códigos de recuperação num lugar seguro.
6. Mande ao Pedro a mensagem "Conta criada", que o Claude mostra pronta, com o seu login.

**Como saber que acabou:** você entra em https://github.com com o seu login e o Pedro respondeu que liberou.

## Parte 2. Ferramentas

São os programas que deixam o Claude baixar o app e rodar ele no seu Mac. Você só faz dois deles: o resto o Claude instala sozinho.

**Homebrew** (o instalador dos outros programas):

1. Abra o Terminal: aperte Command e espaço, digite "Terminal" e aperte Enter.
2. Cole esta linha e aperte Enter:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. Ele pede a senha do Mac. Digite e aperte Enter. Nada aparece enquanto você digita, é normal.
4. Aperte Enter de novo quando ele pedir para continuar. Leva uns minutos.
5. No fim ele mostra "Next steps" com duas ou três linhas. Cole estas duas, uma de cada vez, e aperte Enter em cada:
   ```
   echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
   ```
   ```
   eval "$(/opt/homebrew/bin/brew shellenv)"
   ```
6. Volte ao Claude e diga "feito". Ele instala o resto: git, GitHub, Node, Python e Supabase.

**Docker Desktop** (o motor que roda o app no seu Mac):

1. Baixe a versão para Mac com chip Apple:
   https://desktop.docker.com/mac/main/arm64/Docker.dmg
2. Abra o arquivo baixado e arraste a baleia para a pasta Aplicativos.
3. Abra o Docker pela pasta Aplicativos. Se o Mac perguntar se quer abrir, clique em Abrir.
4. Aceite os termos. Se pedir a senha do Mac, digite.
5. Ele oferece criar conta ou entrar: clique em "Skip" (pular). Pode pular também o questionário.
6. Espere a baleia ficar parada na barra lá em cima, perto do relógio.

**Como saber que acabou:** o Claude roda a conferência e todos os programas aparecem como OK.

## Parte 3. GitHub conectado e a sua cópia baixada

O Claude vai criar uma cópia do código só sua no GitHub (o nome técnico é "fork") e baixar essa cópia para o seu Mac. É nela que você testa as ideias. O código do time fica intocado: lá você só abre cards e mostra protótipos, e quem decide o que entra é a Vitta.

1. No Terminal, cole e aperte Enter:
   ```
   gh auth login --web --git-protocol https --hostname github.com
   ```
2. Ele mostra um código de 8 letras. Anote e aperte Enter.
3. O navegador abre o GitHub. Entre com o seu login, cole o código e clique em "Authorize".
4. No Terminal aparece "Logged in as" com o seu login. Volte ao Claude e diga "feito".
5. O Claude cria a sua cópia e baixa para a pasta `hospital-reunioes`, na sua pasta pessoal (a da casinha, no Finder).
6. No Claude, abra uma conversa nova na área de código e escolha essa pasta `hospital-reunioes`.
7. Digite `/setup-diretor` e aperte Enter. O Claude continua de onde parou.

Se a sua cópia foi baixada antes de 26/11/2026, ela ainda aponta o endereço antigo do repositório do time. O Claude troca o endereço sozinho quando a conferência acusar, e você não precisa fazer nada.

**Como saber que acabou:** na conversa nova, o Claude roda a conferência e mostra a sua cópia ligada ao seu login e o GitHub conectado.

## Parte 4. A sua cópia do app

Agora o Claude liga o banco de dados e o app no seu Mac. Na primeira vez demora de 10 a 15 minutos, porque ele baixa tudo. Das outras vezes leva menos de um minuto.

1. Confira se a baleia do Docker está parada lá em cima. Se não estiver, abra o Docker.
2. Diga "pode subir" ao Claude e espere. Ele avisa quando terminar.
3. Abra no navegador:
   http://localhost:3000
4. Entre com o usuário de teste:
   e-mail: admin@hospital.com
   senha: Admin@123!
   Esse usuário só existe no seu Mac.
5. O app abre vazio, com o menu à esquerda. Os dados de teste o Claude cria quando a ideia precisar, sempre com nomes inventados.

**Como saber que acabou:** você vê o app do hospital no seu navegador, com o endereço `localhost:3000` lá em cima, e conta ao Claude.

## Parte 5. O Claude do jeito do time

O Claude instala os complementos que o time usa. Um deles tira print das telas do seu app para pôr nos cards.

Ele também grava uma trava nas configurações dele: o seu Claude fica proibido de juntar qualquer mudança ao código do app (o nome técnico é "merge"). Quem junta é sempre a Vitta, depois de revisar e testar.

1. Diga "pode instalar" e espere.
2. Quando ele pedir, feche o Claude (Command e Q) e abra de novo.
3. Volte à conversa na pasta `hospital-reunioes` e digite `/setup-diretor`.

**Como saber que acabou:** a conferência mostra tudo OK, inclusive a linha "trava do merge".

## Parte 6. O convite do time

O Pedro convida você para dois lugares no GitHub. O primeiro é o repositório do app: com ele você recebe cards no seu nome, responde, devolve e fecha os que terminar. O segundo é o `hospital-arquivos`, uma pasta privada que só você e os sócios da Vitta veem, onde ficam os seus arquivos de apoio (Parte 10).

Mesmo convidado, você não junta mudança ao app. No repositório do app você entra com o papel Triage: mexe nos cards, nas etiquetas e em quem cuida de cada um, e o GitHub não deixa você mudar o código nem juntar mudança. A trava do seu Claude (Parte 5) e a regra que reprova o seu pedido de mudança até alguém da Vitta assumir continuam valendo, como segunda proteção.

1. Diga "aceita os convites" ao Claude. Ele aceita os dois pelo GitHub e confere.
2. Se ele disser que não achou convite, mande ao Pedro a mensagem "Sem convite", que o Claude mostra pronta.
3. Quando o Pedro responder, diga "aceita os convites" de novo.
4. Se a conferência disser que você tem acesso de escrita, mande ao Pedro a mensagem "Acesso de escrita", que o Claude mostra pronta. Ele troca o seu papel para Triage.

**Como saber que acabou:** a conferência mostra "colaborador do time" e "hospital-arquivos" como OK.

## Parte 7. Planejar uma ideia

O time usa comandos que começam com uma barra. Você digita o comando e o Claude conduz. Os que importam para você:

- `/grill-with-docs`: é aqui que toda ideia começa. O Claude faz uma pergunta por vez, sempre com a recomendação dele, e confere a ideia contra o glossário do app e as decisões já tomadas. Serve para a ideia sair sem buraco e com as palavras que o time usa.
- `/prototype`: monta uma versão de teste da tela ou da regra no seu app local, para você ver funcionando antes de pedir. Serve para descobrir o que você quer de verdade antes de o time gastar tempo.
- O card: no fim, o Claude escreve o pedido no formato que o time espera e, com o seu "pode criar", abre no GitHub. Esse card substitui o "Criar o card" da aba Tecnologia.
- `/ask-pedro`: quando não souber qual comando usar, digite isso e pergunte. Ele aponta o caminho.

Dois comandos que você vai ver citados e que são da Vitta, não seus: `/to-prd` e `/to-issues`. Depois do seu card, o Pedro faz a parte técnica (`/grill-with-docs` com o número do card), transforma em plano (`/to-prd`) e divide em tarefas (`/to-issues`). O `/triage` é a triagem que a Vitta faz dos cards que chegam.

Achou um erro no app (um bug)? Relate pelo Assistente do app, o robozinho no canto de baixo, à direita, do app do hospital. Ele faz as perguntas certas e manda o relato para a Vitta. O seu Claude cuida das melhorias.

**Como saber que acabou:** você sabe por onde começar quando tiver uma ideia: abrir o Claude na pasta `hospital-reunioes` e digitar `/grill-with-docs`.

## Parte 8. Prototipar

1. Conte a ideia ao Claude depois do `/grill-with-docs`, ou peça "quero ver isso funcionando".
2. O Claude atualiza a sua cópia com o que o time subiu, monta o protótipo e liga o app de novo.
3. Abra http://localhost:3000 e teste. Diga o que mudar. Repita até ficar do jeito que você quer.
4. O Claude tira os prints e manda o protótipo para a sua cópia no GitHub, com um pedido de revisão em rascunho (o nome técnico é "PR em rascunho") ligado ao card.

O protótipo é o ponto de partida. Quando alguém da Vitta pega, o pedido ganha a etiqueta "assumido", e a pessoa continua de onde você parou, completa e leva ao app. Juntar a mudança ao app é sempre da Vitta.

**Como saber que acabou:** o card tem um comentário com o link do protótipo.

## Parte 9. Abrir o card

1. O Claude mostra o texto do card inteiro.
2. Leia a parte "Para o diretor": é o resumo que você vai acompanhar. Peça mudança se algo não for o que você quis dizer.
3. Diga "pode criar".
4. O Claude cria o card e mostra o link.
5. Mande ao Pedro a mensagem "Card novo", que o Claude mostra pronta.

**Como saber que acabou:** o link abre o card no GitHub com as etiquetas "needs-triage" e "origem:diretor" e o Pedro como responsável.

## Parte 10. Arquivo de apoio

Às vezes a ideia depende de um documento seu: uma especificação, uma planilha, uma memória de cálculo, um PDF. A Vitta precisa ler esse documento na hora de fazer o código. O card é público, então o arquivo não vai nele. Vai para o `hospital-arquivos`, numa pasta com o número do card, e o card leva só o link.

1. Arraste o arquivo para a conversa do Claude, ou diga onde ele está no seu Mac.
2. Diga para qual card ele é. Se o card ainda não existe, o Claude abre primeiro (Parte 9).
3. O Claude guarda o arquivo na pasta do card e comenta no card com o link.

**Como saber que acabou:** o card tem um comentário com o link, e o link abre o seu arquivo no GitHub. Quem não é do time vê uma página de "não encontrado", e é assim mesmo.

## Parte 11. A Tarefa do diretor

Às vezes a Vitta precisa de você no meio do trabalho. Pode ser uma pergunta (o card vem com a etiqueta "needs-info") ou uma coisa a fazer, como testar, configurar ou mandar um arquivo (etiqueta "ready-for-human"). As duas chegam como um card no seu nome, e o GitHub avisa por e-mail. O card de implantação também é uma coisa a fazer: chega depois que a mudança está no app, você combina com quem faz no hospital e fecha quando terminarem.

1. Abra o Claude na pasta `hospital-reunioes` e pergunte "o que está no meu nome?". Ele lista os cards.
2. Escolha um. O Claude explica o que pedem, com as opções e a recomendação de quem pediu.
3. Responda ao Claude. Ele escreve a resposta, mostra para você e, com o seu "pode mandar", comenta no card.
4. Se era pergunta, o Claude devolve o card a quem perguntou.
5. Se era coisa a fazer, diga "terminei" quando acabar. O Claude comenta o que foi feito e fecha o card. O trabalho que esperava por você volta a andar sozinho.
6. Se a tarefa pede um arquivo, ele vai pela Parte 10, e o comentário leva o link.

**Como saber que acabou:** quando você pergunta "o que está no meu nome?", o card não aparece mais.
