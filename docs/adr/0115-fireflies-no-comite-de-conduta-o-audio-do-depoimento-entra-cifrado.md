---
status: proposed
---

# Fireflies no Comitê de Conduta: o áudio do depoimento entra cifrado vindo do Fireflies, pela conta única

Decisão do diretor no grill de 25/11/2026 (três rodadas), sobre o segundo card da integração com o Fireflies, o do Comitê de Conduta. A ADR 0114 deixou o Comitê para cá (decisão 4). Fica `proposed` até o grill técnico do Pedro. Aceita, ela emenda a decisão 2 da ADR 0097 e a decisão 4 da ADR 0114, e os pares `amends`/`amended_by` entram nas três. Premissa do diretor, que veio do primeiro grill: o app busca o áudio do depoimento direto no Fireflies e o guarda cifrado no módulo, para quem abre o caso.

## Decisões

1. **O Comitê usa a conta única do Fireflies do hospital.** Por custo, não há conta separada. Quem tem a senha alcança a gravação de um depoimento entre o fim da gravação e a hora em que o app apaga, alguns minutos. O diretor aceitou esse intervalo, inclusive na Rota Especial, em que o caso pode envolver quem tem a senha. Duas regras diminuem o que fica à vista: o título leva só o código, e a senha não vai para quem é de fora do Comitê (decisão 9).

2. **Cada depoimento e cada reunião do Comitê ganham o próprio Código da gravação, que convive com o protocolo aleatório (ADR 0097, decisão 8).** É a letra C e cinco números, sorteado, com o último conferindo os outros, como nas Reuniões, e sem nenhuma relação com o protocolo do caso. Ele não conta casos nem depoimentos. O código do depoimento vale até "CONCLUIR DEPOIMENTO", e o da reunião até "CONCLUIR REUNIÃO": cada gravação com ele entra como mais um arquivo. Ele aparece só no cartão do depoimento e na tela da reunião, com botão de copiar, para quem abre o caso, e nunca vai por e-mail.

3. **O áudio do depoimento entra no app vindo do Fireflies (emenda a decisão 2 da ADR 0097).** Quando a gravação com o código chega, o app busca o áudio e a transcrição, guarda os dois cifrados no cartão do depoimento e apaga a gravação no Fireflies. O sentido é sempre do Fireflies para o app: nenhum arquivo do caso sai do app por link, e o app nunca manda áudio do caso ao Fireflies (o `uploadAudio` fica fora do Comitê).

4. **Da reunião do Comitê entra só o texto.** O áudio da reunião continua sem entrar no app. A transcrição chega sozinha na etapa Voto, o app apaga a gravação no Fireflies e a transcrição continua eliminada ao concluir a reunião.

5. **Nada nasce sozinho no Comitê.** A ata de deliberação depende dos votos registrados e continua no "GERAR ATA" da coordenação. O termo de declaração continua no "REDIGIR TERMO". O Comitê não precisa de exceção à decisão 1 da ADR 0082.

6. **O app marca a declaração da plataforma de gravação.** O item "Apaguei a gravação de áudio da plataforma de gravação", no depoimento e na reunião, passa a ser marcado pelo app, com a hora em que apagou no Fireflies, e entra na trilha do caso. "Apaguei os arquivos do computador e do celular" continua sendo declaração de quem conduziu, porque o aplicativo do Fireflies no celular pode guardar uma cópia no aparelho.

7. **O Fireflies é aceito como passagem no Comitê.** A ADR 0097 recusou mandar a transcrição com nomes à IA porque ela ficaria até 30 dias no fornecedor. O Fireflies recebe a voz e os nomes só até o app apagar. Duas condições antes de ligar: o Pedro confirma que apagar no Fireflies é definitivo e que o plano não usa os dados para treino, e o resumo que o Fireflies manda por e-mail depois de cada gravação fica desligado na conta.

8. **O que chega sem código válido não vai para a fila das Reuniões quando é do Comitê.** Título que começa com C, mas cujo código não casa, vai para a fila Gravações do Comitê sem destino: o app traz texto e áudio, guarda os dois cifrados e apaga no Fireflies. A fila mostra só data, hora e duração, sem o título, e só a vê quem tem depoimento ou reunião do Comitê em aberto num caso que abre. Puxar leva a gravação para um depoimento ou reunião daquele caso. O que ninguém puxa apaga com 15 dias, com aviso no sétimo. A gravação sem código nenhum cai na fila Transcrições sem destino, das Reuniões, e o cartão do depoimento ganha "BUSCAR NA FILA" para quem conduz puxar de lá. Como aquela fila não guarda áudio, o depoimento puxado dela fica com o item do áudio em "Não se aplica", com o motivo "a gravação chegou sem código".

9. **A senha fica com quem já tem.** O apurador designado e o membro da CIPA não recebem a senha da conta única: gravam com um membro do Comitê que tem a senha, ou anexam à mão. O anexo à mão de hoje continua para todos.

10. **A chegada da gravação é uma tarefa em MINHA VEZ.** Quem conduz recebe a linha, o sino e o e-mail de sempre ("Há uma tarefa no Canal de Conduta."), sem dizer o que chegou. A tarefa é abrir os arquivos e marcar "Abri os arquivos na aplicação e estão corretos".

## Alternativas consideradas

- **Conta do Fireflies separada, só do Comitê**: rejeitada pelo custo de uma licença a mais. Tiraria o depoimento da vista de quem tem a senha da conta única, inclusive na Rota Especial, e separaria a fila sem código.
- **Um código por caso**: rejeitada. Títulos iguais ligariam depoimentos do mesmo caso, e o app não saberia de qual depoimento é cada gravação.
- **Código com a letra das Reuniões, para esconder a gravação do Comitê na lista**: rejeitada. Um erro de digitação levaria o depoimento para uma Reunião comum, que gera Ata sozinha e manda o texto à IA sem trocar os nomes.
- **Toda gravação sem código válido na fila das Reuniões**: rejeitada. Um Facilitador poderia puxar um depoimento para a Reunião dele.
- **A fila das Reuniões guardar também o áudio**: rejeitada. O áudio das Reuniões continua sem entrar no app.
- **Senha para o apurador e o membro da CIPA enquanto dura o caso**: rejeitada. Abriria todas as gravações do hospital a quem é de fora do Comitê.
- **A ata de deliberação nascer sozinha na chegada da transcrição**: rejeitada. A ata precisa dos três votos, que podem não estar registrados.
- **Não usar o Fireflies no Comitê**: rejeitada. O tempo do depoimento no fornecedor cai de dias, com a declaração manual, para minutos.

## Consequências

- O risco aceito na decisão 1 continua: na Rota Especial, quem tem a senha da conta única pode ouvir um depoimento antes de o app apagar.
- Um depoimento gravado sem código nenhum ainda pode ser puxado por um Facilitador para a Reunião dele. O "BUSCAR NA FILA" e o aviso no cartão diminuem, não eliminam.
- Desligar o resumo por e-mail do Fireflies vale para a conta toda, então as Reuniões e o Núcleo também ficam sem ele.
- O código do depoimento e da reunião e a fila do Comitê são dados novos: a entrega tem migration.
- O Comitê só liga a integração depois das duas condições da decisão 7, e o canal continua fechado até a abertura (ADR 0097, decisão 11).
