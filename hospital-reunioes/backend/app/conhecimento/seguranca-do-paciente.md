# Segurança do Paciente

Segurança do Paciente é o módulo em que o Núcleo de Segurança do Paciente funciona dentro do aplicativo. Ele nasceu da especificação da Diretoria Executiva e entra em quatro fases: a primeira cuida da constituição do Núcleo (membros, documentos, capacitações, agenda regulatória) e das reuniões; a segunda traz a notificação de incidente, a triagem e os prazos; a terceira, a investigação e o plano de ação; a quarta, a notificação externa, os indicadores, o relatório mensal e o dossiê de inspeção.

O Núcleo continua recebendo os casos da Ouvidoria como hoje. O módulo é outra coisa: é onde o Núcleo trabalha.

Toda Demanda sobre o item Segurança do Paciente do menu, sobre quem vê o quê no módulo ou sobre uma tela do Núcleo pertence a este Produto.

## O que já está no ar

A fundação do módulo:

- o item **Segurança do Paciente** no menu lateral, com a página inicial do módulo, as Reuniões e o grupo Núcleo (Membros, Documentos, Capacitações e Agenda regulatória). Cada tela abre com uma linha dizendo o que fazer ali; as telas ainda sem conteúdo dizem que ele chega nas próximas entregas;
- os itens Auditorias de adesão, Gestão de riscos e Comissões, que aparecem no menu desabilitados, com o selo "Em breve" e uma explicação do que vão fazer;
- o Núcleo criado como o primeiro colegiado do hospital, ainda sem nenhum membro: a composição é cadastrada pela tela;
- o cadastro de pessoas com conselho profissional, número de registro e UF;
- o Acesso pleno ao NSP, marcado no cadastro da pessoa pela área administrativa.

## Quem vê

O item Segurança do Paciente aparece para quem tem participação vigente no Núcleo, para quem tem o Acesso pleno ao NSP e para a Diretoria. Os demais não veem o item.

Dentro do módulo, cada pessoa vê conforme o papel:

- **Acesso pleno ao NSP**: tudo, inclusive a configuração. É do Diretor Executivo;
- **Presidência do Núcleo**, com o Termo de Adesão assinado: tudo do módulo;
- **Membro do Núcleo** (ou suplente), com o Termo assinado: painel, calendário, agenda, membros, documentos, capacitações, reuniões e casos, sem a identidade de quem notificou;
- **quem está no Núcleo e ainda não assinou o Termo**: só painel, calendário e agenda;
- **Diretoria**: painel, calendário, agenda e a composição do Núcleo;
- **super admin do aplicativo**: só a configuração técnica do módulo, sem nenhum conteúdo.

Participação vencida, ou que ainda não começou, não dá acesso.

## O que ele ainda não faz

Nesta primeira entrega as telas de Membros, Documentos, Capacitações, Agenda regulatória e Reuniões estão vazias: o cadastro de membros com o Termo, os documentos com versões, as capacitações, a agenda e as reuniões do Núcleo chegam nas próximas entregas da primeira fase. A notificação de incidente e a triagem são da segunda fase.

## O que já foi decidido

- O super admin do aplicativo não abre conteúdo do Núcleo e só chega à configuração técnica.
- Quem vê tudo é o Acesso pleno ao NSP, uma permissão dada pelo nome ao Diretor Executivo.
- A proteção é do aplicativo, e a Diretoria sabe que quem opera o banco de dados diretamente consegue ler.
- Presidência, suplente e membro vêm da participação vigente no Núcleo, com início e fim, e não de um perfil marcado à mão.
- Quem está no Núcleo sem o Termo de Adesão assinado vê só painel, calendário e agenda, até assinar.
- Os dados dos membros não entram no aplicativo por carga automática: a composição é cadastrada pela tela, depois da entrega.
- Auditorias de adesão, Gestão de riscos e Comissões ficam no menu com o selo "Em breve", desabilitados, para quem usa já saber o que vem.
- Os títulos das telas do módulo ficam em caixa alta, na identidade do hospital.

## O que costuma virar Demanda

- Uma pessoa do Núcleo que não vê o item no menu: costuma ser participação com a vigência vencida ou ainda não cadastrada.
- Um diretor que pede para ver um caso: depende da fase e da faixa do caso, e o Acesso pleno é só do Diretor Executivo.
- Pedido para o super admin ler uma ata ou um caso do Núcleo: não é atendido, por decisão da Diretoria.
