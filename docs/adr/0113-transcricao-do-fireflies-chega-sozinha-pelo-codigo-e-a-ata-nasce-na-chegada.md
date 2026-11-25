---
status: proposed
---

# A Transcrição do Fireflies chega sozinha pelo Código da gravação, e a Ata nasce na chegada

Decisão do diretor no grill de 25/11/2026 (três rodadas), sobre a integração com o Fireflies em Reuniões e no Núcleo de Segurança do Paciente. Fica `proposed` até o grill técnico do Pedro. Aceita, ela emenda a decisão 1 da ADR 0082, e o par `amends`/`amended_by` entra nas duas.

## Decisões

1. **O destino vem só do Código da gravação.** O hospital tem uma conta única no Fireflies, com a senha dividida, por custo. O app não sabe quem gravou, então quem grava digita no título o código da Reunião agendada (letra do módulo e cinco números, o último conferindo os outros). A Transcrição entra sozinha só com código válido, Reunião agendada e a mesma data. O resto vai para a fila Transcrições sem destino, onde o app sugere a Reunião pelo horário e uma pessoa confirma. O app nunca adivinha.

2. **A Ata nasce sozinha quando a Transcrição entra na Reunião (exceção à decisão 1 da ADR 0082).** O gesto humano é encerrar a gravação com o código, ou puxar a Transcrição da fila. Cada gravação gera uma Ata só, então o custo tem teto, e o Facilitador continua revisando a Ata antes de ela sair para assinatura ou gerar Pendências.

3. **O Fireflies é só passagem.** O app apaga a gravação e a transcrição no Fireflies assim que guarda o texto, porque na conta única todo mundo que tem a senha ouve tudo. A exclusão automática do próprio Fireflies é do plano Enterprise e tem prazo mínimo de uma semana. A Transcrição parada na fila apaga com 15 dias, com aviso aos Facilitadores no sétimo.

4. **O Comitê de Conduta fica para um segundo card, com ADR própria.** Ele tem dois destinos (depoimento e reunião do Comitê), conteúdo cifrado e três regras da ADR 0097 em jogo: o protocolo aleatório, o arquivo que não sai por link e a transcrição crua que não vai ao fornecedor. Premissa do diretor para esse card: o app busca o áudio do depoimento no Fireflies e o guarda cifrado no módulo.

## Alternativas consideradas

- **Uma conta do Fireflies por Facilitador**: rejeitada pelo custo das licenças. Daria o dono de cada gravação e separaria o que cada um vê.
- **O Facilitador toca em "Gerar Ata" depois que a Transcrição chega**: rejeitada. Somaria um passo sem proteger de nada que a revisão da Ata já não proteja.
- **Apagar no Fireflies só quando a Ata chega ao fim**: rejeitada. Daria para ouvir de novo na revisão, ao preço de deixar o áudio exposto na conta única por dias.
- **Ligar pela data e hora, sem código**: rejeitada como regra, mantida como sugestão na fila. Duas reuniões no mesmo horário cairiam uma na outra.
- **Falar o código no começo da gravação**: fora da primeira entrega. A transcrição de número falado erra com frequência.

## Consequências

- O código é dado novo da Reunião, e a fila é uma tabela nova: a entrega tem migration.
- Um código digitado errado que acerte o dígito de conferência e caia numa Reunião agendada no mesmo dia leva a Transcrição para a Reunião errada. A conferência e a data tornam isso raro, não impossível.
- Se apagar no Fireflies pela API não apagar o áudio, a decisão 3 não se cumpre: a confirmação com o Fireflies vem antes de a entrega subir.
- O anexo manual da Transcrição continua, como rede de segurança.
