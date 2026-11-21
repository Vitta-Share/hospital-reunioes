# Canal de Conduta

Canal de Conduta é o módulo em que quem trabalha no hospital, com qualquer vínculo, relata conduta grave de forma anônima, e em que o Comitê de Conduta apura o caso até a medida. Ele tem dois lados: o público, sem login, onde a pessoa relata e acompanha pelo protocolo e pelo código, e o do Comitê, onde os casos são lidos e apurados.

Hoje o relato de conduta de colaborador chega pela Ouvidoria, junto das manifestações de pacientes. O Canal separa esses casos, com anonimato real e prova que aguente uma medida disciplinar ou um processo.

Toda Demanda sobre o relato de conduta, sobre o Comitê de Conduta, sobre quem lê um caso ou sobre o sigilo do Canal pertence a este Produto.

## O que já está no ar

A base do sigilo, ainda sem nenhuma tela:

- o Comitê de Conduta criado como o segundo colegiado do hospital, ao lado do Núcleo de Segurança do Paciente, ainda sem nenhum membro. Ele tem o papel de coordenação, além de membro e suplente;
- o conteúdo de cada caso guardado cifrado. Quem abre a base de dados direto vê o relato embaralhado, e não o texto. Ficam legíveis só o que a lista e o prazo precisam: a rota, a etapa, a categoria e as datas;
- o protocolo do caso é sorteado, sem ordem e sem contagem, para não revelar quantos casos existem. A numeração da Ouvidoria continua a mesma;
- o código de acompanhamento é mostrado uma vez só a quem relatou, e o aplicativo guarda apenas uma marca dele, que não permite recuperar o código;
- a lista dos casos e a abertura de um caso, para quem está designado. Cada abertura fica registrada com quem abriu, quando e o quê;
- o canal está fechado: a página pública responde como se não existisse, até a abertura.

## Quem vê

Ninguém vê um caso por ter um cargo. Vê quem está designado naquele caso:

- a coordenação e os membros do Comitê, com a participação em dia e o Termo assinado, veem os casos da fila comum;
- o suplente vê só o caso para o qual foi convocado;
- o apurador, o membro da CIPA e o grupo da Rota Especial veem só o caso que receberam, depois do termo assinado;
- quem é citado no relato como envolvido nunca vê o caso, em nenhum perfil, e quem se declarou impedido perde o acesso àquele caso;
- o super admin e a equipe técnica não abrem conteúdo de caso pelo aplicativo;
- quem está no Comitê e ainda não assinou o Termo não abre caso.

Quem não tem acesso recebe a mesma recusa, exista o caso ou não.

## O sigilo

- Se a chave da cifra não estiver configurada no servidor, o módulo recusa gravar e ler caso, e o resto do aplicativo funciona normalmente. A verificação de saúde do sistema diz se a chave está lá, sem mostrar a chave.
- Se o registro da abertura não puder ser gravado, o caso não abre.
- O registro dos acessos é uma corrente: cada linha carrega a marca da anterior, e nenhuma pode ser alterada nem apagada. Uma linha trocada ou apagada por quem mexer direto na base aparece na conferência.
- O registro de funcionamento do servidor não guarda o endereço de quem usa o Canal.
- Os arquivos do caso ficam numa área própria, cifrados, e só saem pelo aplicativo, depois de conferido o acesso.
- A cifra protege as cópias de segurança e quem consulta a base de dados. Quem opera o servidor ainda alcança a chave, e por isso o canal só abre com o aditivo de sigilo assinado.

## O que ele ainda não faz

O formulário público de relato, a página de acompanhamento, a tela do Comitê, a triagem com o agente, os ritos, os depoimentos, o voto, a ata, o dossiê e o cadastro dos membros chegam nas próximas entregas. Por enquanto ninguém relata pelo Canal: os relatos continuam chegando pela Ouvidoria.

## O que já foi decidido

- O canal só abre quando a primeira fase inteira estiver pronta, com o aditivo de sigilo assinado, o layout aprovado e o teste de anonimato feito por quem não desenvolveu.
- O super admin não lê caso, e o único super admin com papel no Canal só cadastra membros, a pedido do Comitê.
- Os casos de conduta que já estão na Ouvidoria terminam lá; só os novos vão ao Canal.
- O protocolo é sorteado, para não contar os casos nem deixar buraco na fila quando um caso vai para a Rota Especial.
- Nada do Canal guarda o endereço, o aparelho ou a localização de quem relata.

## O que costuma virar Demanda

- Um membro do Comitê que não abre caso: costuma ser o Termo ainda não assinado ou a participação fora da vigência.
- Pedido para o super admin ler um caso: não é atendido, por decisão da Diretoria.
- A página pública que não abre: o canal ainda está fechado.
- Pedido para apagar um registro de acesso: não existe; o registro não se apaga.
