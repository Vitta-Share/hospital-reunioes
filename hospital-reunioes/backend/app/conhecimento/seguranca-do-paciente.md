# Segurança do Paciente

Segurança do Paciente é o módulo em que o Núcleo de Segurança do Paciente funciona dentro do aplicativo. Ele nasceu da especificação da Diretoria Executiva e entra em quatro fases: a primeira cuida da constituição do Núcleo (membros, documentos, capacitações, agenda regulatória) e das reuniões; a segunda traz a notificação de incidente, a triagem e os prazos; a terceira, a investigação e o plano de ação; a quarta, a notificação externa, os indicadores, o relatório mensal e o dossiê de inspeção.

O Núcleo continua recebendo os casos da Ouvidoria como hoje. O módulo é outra coisa: é onde o Núcleo trabalha.

Toda Demanda sobre o item Segurança do Paciente do menu, sobre quem vê o quê no módulo ou sobre uma tela do Núcleo pertence a este Produto.

## O que já está no ar

A fundação do módulo:

- o item **Segurança do Paciente** no menu lateral, com a página inicial do módulo, as Reuniões e o grupo Núcleo (Membros, Documentos, Capacitações e Agenda regulatória). Cada tela abre com uma linha dizendo o que fazer ali; as telas ainda sem conteúdo dizem que ele chega nas próximas entregas;
- os itens Auditorias de adesão, Gestão de riscos e Comissões, que aparecem no menu desabilitados, com o selo "Em breve" e uma explicação do que vão fazer;
- o Núcleo criado como o primeiro colegiado do hospital, ainda sem nenhum membro: a composição é cadastrada pela tela;
- a tela **Membros**, com uma linha por membro (papel, área, conselho e registro, vigência, estado e situação do Termo). A Presidência e o Acesso pleno cadastram, editam, renovam a vigência, mudam o papel e encerram a participação. Os demais que abrem a tela só leem;
- o cadastro de pessoas com conselho profissional, número de registro e UF;
- o Acesso pleno ao NSP, marcado no cadastro da pessoa pela área administrativa.

A tela Núcleo, Documentos:

- guarda o ato de designação, o Regimento, o Plano de Segurança do Paciente, o Termo, as atas e outros documentos do Núcleo, cada um com as suas versões;
- cada tipo tem uma única versão vigente, marcada na tela. As versões anteriores ficam na lista, embaixo da vigente, e continuam abrindo;
- o texto do Regimento fica guardado no aplicativo e é lido na própria tela, assim como o do Plano quando ele foi publicado com texto. Membro com o Termo assinado, Presidência e Acesso pleno leem;
- quem publica uma versão nova é a Presidência ou o Acesso pleno. A versão publicada passa a ser a vigente e a anterior vai para a lista;
- ao publicar uma revisão do Regimento, a Presidência escolhe se ela é material (muda o conteúdo) ou só de redação, e a escolha fica gravada e aparece na tela;
- publicar ainda não manda nada para assinatura nem gera Termo novo: isso chega nas entregas de assinatura.

As reuniões do Núcleo:

- o item **Reuniões** mostra o calendário das reuniões do Núcleo, mês a mês. Quem tem o Termo assinado clica na reunião e abre a ata; quem ainda não assinou vê a data, o tipo e o título, e não abre;
- a Presidência cria a reunião ali mesmo, à mão, num dos quatro tipos do Núcleo: ordinária mensal, análise de evento, apresentação à Diretoria e reunião rápida de segurança. Depois disso a reunião segue o caminho de sempre: transcrição, revisão e ata;
- a reunião do Núcleo some de todo o resto do aplicativo para quem não é do Núcleo: da lista de reuniões, do calendário geral, das pendências, dos números do painel, do sino e do que o Claude da diretoria consulta. Isso vale também para o super admin.

A Agenda regulatória do Núcleo:

- a lista única das obrigações que se repetem (notificação externa do mês, fechamento mensal, reunião ordinária, avaliações nacionais, avaliação da cultura de segurança, revisão do PSP e do Regimento, vencimento de vigência dos membros, recalibração do agente), cada uma com periodicidade, próxima data, link e quantos dias antes lembrar. A lista nasce com os eventos da especificação e com as datas em branco, para a Presidência marcar;
- a Presidência inclui, edita e desativa os eventos. Quem está no Núcleo, mesmo sem o Termo assinado, e a Diretoria só leem;
- quando a próxima data entra na antecedência, o aplicativo cria uma pendência para a Presidência, uma só por data. O lembrete não sai por e-mail: aparece no cartão do evento, na tela Agenda regulatória, com o número da pendência e o prazo. Ele não entra na tela Pendências, porque é assunto do Núcleo. Se a Presidência muda a data antes de registrar o resultado, o lembrete da data antiga é cancelado e um novo nasce para a data nova;
- depois de cumprir, a Presidência registra o resultado e a data em que fez. O resultado fica no histórico do evento, o lembrete é concluído e a próxima data é calculada pela periodicidade (mensal, anual ou a cada dois anos). Evento avulso fica sem próxima data até alguém marcar.

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

## Membros e estados

O estado de cada membro é calculado pelas datas e pela assinatura, e ninguém o edita à mão:

- **Cadastrado**: a participação existe e o Termo ainda não foi gerado;
- **Documento gerado** e **Aguardando assinatura**: o Termo saiu e espera a assinatura;
- **Ativo**: Termo assinado e vigência em dia;
- **A vencer**: faltam 60 dias ou menos para o fim da vigência;
- **Em carência**: até 30 dias depois do fim da vigência, para dar tempo de renovar;
- **Vencido**: passou a carência;
- **Encerrado**: a Presidência encerrou a participação.

Membro nunca é apagado. Encerrar termina a vigência no dia escolhido e a participação vai para o histórico, recolhido no fim da tela. Escolhendo uma data, a tela mostra quem compunha o Núcleo naquele dia, inclusive quem já saiu. Toda mudança (cadastro, edição, renovação, mudança de papel, encerramento) fica registrada com quem fez, quando, o valor anterior e o novo, e aparece na seção de cada membro. Uma pessoa tem uma participação aberta por vez: para voltar depois de encerrada, ela é cadastrada de novo.

## O que ele ainda não faz

A tela de Capacitações ainda está vazia: as capacitações chegam nas próximas entregas da primeira fase. Em Membros, o cadastro ainda não gera o Termo de Adesão nem manda para assinatura, então todo membro novo fica em Cadastrado até a entrega do Termo. Renovar a vigência ou mudar o papel também não pede Termo novo por enquanto. A assinatura de um documento publicado também chega depois. Nas reuniões, a pauta montada pelo sistema, o convite aos membros e a ata própria do Núcleo também chegam depois: por enquanto a Presidência cria a reunião à mão e a ata segue o modelo das outras reuniões. A notificação de incidente e a triagem são da segunda fase.

## O que já foi decidido

- O super admin do aplicativo não abre conteúdo do Núcleo e só chega à configuração técnica.
- Quem vê tudo é o Acesso pleno ao NSP, uma permissão dada pelo nome ao Diretor Executivo.
- A proteção é do aplicativo, e a Diretoria sabe que quem opera o banco de dados diretamente consegue ler.
- Presidência, suplente e membro vêm da participação vigente no Núcleo, com início e fim, e não de um perfil marcado à mão.
- Quem está no Núcleo sem o Termo de Adesão assinado vê só painel, calendário e agenda, até assinar.
- A reunião do Núcleo é vista por quem é do Núcleo, e não por quem foi incluído na lista de participantes: quem é de fora não a vê nem estando na lista, e o membro a vê mesmo sem estar.
- A reunião do Núcleo não aparece em nenhuma tela de quem é de fora, inclusive do super admin.
- Os dados dos membros não entram no aplicativo por carga automática: a composição é cadastrada pela tela, depois da entrega.
- Auditorias de adesão, Gestão de riscos e Comissões ficam no menu com o selo "Em breve", desabilitados, para quem usa já saber o que vem.
- Os títulos das telas do módulo ficam em caixa alta, na identidade do hospital.
- Nenhum documento do Núcleo é apagado nem editado: a correção é uma versão nova, e a anterior fica na lista com quem publicou e quando.
- O texto do Regimento entra pela tela, nunca por carga automática.
- Revisão só de redação do Regimento não pede nova assinatura do Termo de Adesão; revisão material pede, quando as entregas de assinatura chegarem.
- O lembrete de cada obrigação é uma pendência da Presidência no aplicativo, e não um e-mail, criada por uma rotina diária que não usa inteligência artificial.

## O que costuma virar Demanda

- Uma pessoa do Núcleo que não vê o item no menu: costuma ser participação com a vigência vencida ou ainda não cadastrada.
- Pedido para apagar um membro cadastrado por engano: não existe exclusão. A Presidência encerra a participação, que fica no histórico.
- Um diretor que pede para ver um caso: depende da fase e da faixa do caso, e o Acesso pleno é só do Diretor Executivo.
- Pedido para o super admin ler uma ata ou um caso do Núcleo: não é atendido, por decisão da Diretoria.
- Pedido para apagar um documento publicado errado: não existe; a Presidência publica uma versão nova corrigida, que passa a ser a vigente.
- Um membro que não abre a tela Documentos: costuma ser o Termo de Adesão ainda não assinado.
- Uma reunião do Núcleo que alguém de fora diz não achar na lista de reuniões: é o sigilo funcionando, e a reunião está no módulo Segurança do Paciente.
- Um lembrete da agenda que não apareceu: costuma ser evento sem próxima data, evento desativado ou o Núcleo sem Presidência vigente.
