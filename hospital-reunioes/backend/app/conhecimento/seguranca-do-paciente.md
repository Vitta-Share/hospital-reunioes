# Segurança do Paciente

Segurança do Paciente é o módulo em que o Núcleo de Segurança do Paciente funciona dentro do aplicativo. Ele nasceu da especificação da Diretoria Executiva e entra em quatro fases: a primeira cuida da constituição do Núcleo (membros, documentos, capacitações, agenda regulatória) e das reuniões; a segunda traz a notificação de incidente, a triagem e os prazos; a terceira, a investigação e o plano de ação; a quarta, a notificação externa, os indicadores, o relatório mensal e o dossiê de inspeção.

O Núcleo continua recebendo os casos da Ouvidoria como hoje. O módulo é outra coisa: é onde o Núcleo trabalha.

Toda Demanda sobre o item Segurança do Paciente do menu, sobre quem vê o quê no módulo ou sobre uma tela do Núcleo pertence a este Produto.

## O que já está no ar

A fundação do módulo:

- o item **Segurança do Paciente** no menu lateral, com a página inicial do módulo, as Reuniões e o grupo Núcleo (Membros, Documentos, Capacitações e Agenda regulatória). Cada tela abre com uma linha dizendo o que fazer ali;
- os itens Auditorias de adesão, Gestão de riscos e Comissões, que aparecem no menu desabilitados, com o selo "Em breve" e uma explicação do que vão fazer;
- o Núcleo criado como o primeiro colegiado do hospital, ainda sem nenhum membro: a composição é cadastrada pela tela;
- a tela **Membros**, com uma linha por membro (papel, área, conselho e registro, vigência, estado e situação do Termo). A Presidência e o Acesso pleno cadastram, editam, renovam a vigência, mudam o papel e encerram a participação. Os demais que abrem a tela só leem;
- o cadastro de pessoas com conselho profissional, número de registro e UF;
- o Acesso pleno ao NSP, marcado no cadastro da pessoa pela área administrativa.

O Termo de Adesão:

- ao cadastrar um membro, o aplicativo gera um documento só, com o Termo de Adesão preenchido (nome, cargo, setor, conselho, número do registro e UF, papel e vigência) e, no fim, o texto inteiro do Regimento vigente. O documento vai por e-mail para a assinatura eletrônica, com um signatário só: o próprio membro. Sem Regimento publicado em Documentos, o cadastro fica feito, o membro fica em Cadastrado e a tela avisa para publicar o Regimento;
- quando o membro assina, ele fica Ativo sozinho, sem ninguém mexer, e o Termo assinado entra em Documentos como o Termo daquele membro e daquela vigência;
- renovar a vigência ou mudar o papel de um membro gera um Termo novo, com a vigência e o papel de agora e o Regimento vigente, e o manda para assinatura. Quem já tinha o Termo assinado continua no estado em que estava até assinar o novo, seguindo as datas da vigência e a carência. Cada Termo assinado entra em Documentos, um por membro e por vigência;
- na seção de cada membro com Termo à espera da assinatura, inclusive o Termo novo de quem já tinha assinado, a Presidência e o Acesso pleno têm três botões: **Reconsultar status da assinatura** (para quando a assinatura foi feita e o aplicativo não ficou sabendo), **Reenviar o Termo** (cancela o link anterior e manda um documento novo, com outro número) e **Liberar sem assinatura** (exige justificativa, que fica registrada com quem liberou e quando). A Diretoria não usa esses botões;
- quem está no Núcleo e ainda não assinou vê, nas telas bloqueadas, a faixa "Assine o Termo de Adesão para liberar este acesso", com o botão que abre o documento pendente.

Os avisos por e-mail:

- todo dia de manhã o aplicativo manda os avisos do Núcleo, um e-mail com o nome de cada pessoa, sem nada do conteúdo do Núcleo. O assunto diz o que fazer e traz a data por extenso, como 16/11/2026;
- Termo de Adesão: quando o documento é gerado, o membro recebe o aviso para assinar. Sem assinatura, ele recebe de novo com 3 e 7 dias, e com 14 dias o aviso vai para ele e para a Presidência. Assinado ou liberado sem assinatura, os avisos param. Reenviar o Termo recomeça a contagem pelo documento novo;
- vigência: 60 e 30 dias antes do fim, o membro e a Presidência recebem o aviso para renovar. Renovada a vigência, os avisos recomeçam pelo fim novo;
- fim da carência sem renovação: a Presidência e a Diretoria Executiva recebem o aviso para recompor o Núcleo;
- cada aviso sai uma vez só para cada pessoa. Se o aplicativo ficou fora do ar uns dias, sai só o aviso mais recente que ficou para trás (o de 7 dias, e não o de 3 e o de 7 juntos). O envio que falha, ou a pessoa sem e-mail no cadastro, fica registrado e não impede os outros avisos do dia;
- participação encerrada não recebe aviso.

A tela Núcleo, Documentos:

- guarda o ato de designação, o Regimento, o Plano de Segurança do Paciente, o Termo, as atas e outros documentos do Núcleo, cada um com as suas versões;
- cada tipo tem uma única versão vigente, marcada na tela. As versões anteriores ficam na lista, embaixo da vigente, e continuam abrindo;
- o texto do Regimento fica guardado no aplicativo e é lido na própria tela, assim como o do Plano quando ele foi publicado com texto. Membro com o Termo assinado, Presidência e Acesso pleno leem;
- quem publica uma versão nova é a Presidência ou o Acesso pleno. A versão publicada passa a ser a vigente e a anterior vai para a lista;
- ao publicar uma revisão do Regimento, a Presidência escolhe se ela é material (muda o conteúdo) ou só de redação, e a escolha fica gravada e aparece na tela;
- publicar uma revisão material do Regimento gera um Termo novo, já com o texto revisado, para todos os membros em Ativo, A vencer e Em carência, e o manda para assinatura. A revisão só de redação não gera Termo nem pede assinatura de ninguém.

As reuniões do Núcleo:

- o item **Reuniões** mostra o calendário das reuniões do Núcleo, mês a mês. Quem tem o Termo assinado clica na reunião e abre a ata; quem ainda não assinou vê a data, o tipo e o título, e não abre;
- a Presidência cria a reunião ali mesmo, à mão, num dos quatro tipos do Núcleo: ordinária mensal, análise de evento, apresentação à Diretoria e reunião rápida de segurança. A ordinária, a de análise de evento e a de apresentação à Diretoria seguem o caminho de sempre: transcrição, revisão e ata;
- a reunião rápida de segurança não tem transcrição, ata nem assinatura, e não conta quórum. Ao escolher esse tipo, a Presidência preenche a data, o setor, quem participou e um texto de até três linhas. A reunião aparece na lista com o tipo marcado e o setor no lugar do título. Quem tem o Termo assinado lê o texto e os participantes ali mesmo, na lista, sem abrir outra tela; quem ainda não assinou vê só a data, o tipo e o setor. Ela também não tem pauta, convocação nem presença;
- a Presidência gera o **calendário do ano** de uma vez: as doze reuniões ordinárias, uma por mês, no dia do mês e na hora que ela escolhe. Dia que cai em fim de semana ou feriado cadastrado vai para o próximo dia útil do mesmo mês. Pedir de novo no mesmo ano não duplica: o mês que já tem ordinária fica como está;
- a **pauta** da ordinária aparece 5 dias úteis antes da reunião, contando os feriados cadastrados, montada pelo aplicativo: as pendências da ordinária anterior, com a situação de hoje de cada uma, e os eventos da Agenda regulatória previstos até um mês depois da reunião. Os blocos de indicadores, casos, planos de ação vencidos e alertas sanitários aparecem como "sem dados nesta fase". Nos outros tipos de reunião, a pauta aparece desde a criação. A Presidência muda, tira e inclui itens e blocos enquanto a reunião está programada; quem tem o Termo assinado lê;
- a Presidência **convoca** em um clique: sai um e-mail nominal para cada membro Ativo, A vencer ou Em carência, com o dia da semana, a data e a hora, e o link para o módulo, sem o conteúdo da pauta. O aplicativo grava quem foi convocado e mostra a lista junto da pauta. A ordinária precisa ser convocada até o 5º dia útil antes da reunião; os outros tipos, até 24 horas antes. Fora desse prazo o aplicativo recusa e diz por quê. Cada reunião é convocada uma vez;
- na reunião programada, a Presidência abre a **Presença** na própria lista e marca cada pessoa como presente, ausente, ausente justificado ou convidado. Convidado é quem não é do Núcleo e foi chamado para a reunião. O botão Presença só aparece para a Presidência e o Acesso pleno: os outros membros não veem a presença na tela;
- o aplicativo calcula o quórum: metade de quem conta para quórum no dia da reunião, arredondada para cima, com a Presidência ou o suplente presente. Conta para quórum quem estava Ativo, A vencer ou Em carência naquele dia. Com cinco membros, são três presentes. Convidado e ausente justificado não somam;
- sem quórum, a Presidência escolhe a nova data e a reunião fica como não instalada, não aceita transcrição nem ata, e a reunião reagendada nasce ligada à original, com o mesmo tipo e título. A situação "Não instalada" aparece na lista do Núcleo e na legenda do calendário;
- a **ata do Núcleo** tem os dez blocos do Regimento: identificação; presenças e quórum; situação das pendências da reunião anterior; indicadores; casos analisados; deliberações; plano de ação; alertas sanitários; próxima reunião; assinaturas. A IA escreve a minuta só quando a Presidência importa a transcrição na tela da reunião, e nenhuma rotina automática chama a IA. A tela da reunião do Núcleo mostra a ata nos dez blocos, no lugar das seções da ata comum, e ainda não gera PDF;
- identificação, presenças e quórum, pendências da reunião anterior e indicadores vêm do aplicativo, e não da transcrição: o que a IA escrever sobre eles é descartado, e a tela marca esses blocos como "do sistema". Indicadores e casos aparecem como "Sem dados nesta fase.". As assinaturas listam os presentes;
- a ata não traz nome de paciente nem de profissional envolvido em caso, nem travessão. Se a minuta trouxer nome de membro fora da lista de presença, o aplicativo pede outra uma vez; se a segunda vier igual, a tela avisa e abre os blocos em branco para a Presidência redigir;
- na reunião de apresentação à Diretoria, a ata é a resumida: os mesmos dez blocos, com no máximo três itens em cada bloco escrito pela IA;
- quem importa a transcrição, revisa e valida a ata do Núcleo é a Presidência, o suplente em exercício (o suplente presente numa reunião em que a Presidência não estava) e o Acesso pleno: só para eles a tela mostra os botões Revisar e Validar a ata. Os outros membros leem a ata e veem "A Presidência revisa e valida esta ata.". Na reunião do Núcleo não aparecem os botões da ata comum (enviar para assinatura, finalizar sem assinatura, pedir correção);
- cada deliberação precisa de responsável e prazo para a ata ser validada. Ao validar, cada deliberação vira uma pendência da reunião, com o responsável e o prazo, e a ata fica marcada como validada. A assinatura dos presentes chega numa próxima entrega;
- a reunião do Núcleo some de todo o resto do aplicativo para quem não é do Núcleo: da lista de reuniões, do calendário geral, das pendências, dos números do painel, do sino e do que o Claude da diretoria consulta. Isso vale também para o super admin.

A Agenda regulatória do Núcleo:

- a lista única das obrigações que se repetem (notificação externa do mês, fechamento mensal, reunião ordinária, avaliações nacionais, avaliação da cultura de segurança, revisão do PSP e do Regimento, vencimento de vigência dos membros, recalibração do agente), cada uma com periodicidade, próxima data, link e quantos dias antes lembrar. A lista nasce com os eventos da especificação e com as datas em branco, para a Presidência marcar;
- a Presidência inclui, edita e desativa os eventos. Quem está no Núcleo, mesmo sem o Termo assinado, e a Diretoria só leem;
- quando a próxima data entra na antecedência, o aplicativo cria uma pendência para a Presidência, uma só por data. O lembrete não sai por e-mail: aparece no cartão do evento, na tela Agenda regulatória, com o número da pendência e o prazo. Ele não entra na tela Pendências, porque é assunto do Núcleo. Se a Presidência muda a data antes de registrar o resultado, o lembrete da data antiga é cancelado e um novo nasce para a data nova;
- depois de cumprir, a Presidência registra o resultado e a data em que fez. O resultado fica no histórico do evento, o lembrete é concluído e a próxima data é calculada pela periodicidade (mensal, anual ou a cada dois anos). Evento avulso fica sem próxima data até alguém marcar.

A tela Núcleo, Capacitações:

- mostra cada capacitação com título, data, carga horária, instrutor, público (membros do Núcleo ou profissionais), os temas tratados e a lista de participantes, com quem já confirmou a presença e quando;
- a Presidência e o Acesso pleno registram a capacitação pelo botão Registrar capacitação, escolhendo os temas tratados e os participantes. Os demais que abrem a tela só leem;
- quem está na lista de uma capacitação vê o botão **Confirmar minha presença** no cartão dela e confirma com um toque. O aplicativo grava a data e a hora. Ninguém confirma pelo outro, nem a Presidência;
- a seção Temas mínimos por membro mostra, para cada membro com participação vigente, quantos temas mínimos já cobriu e quais. Conta só a capacitação com presença confirmada: estar na lista sem confirmar não cobre o tema;
- a lista de temas mínimos fica no fim da tela. A Presidência e o Acesso pleno incluem, renomeiam e desativam os temas. A lista nasce vazia, à espera dos temas que a Diretoria vai mandar. Tema desativado sai da cobertura e da escolha no cadastro, mas continua aparecendo nas capacitações antigas.

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

Nas Capacitações, o profissional de fora do Núcleo que está na lista ainda não abre o módulo, então não confirma a presença por enquanto; a capacitação registrada também não se edita depois de salva. A assinatura de um documento publicado também chega depois. Nas reuniões, a ata própria do Núcleo também chega depois: por enquanto a ata segue o modelo das outras reuniões, e a pauta ainda não traz indicadores, casos, planos vencidos nem alertas, que dependem das próximas fases. A notificação de incidente e a triagem são da segunda fase. As notificações criadas a partir da reunião rápida chegam na segunda fase.

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
- Revisão só de redação do Regimento não pede nova assinatura do Termo de Adesão; revisão material pede, de todos os membros em Ativo, A vencer e Em carência.
- O lembrete de cada obrigação é uma pendência da Presidência no aplicativo, e não um e-mail, criada por uma rotina diária que não usa inteligência artificial.
- A pauta é montada pelo aplicativo, sem inteligência artificial.
- A convocação vai só para quem conta para quórum, os membros Ativo, A vencer e Em carência.
- Os avisos do Termo e da vigência saem por uma rotina diária que não usa inteligência artificial, e cada aviso sai uma vez só.

## O que costuma virar Demanda

- Uma pessoa do Núcleo que não vê o item no menu: costuma ser participação com a vigência vencida ou ainda não cadastrada.
- Pedido para apagar um membro cadastrado por engano: não existe exclusão. A Presidência encerra a participação, que fica no histórico.
- Um diretor que pede para ver um caso: depende da fase e da faixa do caso, e o Acesso pleno é só do Diretor Executivo.
- Pedido para o super admin ler uma ata ou um caso do Núcleo: não é atendido, por decisão da Diretoria.
- Pedido para apagar um documento publicado errado: não existe; a Presidência publica uma versão nova corrigida, que passa a ser a vigente.
- Um membro que não abre a tela Documentos: costuma ser o Termo de Adesão ainda não assinado.
- Um membro que diz ter assinado e continua em Aguardando assinatura: a Presidência usa Reconsultar status da assinatura na seção dele.
- Um membro que não recebeu o e-mail para assinar: costuma ser e-mail errado no cadastro; corrigido o e-mail, a Presidência usa Reenviar o Termo.
- Uma reunião do Núcleo que alguém de fora diz não achar na lista de reuniões: é o sigilo funcionando, e a reunião está no módulo Segurança do Paciente.
- Pedido de ata ou de assinatura de uma reunião rápida de segurança: ela não tem ata. O registro é o texto de três linhas, que aparece na lista de reuniões do módulo.
- Um lembrete da agenda que não apareceu: costuma ser evento sem próxima data, evento desativado ou o Núcleo sem Presidência vigente.
- Um membro que diz não ter recebido a convocação: costuma ser Termo não assinado, vigência vencida ou cadastro sem e-mail.
- Um membro que diz não ter recebido o aviso do Termo ou da vigência: costuma ser cadastro sem e-mail, participação encerrada ou Termo já assinado.
- A Presidência que não consegue convocar a ordinária: passou do 5º dia útil antes da reunião, e o aplicativo diz qual era o último dia.
- Um membro que fez a capacitação e o tema não aparece como coberto: costuma ser que ele não confirmou a presença, ou que o tema foi desativado na lista.
- Pedido para a Presidência confirmar a presença de alguém: não existe; cada participante confirma a própria.
