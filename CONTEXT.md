# Hospital Reuniões

Automatiza o ciclo de vida de reuniões corporativas de um hospital de alta complexidade: gravação → transcrição por IA → geração de **Ata** → aprovação (com ou sem assinatura digital) → acompanhamento de **Pendências**. Este arquivo é o glossário do domínio — define o que os termos **são**. Use esta terminologia em issues, testes e propostas; não derive para sinônimos marcados como _Evitar_.

## Pessoas e papéis

**Facilitador**:
Quem conduz uma Reunião e responde pela Ata: marca, revisa, aprova e envia para assinatura. É um vínculo com a Reunião, não um perfil: vê as Pendências das Reuniões que conduziu, além das próprias (ADR 0098). Hoje são 5 (1 diretor + 4 diretoras).
_Evitar_: admin, gestor, usuário.

**Colaborador**:
Pessoa citada numa Reunião e/ou responsável por uma Pendência. Tem conta no app: entra, vê só as Pendências dele e as atualiza com Anotação. Quem nunca entrou recebe no e-mail um link pessoal para fazer o mesmo (ADR 0098).
_Evitar_: funcionário, membro, usuário comum.

**Secretária**:
Perfil que só agenda Reuniões e inclui Participantes, para qualquer Facilitador. Não vê Ata, Pendência, painel nem ranking, e nunca é a Facilitadora. Mantém a fila da Ouvidoria. Não vê [Dados do Atendimento] nem o [Espelho da Global Health] (ADR 0101).
_Evitar_: assistente, operador.

**Super admin**:
Facilitador com permissões irrestritas (inclui ações de _bypass_ usadas em debug). Marcado por `is_super_admin`.

**Role (faixa hierárquica)**:
Etiqueta interna de administração (`diretor`, `gerente`, `coordenador`, `presidente`), derivada do cargo, com poder de permissão quase nulo (a permissão real vive em `access_profile` e `perfil_pop`). **Nunca aparece para o próprio Facilitador**; só o Super admin a vê, no painel de usuários (ADR 0033, risco trabalhista). O texto público de identificação de uma pessoa nas telas é o **cargo**.
_Evitar_: exibir role em tela de usuário final; confundir role com perfil de acesso.

**Participante**:
Vínculo entre um Colaborador e uma **Reunião** específica. É o roster que a IA tenta casar na **Resolução**, para alocar Pendências ao responsável certo: interno vira responsável real (com cobrança), externo fica só como nome. Os nomes vêm detectados da Transcrição.
_Evitar_: convidado, presente.

**Resolução**:
O casamento de um nome citado (na Transcrição ou na conversa de uma Ata Guiada) com um Colaborador do cadastro, para que a Pendência nasça atribuída à pessoa certa. Prioriza o roster de Participantes da Reunião e cai para o cadastro geral; nome que não casa fica como **externo** (só o nome, sem vínculo nem cobrança). Na Ata Guiada acontece **ao vivo**: o agente conversa usando os nomes canônicos do cadastro e pergunta quando há ambiguidade ("qual Lucas?") ou quando não encontra ninguém. A linha cujo responsável é "Todos os participantes" (ou "Todos os presentes") não passa pelo casamento: nasce uma Pendência, ou uma Rotina, para cada Participante da Reunião, e o quadro continua mostrando "Todos os participantes" (issue #2327).
_Evitar_: matching, match, reconhecimento, identificação.

**Signatário**:
Participante que precisa assinar a Ata dentro de um Envelope da ClickSign.
_Evitar_: assinante, signer.

> **Ambiguidade sinalizada — "usuário":** evite o termo cru. Quem age no sistema é o **Facilitador** (conduz a Reunião) ou o **Colaborador** (responde por Pendências), e os dois entram no app. Dizer "usuário" esconde essa distinção, que é central para acesso e notificação.

## Reunião e Ata

**Reunião**:
A entidade central. Nasce PROGRAMADA e caminha por uma máquina de estados até um estado terminal (ASSINADA, APROVADA ou CANCELADA). A partir de AGUARDANDO_VALIDACAO o Facilitador escolhe entre dois caminhos: **enviar para assinatura** (cria o Envelope na ClickSign) ou **finalizar sem assinatura** (vai direto para APROVADA). Estados: `PROGRAMADA → PROCESSANDO → (AGUARDANDO_RESOLUCAO) → AGUARDANDO_VALIDACAO → (CORRIGINDO) → AGUARDANDO_ASSINATURA → ASSINADA`; ramo terminal sem assinatura `AGUARDANDO_VALIDACAO → APROVADA`; ramos `ERRO` e `CANCELADA`.
_Evitar_: encontro, meeting, evento.

**Transcrição**:
O texto bruto da Reunião (colado manualmente ou sincronizado via Fireflies). É a entrada do Pipeline de IA.
_Evitar_: gravação, áudio (o áudio em si não entra no sistema).

**Ata**:
O documento estruturado da Reunião — tópicos, decisões e ações. Tem **dois modos de geração**: **por Transcrição** (o Pipeline de IA extrai a Ata completa a partir do texto da Reunião; vira PDF e pode ser assinada) ou **Guiada** (ver **Ata Guiada**). Uma Reunião tem no máximo **uma** Ata, por um dos dois modos.
_Evitar_: minuta, relatório, documento.

**Ata Guiada**:
A Ata de uma Reunião **sem Transcrição**, montada pelo Facilitador numa **tela dedicada** (a partir de uma Reunião PROGRAMADA) no formato **ata viva**: o `Resumo Executivo` e o `Quadro de Atribuições` tomam forma ao vivo — com o mesmo visual da Ata final — enquanto um **chat lateral** (por texto ou voz) organiza o relato e pergunta as lacunas críticas (sobretudo responsável e prazo de cada ação). Os responsáveis citados passam por **Resolução** ao vivo: o quadro exibe o nome canônico do cadastro e sinaliza quem ficou sem vínculo. O Facilitador pode **apontar uma seção** (⌖) e corrigi-la pela conversa, e anexar opcionalmente um **Documento de apoio** como contexto. Segue o caminho **sem assinatura** (valida → APROVADA, liberando as Pendências); não tem Envelope nem, por ora, PDF. É o modo leve da Ata, para reuniões operacionais que não justificam Transcrição.
_Evitar_: ata lite, ata rápida, registro, nota da reunião.

**Documento de apoio**:
Um arquivo que o Facilitador **opcionalmente** anexa durante a montagem de uma **Ata Guiada** (`.txt`, `.md`, `.pdf` ou `.docx`) para dar ao agente o contexto do que ele já tem escrito (anotações, slides, um rascunho). É **contexto sob demanda**: o agente só o consulta quando o Facilitador pede ("tira as ações do anexo", "resume o documento") e **nunca** despeja seu conteúdo na ata sozinho. É **efêmero** — vive só durante a montagem e não persiste na Reunião.
_Evitar_: fonte, transcrição, anexo da ata, base da ata.

**APROVADA**:
Estado terminal de uma Ata finalizada **sem assinatura digital**. Na validação, o Facilitador escolhe "Finalizar sem assinatura": as Pendências nascem na hora e a Reunião vai direto para APROVADA — sem Envelope, sem ClickSign, sem aguardar assinaturas. É paralela a ASSINADA (que exige a assinatura no ClickSign) e igualmente terminal — sem reversibilidade ("assinar depois" não existe). Serve a reuniões operacionais, onde o valor está em registrar a Ata e disparar as tarefas, não na formalidade da assinatura.
_Evitar_: concluída, fechada, validada.

**Pipeline de IA** (ou **Pipeline**):
A sequência de chamadas LLM que transforma Transcrição em Ata (extrair fala → casar participantes → resumir → estruturar JSON → gerar Ata em português → PDF). A API da Anthropic é o provedor único da IA de texto, no Claude Sonnet 5.5 (issue #1302); sem chave configurada, em desenvolvimento, o Pipeline cai num mock.
_Evitar_: processamento, job de IA.

## Início (a tela de cada pessoa)

**Início**:
A primeira tela de quem entra no app, diferente para cada pessoa. Abre com uma frase sobre a situação dela (quantos prazos venceram e há quanto tempo o mais antigo espera), mostra a [Minha Fila] e, ao lado, as próximas Reuniões e as Rotinas do ciclo. Quem não tem nada vencido lê "Você está em dia", o próximo prazo e o que entregou nos últimos sete dias. A frase é escrita por regra, a partir dos números, sem IA. Cada pessoa vê ali os próprios números dos últimos 90 dias (entregas no prazo e fora). A Secretária não tem Início (ADR 0104).
_Evitar_: dashboard, capa, home, painel pessoal.

**Minha Fila**:
A lista do Início com o que depende de quem está olhando, de todos os módulos numa ordem só, do prazo mais vencido para o mais distante: Pendências próprias, Atas a assinar, Contestações a responder, Rotinas a revisar, Verificações do ciclo, casos da Ouvidoria do setor e o que mais tiver a pessoa como responsável. Cada linha diz de onde veio e leva à tela onde aquilo se resolve; o que é um clique sem Anotação se resolve ali mesmo. Tem três grupos: Passou do prazo, Vence em até 48 horas e Próximos 7 dias. O painel de Reuniões não tem fila própria.
_Evitar_: caixa de entrada, tarefas, uma fila por módulo.

**Fila do papel**:
A fila que é de um papel e não de uma pessoa: a do ouvidor, as contas sem dono, a triagem do Núcleo. No Início aparece como uma linha de resumo por fila, num bloco separado, e não entra na contagem da frase nem na [Minha Fila].
_Evitar_: pôr o item da fila comum na Minha Fila de cada pessoa do papel.

**Quem responde a você**:
O bloco do Início de quem acompanha outras pessoas, com uma linha por pessoa: prazos vencidos agora, itens em aberto, entregas dos últimos 90 dias no prazo e fora, Rotinas do ciclo e último acesso. Clicar na linha abre o que venceu e não foi entregue. Até o organograma chegar, quem aparece segue o vínculo: o Super admin vê todas as pessoas com item, e o Facilitador vê os responsáveis das Reuniões dele.
_Evitar_: liderados e equipe (enquanto não houver organograma), ranking (é outro bloco, no painel de Reuniões, com o hospital inteiro).

**Registro de acesso**:
A marca de que uma pessoa abriu o Início num dia. Uma por pessoa por dia, sem trilha de cliques, guardada por 90 dias. Só aparece em [Quem responde a você], para quem já vê os itens da pessoa.
_Evitar_: log, monitoramento, rastreio; mostrar o acesso a quem não vê os itens da pessoa.

## Pendências

> Os verbetes desta seção descrevem a regra da ADR 0098, que entra no código pelas ondas do PRD #1757. Até cada onda subir, o código segue a ADR 0030.

**Pendência**:
Uma Ação da Ata atribuída a um responsável, com prazo. Tem quatro estados (`PENDENTE`, `EM_PROGRESSO`, `CONCLUIDO`, `CANCELADO`). **Atrasada** e **repactuada** são situações calculadas, não estados: atrasada é a Pendência aberta com prazo vencido, repactuada é a que tem Repactuação no Histórico. Nasce quando o Facilitador envia a Ata para assinatura, todas de uma vez, e desde o primeiro segundo é plena (painel, prazo, cobrança); a assinatura passa a ser ciência da Ata (ADR 0098). No caminho sem assinatura, todas nascem na aprovação (**APROVADA**, ADR 0003). Conclui o responsável ou o Super admin, sem validação. Cancela o Facilitador da Reunião ou o Super admin. Nenhuma Pendência é apagada.
_Evitar_: tarefa, to-do, meta (o diretor chama de meta a Pendência com prazo; no app não existe cadastro de metas), ação (use "ação" só para a linha da Ata que origina a Pendência).

**Repactuação**:
O prazo novo de uma Pendência, marcado com justificativa pelo responsável, pelo Facilitador ou pelo Super admin. Vale na hora, sem aprovação e sem limite de vezes. **Não cria Pendência nova** e não apaga o prazo antigo, que fica no Histórico. Conta como atraso só quando feita depois de o prazo vencer.
_Evitar_: adiamento, remarcação, prorrogação.

**Anotação**:
O texto obrigatório que acompanha toda mudança de uma Pendência (andamento, conclusão, Repactuação, cancelamento, Reabertura). Pode levar uma prova anexada (foto ou PDF), que é opcional.
_Evitar_: comentário, observação, justificativa como termo separado.

**Histórico da Pendência**:
O registro de cada mudança de uma Pendência, com quem fez, quando e a Anotação. Só cresce: ninguém edita nem apaga, nem o Super admin.
_Evitar_: log, auditoria, trilha.

**Reabertura**:
O Facilitador devolve uma Pendência concluída, com Anotação e prazo novo. Pesa na avaliação do responsável, ao lado dos atrasos.
_Evitar_: devolução, reprovação, validação.

**Contestação**:
O aviso do responsável, enquanto a Ata está em assinatura, de que o item dele está errado. A Pendência continua cobrada até o Facilitador ajustar ou recusar, com Anotação. A Ata não volta para assinatura.
_Evitar_: recusa (é o que o Facilitador faz com a Contestação), discordância.

**Ação, Rotina e Processo**:
Os três tipos de linha do quadro da Ata. **Ação** acontece uma vez, tem entregável e vira Pendência. **Rotina** se repete toda semana, quinzena ou mês, tem responsável e substitui o fluxo contínuo. **Processo** define como se faz dali para frente, sem responsável e sem cobrança, e vai para as Definições de processo do setor.
_Evitar_: fluxo contínuo (virou Rotina), meta recorrente, chamar Processo de POP (o POP é outro módulo).

**Verificação**:
O registro de um ciclo de uma Rotina, marcado pelo responsável como Realizada (um clique) ou Não realizada (com Anotação). O ciclo segue o calendário: semana, quinzena (do dia 1 ao 15 e do 16 ao fim do mês) ou mês, e vale até o último dia. Verificação não marcada depois do ciclo fica atrasada e ainda pode ser marcada.
_Evitar_: checagem, conferência, validação.

**Definições de processo do setor**:
A lista das linhas do tipo Processo, por setor da Reunião, com o trecho da Ata copiado. Mora nas Reuniões, não nos POPs.
_Evitar_: POP, rascunho de POP, norma.

**E-mail de segunda**:
O resumo semanal, toda segunda às 8h, um por pessoa: para o Facilitador, o que aconteceu nas Reuniões dele; para o responsável, as Pendências dele em aberto. Não sai quando não há nada para mostrar.
_Evitar_: relatório semanal, digest, newsletter.

## Assinatura digital

**Envelope**:
O container da ClickSign que agrupa o PDF da Ata e seus Signatários. Identificado por `envelope_key_clicksign`. Fecha de dois jeitos, e ambos são **finalização**: todos assinam, ou o deadline (30 dias) estoura e a ClickSign fecha com as assinaturas que tiver. Nos dois casos a Reunião vira ASSINADA; quando faltou gente, o banner ganha um selo discreto "N de M assinaram". Recusa ou cancelamento matam o Envelope sem reenvio: a ciência de quem falta segue por **Aceite interno** (ADR 0030, emendada pela 0098).
_Evitar_: documento, contrato, pacote.

**Aceite interno**:
O equivalente funcional da assinatura, colhido pelo próprio sistema quando o Envelope morre (recusa ou cancelamento). O Signatário pendente recebe email com link público tokenizado, vê a ata completa e clica "Li e aceito": o aceite conta como o "assinou" dele no desfecho. Não cria Pendência, porque elas já nasceram no envio (ADR 0098). O Super admin pode registrar o aceite em nome de um signatário (auditado em `audit_log`). Não é assinatura digital: a formalidade ClickSign continua exclusiva do Envelope.
_Evitar_: assinatura interna, aceite manual.

## Dados do Atendimento (Ana)

Área nascida no ADR 0031 (14/ago/2026): o app vira a casa dos dados que alimentam a **Ana**, e ganha a primeira API de serviço para outro sistema.

**Ana**:
A agente de IA de atendimento e agendamento de pacientes do mesmo hospital: produto irmão, com repo e roadmap próprios (`~/PedroDev/Ana`). **Ainda não atende no WhatsApp oficial do hospital**: aquele número segue no Kommo, com atendimento humano, e o canal vivo dela é um Telegram de teste, mais uma inbox de API (ADR 0034). Consome dados deste app pela [API da Ana]; não loga, não tem conta, não é usuária.
_Evitar_: tratar a Ana como feature deste app (é cliente de serviço).

**Retrato da Ana**:
A página que explica a [Ana] para quem decide, gerada no repositório dela: o que ela faz (as capacidades), as regras (o mapa do prompt e o texto de cada seção), onde ela busca a resposta (ferramentas e integração) e o que a Global Health dá e não dá. É regenerada sempre que o prompt muda e aparece na aba Ana do [Manual do usuário], só para Super admin (ADR 0094).
_Evitar_: publicar o Retrato em site aberto; copiar o Retrato para o repositório deste app, que é público; Retrato com o prompt de uma versão velha.

**Dados do Atendimento**:
O módulo da área admin com as tabelas que alimentam a Ana: consultas particulares (preços e diferenciais), exames e estimativas de cirurgias. Só o Super admin vê e edita (ADR 0101); o time da Vitta entra como Super admin, porque o [Desenvolvedor] já é um. Edição vale imediatamente para a Ana (leitura direta, sem cache). Substitui a planilha do NocoDB (aposentado pelo ADR 0031). A tabela de convênios por especialidade saiu no ADR 0038: cobertura de convênio é a agenda online da Global Health quem responde, e no lugar dela vive o [Espelho da Global Health]. A regra que organiza o módulo: a Global Health é dona da agenda (o que existe, quem atende, quem é aceito, quando); as tabelas daqui são donas do que ela não tem (preço particular, preparo, estimativa).
_Evitar_: "tabelas do NocoDB" (a casa agora é aqui); cache entre a edição e a API; abrir a leitura a Facilitador ou Secretária; permissão própria para o time da Vitta.

**Manifestação**:
O caso de ouvidoria completo, que vive neste app desde o ADR 0034: relato integral sem edição, identificação de quem manifestou (ou anônima), contato, vínculo, classificação sugerida pela Ana à parte, marcos de tempo e desfecho. Substitui o "índice, não dossiê" do ADR 0031, que deixou de valer. Nasce **em classificação**: nenhum processo automático despacha, só quem tem o [Perfil da Ouvidoria] valida e aciona a área. Denúncia e relato de conduta nascem com **sigilo reforçado**: nem aparecem no índice de quem está fora da Ouvidoria. Quem diz que o caso é denúncia é o [Tipo da manifestação], nunca o texto digitado.
_Evitar_: "protocolo" como sinônimo (o Protocolo é o número, a Manifestação é o caso); mudar estado por fora da máquina de estados.

**Paciente do caso**:
A pessoa atendida de quem a [Manifestação] fala, quando não é quem manifestou (decisão de 09/09/2026, a partir do áudio da Diretoria: o acompanhante reclama pelo QR e a área não acha o atendimento). São dois dados do caso, ambos opcionais: o **nome do paciente** e a **referência do atendimento** (texto curto: data, setor ou leito). Nascem no [Canal aberto] e no registro manual do ouvidor; a Ana fica para leva própria. Não são editáveis depois do nascimento, como o resto da identificação. **Viajam para a área** no caso comum e no caso anônimo, porque o anonimato protege quem falou e o paciente é outra pessoa; não viajam no sigilo reforçado, onde o extrato do ouvidor decide o que sai. Relato em nome de outra pessoa sem nome do paciente acende um aviso no Dossiê antes do acionamento, sem travar nada. A [Retenção] **apaga os dois** junto com o resto do Dossiê, pelas duas portas (os cinco anos e a porta antecipada da Diretoria): é dado pessoal de terceiro, e o anonimato de quem manifestou nunca os alcançou.
_Evitar_: tornar o nome obrigatório (canal aberto nunca barra); esconder o campo quando o manifestante marca "anônimo"; colar o nome dentro do relato (o relato é integral, sem edição); esconder o paciente da área no caso anônimo (é o que faz a área devolver por "não achei"); confundir com "quem manifestou".

**Tipo da manifestação**:
O que a [Manifestação] é, em lista fechada: `denuncia`, `reclamacao`, `sugestao`, `elogio`, `relato_de_conduta`, `informacao` (ADR 0037; `informacao` entrou pelo ADR 0040, a partir do diagnóstico da Diretoria de 31/08/2026, RN-57, sem sigilo por natureza e sem renomear `relato_de_conduta`). É ele, e só ele, que decide o **sigilo reforçado**: `denuncia` e `relato_de_conduta` são sigilosos por natureza, nos três canais, sem ato humano. A regra automática é **piso, nunca teto**: o ouvidor eleva o sigilo de um caso que a lista não previu, e não retira o de um tipo sigiloso por natureza. Tipo vazio significa **não classificado**, e o caso não classificado é sigiloso (fail-closed): é assim que entram o [Canal aberto] e o canal da Ana, e a saída é a classificação. Ao lado dele vive a **categoria**, rótulo humano em texto livre ("demora no atendimento", "conduta da equipe noturna"), que descreve o caso e não decide nada.
_Evitar_: ler a categoria para decidir sigilo (era a regra antiga, e "Assédio moral" não casava com termo nenhum); deixar a Ana mandar o tipo (ela registra, não classifica); tratar tipo vazio como caso comum.

**Classificação**:
O ato do [Perfil da Ouvidoria] que grava o [Tipo da manifestação], o rótulo e o sigilo do caso, e é a **única porta do sigilo**: sobe e desce no mesmo lugar, com movimento na trilha e registro no log de acesso. Acontece em duas telas com a mesma regra: dentro da [Validação e acionamento], para o caso que vai ser despachado, e no Dossiê, para o que já foi ou nunca vai ser. Sem pedido explícito, o sigilo de hoje é mantido: descer é ato consciente, não efeito colateral de reclassificar. A reabertura por reincidência só **eleva**, porque reabrir não é classificar.
_Evitar_: abaixar sigilo sem ato explícito; porta de sigilo separada da classificação; mudar sigilo sem deixar rastro com autor.

**Anexo (da Manifestação)**:
A evidência que fica junto do caso: imagem, PDF, áudio ou documento, até 20 MB por arquivo. Só os metadados ficam no banco; o binário vive em bucket **privado** e se lê por URL assinada com expiração, emitida pelo backend depois de conferir o [Perfil da Ouvidoria]. Estar logado no app não abre anexo de ouvidoria.
_Evitar_: guardar binário no banco; bucket público ou link permanente; servir anexo por caminho que não confira a manifestação de origem.

**Canal de origem**:
Por onde a [Manifestação] chegou ao hospital. Hoje: `ana` (atendimento da Ana), os dois do [Canal aberto], `site` e `qr`, e os sete do registro manual do ouvidor: `whatsapp`, `telefone`, `presencial`, `email`, `instagram`, `reclame_aqui` e `google` (decisão de 15/09/2026, a partir do relato de que o ouvidor carimbava como telefone o que chegava pelo WhatsApp do Kommo). Os quatro últimos nasceram **antes** de qualquer integração: o ouvidor lê a conversa, a avaliação ou o comentário na plataforma e digita o caso à mão, como faz com o telefonema. `ana` e `whatsapp` são canais distintos e a diferença é **quem atendeu**, não o aplicativo: `ana` é a agente de IA pela [API da Ana]; `whatsapp` é humano no WhatsApp do hospital (hoje no Kommo). O link da avaliação pública ou o @ do perfil vão no contato do manifestante ou como anexo; campo estruturado para isso fica para quando a resposta pública virar ação. O canal é fixo depois do nascimento, como o resto da identificação: caso carimbado errado ganha um [Movimento] com a nota, não uma edição. Não confundir com o **T0**, a data e hora reais do contato: o ouvidor pode digitar hoje um telefonema de ontem, e é o T0 que vale para abertura, protocolo e prazo, nunca o momento do clique.
_Evitar_: usar a hora da digitação como marco do caso; tratar canal como setor; ler `whatsapp` como caso da Ana; corrigir canal antigo em massa (o WhatsApp começa do zero no relatório do mês da virada, e isso é verdade).

**Protocolo de ouvidoria**:
O número que identifica a [Manifestação] e é informado a quem manifestou, formato `ANO-NNNN` (ex.: 2026-0007), gerado por sequence do Postgres, nunca pela aplicação nem por IA; NNNN contínuo, não reinicia por ano. Números já comunicados a pacientes seguem valendo: a fundação da numeração não é tocada por migration nova.
_Evitar_: compor ou estimar número fora da sequence; reiniciar a numeração; prefixo `OUV-` como dado (pode ser exibição).

**Canal aberto**:
A entrada da [Manifestação] sem login: o **formulário público** (`/manifestacao`) e o **QR setorial**. O manifestante escreve o relato, se identifica ou não, e recebe o [Protocolo de ouvidoria] na tela; o caso entra em classificação, **sem área definida**, porque quem classifica é o ouvidor. A URL impressa no cartaz é `https://<app>/ouvidoria/qr?p=<codigo>` (rewrite do Next para a rota do backend), onde o código resolve um [Ponto de escuta] cadastrado; o formato antigo `?setor=X&ponto=Y` foi aposentado pelo ADR 0036. É o **servidor** que decide o destino (hoje o formulário; amanhã a conversa da Ana no WhatsApp oficial), para o cartaz nunca precisar ser reimpresso. O setor do cartaz é **origem, não área responsável**: fica em `canal_setor`, junto do `canal_ponto`, e os dois só são gravados quando o código resolve um Ponto de escuta ativo; a área continua sendo decisão do ouvidor. Canal sem credencial tem rate limit por manifestante (primeiro salto do `X-Forwarded-For`, porque o Next proxia a chamada), honeypot e nenhum campo que decida classificação, estado ou sigilo. O seletor das quatro naturezas do formulário (elogio primeiro, opcional, RN-88/ADR 0040) é **sugestão** gravada à parte em `natureza_informada`: não classifica, não decide nada. O ouvidor a lê no Dossiê, num bloco que nomeia a origem ("O manifestante informou: Elogio") e diz que a classificação segue sendo dele; caso sem escolha não desenha bloco nenhum. Desde 09/09/2026 o formulário pergunta, logo depois do relato e com resposta obrigatória de um toque, **"Este relato é sobre quem?"**: "Sobre mim" grava o vínculo `paciente`, "Sobre outra pessoa" grava `acompanhante` e abre os dois campos do [Paciente do caso]; esses campos continuam visíveis com "anônimo" marcado. Colaborador e terceiro ficam para os canais em que alguém conversa com a pessoa. Desde a ADR 0086 (11/11/2026) o cartaz imprime `/a/{código}` e abre o [Funil do QR], o formulário vira a [Manifestação guiada], e as URLs antigas redirecionam.
_Evitar_: deixar o manifestante escolher área, tipo, gravidade ou sigilo; gravar o setor do cartaz na coluna `setor` (faz o caso parecer já classificado); imprimir no cartaz a URL final em vez da `/ouvidoria/qr`; imprimir setor e ponto por extenso na URL; pendurar a página pública sob `/ouvidoria` (aquele espaço é da área logada do ouvidor).

**Ponto de escuta**:
Cada lugar do hospital que tem um cartaz de QR da Ouvidoria: setor, rótulo do ponto ("Poltrona 12", "Corredor do 3o andar"), código curto de 6 caracteres e ativo. É o cadastro por trás do [Canal aberto]: o código impresso no cartaz resolve aqui, e é daqui que saem o PNG do QR e o cartaz A5 em PDF que a tela `/ouvidoria/pontos` entrega prontos. Quem cadastra e imprime é o [Perfil da Ouvidoria], porque cartaz é operação do canal e não governança. Ponto **desativa, nunca apaga** (o histórico de casos aponta para ele), e o QR de ponto inativo abre o formulário público normal, sem origem: quem está parado na frente de um cartaz nunca fica sem canal.
_Evitar_: apagar ponto; devolver erro ao QR de ponto inativo; ler `canal = 'qr'` como prova de presença física (o código está impresso na parede, à vista de quem passa); cadastro de pontos paralelo à taxonomia de Setores.

**Triagem de e-mail**:
O filtro por onde passa todo e-mail que chega em `ouvidoria@` antes de virar caso (ADR 0051). Cada **e-mail recebido** (remetente, assunto, data, corpo e anexos) entra numa lista que só o [Perfil da Ouvidoria] vê, e acende o mesmo ponto de novidade da fila. O ouvidor tem três ações: **virar manifestação** (abre o registro manual pré-preenchido, com canal `email`, T0 igual à data do e-mail e o corpo como relato; o ouvidor escolhe o tipo, e o acuse de recebimento do ADR 0042 sai daí), **juntar a um caso existente** (o texto e os anexos entram como [Movimento] do caso, sem mudar estado nem prazo; se o assunto traz o [Protocolo de ouvidoria], o app sugere o caso) e **descartar** (fica só o cabeçalho, com quem descartou e quando; corpo e anexos são apagados). Não é [Canal aberto]: e-mail traz spam, newsletter e resposta interna, e manifestação não se apaga (ADR 0047), então o filtro vem antes do caso. Ninguém recebe resposta automática na chegada.
_Evitar_: transformar e-mail em caso sem ato do ouvidor; responder automaticamente ao e-mail recebido (responde a robô e abre loop); guardar corpo de e-mail descartado; chamar a tela de "caixa de entrada" (promete responder por ali, e o app não responde e-mail).

**Movimento**:
O registro do que aconteceu com uma [Manifestação]: estado anterior, estado novo, quem fez e quando. A trilha é **imutável** e append-only, gravada na mesma transação da mudança de estado (RPC `ouvidoria_transicionar`): nem a aplicação, nem a API, nem o Super admin editam ou apagam, e o banco recusa por trigger. O **fato** é imutável para sempre; o **conteúdo** da `observacao` tem uma única saída, a [Retenção], porque a resposta da área viaja inteira para dentro dele. Apagar linha continua proibido sem exceção.
_Evitar_: mudar `status` direto por UPDATE; corrigir a trilha (o erro se conserta com movimento novo); tratar a saída da retenção como permissão geral de editar observação.

**Retenção**:
A política de LGPD que apaga o Dossiê da [Manifestação] encerrada há mais de cinco anos e preserva o que os relatórios contam (tipo, área, gravidade, canal, datas, marcos e desfecho). Roda sozinha, de madrugada, e varre os cinco lugares onde o relato mora: a manifestação, os anexos (metadados e binário), a `observacao` dos [Movimento]s, o texto livre das tentativas de contato e das prorrogações, e o `detalhe` das notificações (por onde viajam o motivo da devolução e o da reabertura, escritos pelo ouvidor). O ato entra na trilha, e o carimbo `anonimizada_em` faz o job ser idempotente.
 Desde a decisão de 04/09/2026, a mesma política tem uma **porta antecipada**: a `diretoria_executiva` pode apagar o Dossiê de um caso encerrado antes dos cinco anos, um caso por vez, com motivo escrito obrigatório. É isso que "apagar uma manifestação" significa neste app: o relato, o nome, o contato, os anexos e o texto livre somem hoje; o protocolo, a trilha e os números ficam. O ato entra na trilha com autor e motivo, e é a única coisa que sobra para explicar o buraco. O Dossiê de caso apagado (pela porta antecipada ou pelos cinco anos) mostra o aviso no lugar do relato, e o caso **não reabre** por reincidência: quem volta abre caso novo. Caso apagado entra no [Arquivo] sozinho.
_Evitar_: contar os cinco anos de qualquer marco que não seja o encerramento (T3); anonimizar caso sem `encerrada_em` (o import histórico do NocoDB nasceu assim, `encerrado` sem marco); apagar linha de trilha, de tentativa ou de prorrogação (some a estatística; o que sai é o texto); apagar a linha da manifestação ou tirá-la dos números ("apagar totalmente" é a porta antecipada, nunca DELETE); apagar sem motivo; apagar pelo `ouvidor` ou pelo Super admin; reabrir caso apagado.

**Calendário útil**:
O relógio em que os prazos da Ouvidoria correm: segunda a sexta, das 08h às 17h, no fuso `America/Sao_Paulo`, sem os feriados nacionais, estaduais do RJ e municipais do Rio (tabela administrável, RN-22). Manifestação que entra fora do expediente tem a entrada registrada na hora real, mas a contagem só abre na próxima abertura. **Dia útil não conta o dia do fato**: o prazo de 2 dias úteis de um caso validado sexta às 16h50 abre segunda às 08h e vence terça às 17h. **Hora útil** anda dentro do expediente e para às 17h.
_Evitar_: contar em dias corridos; contar madrugada e fim de semana; embutir feriado no código.

**Motor de prazos**:
A função pura que, dada a gravidade, a [Tabela de prazos] e os feriados, devolve o vencimento (em UTC) e o rótulo em linguagem natural ("vence em 2 dias úteis", "vencido há 3 horas úteis"). Não lê banco nem consulta o relógio: quem carrega os parâmetros é a rota, quem grava o vencimento é quem valida a [Manifestação]. O vencimento fica **congelado** no caso desde o acionamento: mudar a tabela de prazos depois não recalcula caso já despachado. O painel e o email do setor mostram o mesmo rótulo porque saem do mesmo motor.
_Evitar_: recalcular prazo de caso já despachado; calcular calendário útil no navegador; prazo em dias corridos.

**Tabela de prazos**:
Os prazos por gravidade (crítico, alto, médio, baixo) e por marco (acusar recebimento, triagem, resposta da área, resposta conclusiva), em banco e editáveis em tela **só pela `diretoria_executiva`**, sendo o acusar recebimento o único marco em **horas corridas** (promessa ao paciente, ADR 0042; os demais correm no [Calendário útil]), com histórico append-only de quem mudou o quê (RN-21). Valor em branco significa sem prazo para aquela combinação (crítico não tem conclusiva fixa; baixo não passa pela área); zero significa imediato. Nasce com os valores da especificação da Diretoria como seed, porque a tabela ainda muda com as coordenações.
_Evitar_: prazo hardcoded; deixar o ouvidor editar (ele usa o prazo, quem o define é a Diretoria).

**Semáforo de prazo**:
A cor que a linha da fila dá ao vencimento da [Manifestação], em quatro degraus (vencido, vence hoje, até um dia útil de folga, folga maior) mais o relógio parado de quem já saiu das mãos da Ouvidoria (RN-58). A régua de cor é **própria**, nos tokens da tela: vermelho (`text-red-600`) para vencido e vence hoje, âmbar (`text-amber-600`) para o degrau de alerta, neutro (`text-slate-500`) acima disso. Ela **não** é a paleta de gravidade, que vive na pílula da linha (vermelho, laranja, âmbar e cinza claros) e, no email estratificado do setor, nos hexes da spec da Diretoria (`#B3261E` crítico, `#C77700` alto, `#1F3864` médio, `#5F5E5A` baixo, RN-34). Três escalas convivem na mesma linha e cada uma tem seu lugar e sua paleta: estado só na faixa do bloco (RN-70), gravidade só na pílula, prazo só no vencimento. O motivo é a RN-71: pintar o prazo com os hexes da gravidade poria duas perguntas diferentes ("é grave?" e "está atrasado?") na mesma dupla de cores, e é justamente isso que a regra existe para impedir (decisão de 03/09/2026, que emendou a decisão 1 do PRD #471).
_Evitar_: usar os hexes da gravidade no semáforo de prazo; misturar cor de estado, de gravidade e de prazo no mesmo elemento; ler cor de prazo como cor de gravidade.

**Arquivo (da Manifestação)**:
O depósito dos casos **encerrados** que o ouvidor tirou da vista da lista. Arquivar não muda estado, não apaga nada e não entra na trilha: o caso guarda só quando e quem arquivou, e desarquivar limpa o carimbo. Só caso `encerrado` arquiva; caso em andamento tem prazo correndo e setor esperando, e esconder isso é esconder atraso. A recíproca vale no tempo, e não só no instante do clique: a reabertura por reincidência **tira o caso do arquivo**, porque o caso que volta a andar deixa de ser caso guardado, e um prazo novo correndo numa linha que ninguém vê é o mesmo atraso escondido pela porta de trás. Quem arquiva e desarquiva são os dois papéis do [Perfil da Ouvidoria], um caso por vez ou todos os encerrados de uma vez. **Ler** o arquivo é ato do mesmo perfil, e quem confere é o servidor: a vista dos arquivados não é um filtro de tela que se esconde de quem não deve ver, é a outra metade do ato de arquivar, e o índice geral da equipe de Reuniões continua aberto a quem sempre o leu. A lista nasce sem os arquivados e os mostra atrás de um filtro próprio; o caso arquivado continua abrindo pelo protocolo e continua contando nos relatórios e nas métricas, porque arquivar é organização da lista, não fato do caso. Caso apagado pela [Retenção] entra aqui sozinho.
_Evitar_: arquivar caso em andamento; deixar arquivado o caso que foi reaberto; tratar arquivo como estado da máquina; gravar movimento ao arquivar (acenderia o ponto de novidade num caso em que ninguém mexeu); tirar caso arquivado das métricas; guardar a vista dos arquivados só na tela; confundir arquivar (esconde, tem volta) com apagar (some o relato, não tem volta).

**Visto da Ouvidoria**:
O carimbo que apaga o ponto de novidade da linha e tira o caso do contador do menu (RN-66). É **global, um por caso** (`vista_pela_ouvidoria_em`), e não um por pessoa: o ponto diz "a Ouvidoria ainda não viu", não "eu ainda não vi". Novidade é derivada na leitura, nunca guardada: o caso tem novidade quando a última movimentação da trilha é mais recente que o carimbo, ou quando o carimbo é nulo (caso anterior à coluna nasce assim, de propósito). **Dois atos carimbam**, e só eles: a **leitura** (abrir o Dossiê, pelo id ou pelo protocolo) e a **ação do próprio ouvidor** sobre o caso, que são **encerrar** e **validar** (decisão de 03/09/2026, issue #521). A régua tem dois lugares porque o ouvidor encerra e valida pelo botão da própria lista, sem abrir o caso: sem o segundo carimbo, o movimento que a ação grava acendia o ponto e subia o contador logo depois de ele ter trabalhado ali. Quem carimba é o **servidor**, na mesma requisição da transição, e o instante é lido **depois** do movimento, senão o carimbo nasce mais velho que ele e o ponto não apaga.
_Evitar_: carimbar na tela; carimbar pausa, devolução, resposta da área ou reabertura (nenhuma é o ouvidor dizendo "vi e resolvi"); carimbar antes de a transição valer; um carimbo por usuário.

**Validação e acionamento**:
O ato único em que o ouvidor confere o tipo, a área e a gravidade da [Manifestação] e a área é acionada no mesmo passo: o caso vai de "em classificação" para "aguardando área", grava o marco **T1** (quando validou e quem validou), o [Motor de prazos] calcula o vencimento e o [Responsável do setor] recebe o email de acionamento. É a única porta do despacho: nenhum processo automático acorda um setor, e quem não tem o [Perfil da Ouvidoria] não passa nem pela API. A sugestão da Ana não vem junto: ela fica em `classificacao_ia` e nunca vira a classificação validada. É aqui também que o [Tipo da manifestação] é **decidido**, então a [Classificação] acontece dentro deste passo, com a mesma regra da outra porta: o sigilo sobe quando o tipo pede, e desce quando o ouvidor pede e o tipo permite. É também a porta do **reacionamento** depois de uma [Devolução à Ouvidoria] (decisão de 04/09/2026): o caso voltou a "em classificação", a tela vem pré-preenchida com o que o ouvidor já tinha decidido, ele troca a área e confirma; o T1 é carimbado de novo e o prazo da área nasce cheio. O [Redirecionamento] entra pela mesma porta, na mesma requisição em que tira o caso da área antiga.
_Evitar_: acionar setor sem validação; recalcular o vencimento de caso já acionado; deixar a IA preencher a gravidade; usar a reclassificação para tirar o sigilo de um caso.

**Extrato para o setor**:
O texto que o [Responsável do setor] lê no acionamento, escrito pelo ouvidor na [Validação e acionamento], com as palavras dele. **Obrigatório em todo acionamento, sem exceção**: a validação é recusada sem ele. Desde o diagnóstico da Diretoria de 31/08/2026 (RN-78), o email de acionamento e a tela do responsável carregam **três blocos separados**: resumo, relato integral e o extrato (a "nota da ouvidoria"), nesta ordem e visualmente distintos, para a área responder ao paciente e não à interpretação da Ouvidoria. Caso com sigilo reforçado é a exceção (RN-79): sem identificação do manifestante, e o extrato substitui o relato integral. Nessa exceção o **resumo também não viaja** (ele é a palavra crua de quem manifestou, capaz de carregar nome e leito): o acionamento sob sigilo reforçado sai só com a nota da ouvidoria. O **caso anônimo sem sigilo reforçado leva os três blocos**, como o caso comum, desde a emenda de 07/10/2026 da ADR 0041 (issue #1051), que reverteu a extensão da proteção ao anônimo ratificada em 03/09/2026: a área que lia só a nota não conseguia trabalhar o caso. O anônimo continua sem identificação de quem manifestou, e o aviso dele só diz que a manifestação é anônima e pede para não procurar a autoria. Quando o relato expõe quem escreveu, o caminho é subir o sigilo reforçado. Essa decisão revogou a proibição anterior de mandar o relato ou o resumo por email ao setor; o extrato continua obrigatório, agora como um dos três blocos. O extrato fica gravado no caso, para o reenvio mandar a mesma coisa e para provar o que a área recebeu.
_Evitar_: fundir os três blocos ou dar a eles a mesma formatação (RN-60); mandar relato ou identificação em caso sigiloso; mandar a identificação de quem manifestou em caso anônimo; prometer no email uma proteção que o texto enviado não tem.

**Responsável do setor**:
Quem responde por um setor na Ouvidoria, com papel (`titular`, `substituto`, `gestor`) e **vigência** (o fim é inclusivo: quem sai no dia 31 ainda responde no dia 31). Fica sobre a taxonomia de Setores da casa, sem cadastro paralelo. Quem o mantém é o [Perfil da Ouvidoria] inteiro, `ouvidor` e `diretoria_executiva` (decisão de 14/09/2026, ADR 0055; antes era só a Diretoria, como na [Tabela de prazos], que continua só dela): trocar quem responde é encerrar a vigência do titular e cadastrar o novo, e um Cobrar em seguida leva o caso ao vigente. Não existe destinatário por caso: a cadeia de cobrança e escalonamento inteira parte deste cadastro. O titular vigente é quem recebe o acionamento; **setor sem titular vigente não é acionável** e a demanda sobe ao gestor da área, com alerta à Diretoria. Sem titular e sem gestor, a validação é recusada em vez de mandar a demanda para o vazio.
Desde a ADR 0099 (16/11/2026), o responsável que tem login no app é reconhecido pelo e-mail: o e-mail de quem entrou, sem diferenciar maiúsculas, casa com as linhas vigentes deste cadastro. Titular, substituto e gestor vigentes veem na Ouvidoria só os casos acionados para o setor deles ("A responder" e o histórico do setor) e respondem pelo botão RESPONDER, que abre a [Tela do responsável]. Os três podem responder, e a trilha guarda quem respondeu. O cadastro mostra se cada e-mail tem login.
_Evitar_: apagar o responsável para tirá-lo do papel (o caminho é encerrar a vigência); cadastrar setor que não existe na taxonomia; escolher a pessoa por caso ao acionar (o responsável é do setor); mostrar ao responsável logado casos de outro setor; recortar pelo e-mail de acionamento recebido (quem perdeu o e-mail fica sem o caso).

**Tela do responsável**:
A página que o [Responsável do setor] abre pelo link do email de acionamento, sem senha, do celular, uma vez só. A RN-59 fixa a ordem de leitura, porque quem abre este link é o usuário menos treinado do módulo e a hierarquia da tela é o que substitui o treinamento: gravidade, prazo em contagem regressiva, a linha secundária (protocolo, setor e categoria), **quem manifestou**, o **[Paciente do caso]**, os três blocos do [Extrato para o setor], o campo único O QUE FOI FEITO e os dois botões (RESPONDER e SOLICITAR PRORROGAÇÃO). São **dez elementos** desde 03/09/2026 (issue #511): "quem manifestou" já estava na tela desde o portal do setor, sem nome na regra, e o que não tem nome fica fora de qualquer teste de ordem. Ele é o mesmo dado que o email de acionamento carrega e sai pela mesma guarda do caso protegido: caso sigiloso e caso anônimo chegam com "Sem identificação", e a linha permanece, porque a ausência é informação (apagada, a área não distingue caso sem identificação de tela incompleta).
_Evitar_: enfiar elemento novo entre a gravidade e o prazo (no celular ele empurra o prazo para fora da primeira tela, que é o que a RN-59 existe para evitar; a única exceção, nomeada e fechada em 03/09/2026 na issue #559, é a **linha de identidade do hospital**, o logo mais "Demanda da Ouvidoria", que fica ali de propósito, porque a página é pública e abre a partir de um email, e sem ela quem recebe o link não sabe que a tela é do hospital; qualquer outro elemento continua proibido ali); montar quem manifestou por fora da guarda do caso protegido; deixar a tela reconstruir resumo ou relato que o servidor cortou.
 Desde a decisão de 04/09/2026, a tela tem um **décimo primeiro elemento**, o último de propósito: o link discreto da [Devolução à Ouvidoria] ("Este caso não é do meu setor?"), abaixo dos dois botões, porque responder continua sendo o ato principal e a devolução não pode competir com ele. Desde a issue #664 (ADR 0052, decisão 4) a ordem tem mais um elemento, logo abaixo de quem manifestou: a linha **Paciente**, com o nome e, se houver, a referência do atendimento entre parênteses. Ela sai de uma guarda própria, e não da de quem manifestou: viaja no caso comum e no caso anônimo (o anonimato protege quem falou, e o paciente é outra pessoa) e não viaja no sigilo reforçado. O email de acionamento e o reenvio leem da mesma função, então o reenvio de um caso que subiu para sigilo depois do acionamento já sai sem o paciente. Caso sem paciente informado não desenha a linha: ao contrário do "Sem identificação", aqui a ausência não é informação.
 Desde a ADR 0099 (16/11/2026) a mesma tela tem uma segunda porta: o [Responsável do setor] com login abre o caso pelo botão RESPONDER na lista da Ouvidoria, com a mesma ordem, os mesmos botões e as mesmas guardas; muda só que o login entra no lugar do token. Cada caso tem uma resposta só: agir pelo app consome o link do e-mail, e usar o link tira o botão do app.

**Devolução à Ouvidoria**:
O ato do [Responsável do setor] que devolve ao ouvidor a [Manifestação] que não é da área dele, com motivo escrito **obrigatório** (decisão de 04/09/2026, a partir do pedido da Diretoria: a Recepção recebe um caso que é do médico e precisa devolver para o ouvidor encaminhar). Nasce na [Tela do responsável], pelo link discreto abaixo dos dois botões. A área **não escolhe destino**: ela diz por que o caso não é dela, e quem encaminha é o ouvidor, como em todo despacho. O caso volta a **em classificação**, o relógio da área para e a cobrança daquele setor cessa; a Ouvidoria é avisada e o ponto de novidade acende. O ouvidor reaciona pela mesma [Validação e acionamento], que vem **pré-preenchida** com tipo, gravidade e extrato do acionamento anterior: ele troca a área e confirma. O reacionamento grava **T1 novo** e a área certa recebe **prazo cheio**: o tempo perdido com a área errada entra no trecho da Triagem, na conta da Ouvidoria, que foi quem despachou. Não há limite de vezes: a cada volta há um humano decidindo, e a trilha guarda cada devolução com o motivo. O motivo é texto livre, sem piso e com o mesmo teto dos demais textos da área, e vive na `observacao` do [Movimento], por onde a [Retenção] o alcança. Devolver usa o link **uma vez só** e só vale enquanto o caso aguarda a área. Não confundir com a **Devolução por insuficiência**, que anda na direção contrária: o ouvidor devolve resposta fraca ao mesmo setor, com meio prazo. Nem com o [Redirecionamento], que é o mesmo erro de destino percebido pelo ouvidor, e não pela área.
_Evitar_: deixar a área escolher a área nova; chamar de "recusa" (a área não se nega a trabalhar, ela diz que o caso não é dela); estado novo na máquina para o caso devolvido; fazer a área certa herdar o prazo que sobrou da errada; botão do mesmo peso de RESPONDER; devolução no relatório antes de haver histórico para ler (fica para leva própria).

**Redirecionamento**:
O ato do ouvidor que tira a [Manifestação] de uma área e a aciona em outra, num clique só, sem esperar a [Devolução à Ouvidoria] (decisão de 14/09/2026, ADR 0055, a partir da pergunta da Diretoria: "o ouvidor consegue, de forma fácil, alterar a área responsável?"). Vale para caso em **aguardando área** ou **respondido** (a área errada que responde "isso é do Centro Médico" em vez de devolver); caso pausado é retomado antes. O botão "Redirecionar", no Dossiê e no menu da linha da fila, abre a [Validação e acionamento] pré-preenchida com tipo, gravidade e extrato, área em branco e **motivo obrigatório**. Numa requisição só, o servidor tira o caso da área antiga (consome o link, para o relógio, zera os carimbos de cobrança e escalonamento, grava o movimento "Redirecionado pelo ouvidor (de <setor>): motivo") e aciona a área nova pela porta de sempre: **T1 novo, prazo cheio**, e o tempo perdido na conta da Triagem da Ouvidoria, a mesma contabilidade da devolução. Se a área nova não tem titular nem gestor vigente, nada acontece e o caso fica onde estava. A área antiga recebe um **aviso curto** (gatilho `redirecionamento_area`): a demanda daquele protocolo foi encaminhada a outra área e não é preciso responder, sem motivo e sem dizer qual. A resposta da área errada, se houver, fica na trilha como está e não viaja para a área nova. Sem limite de vezes, sem linha no relatório nesta leva.
_Evitar_: fazer em dois atos (retirar e depois validar deixa o caso parado em classificação sem ninguém cobrando); a área nova herdar o prazo restante da errada; redirecionar caso pausado; contar redirecionamento como devolução no Dossiê (o prefixo da observação separa os dois); usar a transição genérica `aguardando_area -> em_classificacao` como redirecionamento (ela não consome o link nem para o relógio); mandar o motivo ou a área nova no aviso à área antiga.

**Notificação da Ouvidoria**:
Todo email que a Ouvidoria dispara nasce antes como registro no caso (data, destinatário, gatilho), e é isso que prova a cobrança e alimenta o botão de reenvio. Gatilhos desta leva: `nova_demanda` (acionamento do setor) e `alerta_sem_titular` (aviso à Diretoria); o catálogo cresceu depois para 12 gatilhos internos (prazos, escalonamentos, prorrogações, devolução e reabertura), e o ADR 0042 acrescentou os dois primeiros com o manifestante como destinatário: `acusar_recebimento` (automático na abertura, fora da janela comercial) e `encerramento_manifestante` (protocolo, desfecho em linguagem simples e canal para reabrir). Duas regras de tempo: **janela comercial** (notificação não crítica gerada fora do expediente espera a próxima abertura; caso crítico sai na hora) e **retentativa com backoff** (falha do provedor devolve a notificação à fila com espera crescente; na terceira falha o registro vira `falha` e o admin técnico é avisado). Quem tira da fila é um job periódico idempotente: antes de chamar o provedor, a notificação é reivindicada (estado `enviando`), para o job não pegar uma linha em voo e mandar a mesma cobrança duas vezes. O reenvio manual nasce como registro próprio, sem reescrever o envio original.
_Evitar_: mandar email sem registrar; reescrever o registro do primeiro envio; disparar cobrança automática de madrugada; devolver à fila uma notificação que já saiu.

**Nota externa**:
A nota que o hospital tem FORA dele: as estrelas do Google (escala de 0 a 5) e o índice do Reclame Aqui (escala de 0 a 10). Nenhuma das duas é medida pelo sistema. Quem as sabe é o [Perfil da Ouvidoria], que abre as duas páginas e digita o que leu; a integração automática é fase seguinte da spec. Cada registro é uma **linha nova**, nunca uma edição, e o que vale é a última de cada fonte: o diário é o que guarda a evolução e o que deixa o relatório de julho, reenviado em setembro, mostrar a nota de julho. O relatório congela a nota junto dos números e a imprime no bloco **Retrato externo**.
Desde a ADR 0089 (11/11/2026) a nota do Google deixa de ser digitada: ela é buscada toda semana pela API do Google, com o total de avaliações, e mostrada na Central de Comando; a tela da Ouvidoria a repete só para leitura. O Reclame Aqui continua digitado.
_Evitar_: mostrar a nota sem a escala ao lado (4,3 de 5 é 86% e 7,8 de 10 é 78%: lado a lado sem denominador, o leitor conclui o contrário); transformar ausência de registro em 0 (leria como a pior nota possível); sobrescrever a linha anterior; validar as duas fontes contra um teto único (aceitaria "Google 8").

**Perfil da Ouvidoria**:
O eixo de permissão próprio do contexto Ouvidoria, ortogonal ao perfil de acesso das Reuniões e ao perfil de POPs: `ouvidor` e `diretoria_executiva`. Só esses dois abrem a [Manifestação] completa, inclusive a sigilosa; o **Super admin fica de fora** (RN-40), porque administrar o sistema não é ler o relato de quem manifestou. O índice de todos os casos, sem relato, fica com este perfil, a Secretária (que mantém a fila) e o Super admin; o [Responsável do setor] com login vê só os casos do setor dele, e quem não é nenhum desses não vê a Ouvidoria (ADR 0099, que emendou a decisão 8 da ADR 0034, onde todo papel de Reuniões via o índice). O Super admin concede o perfil pela tela de Usuários, e a concessão fica no audit log. Todo acesso à Manifestação gera registro de log, inclusive a consulta pelo [Conector] (ADR 0085). A `diretoria_executiva` lê pelo [Conector] o mesmo Dossiê que abre na tela.
_Evitar_: tratar Super admin como quem vê tudo; usar o perfil de Reuniões para decidir acesso ao dossiê.

**Avaliação**:
A nota de 1 a 5 deixada pelo QR, com os motivos (lista fechada de oito) e o comentário opcional de até 500 caracteres (ADR 0086). **Não gera protocolo**: é dado de gestão, sem fila e sem prazo, e não guarda nada de quem avaliou (sem IP, sem aparelho, sem contato). Só o [Perfil da Ouvidoria] vê a aba Avaliações. O comentário é apagado cinco anos depois de criado; a nota e os motivos ficam para os números.
_Evitar_: chamar de manifestação ou de pesquisa de satisfação (a pesquisa por WhatsApp é outro pedido); guardar IP para conter abuso.

**Funil do QR**:
O caminho em que o cartaz abre primeiro a [Avaliação], e só quem pede retorno, escolhe registrar ou deixa um elogio entra na [Manifestação guiada]. Notas 1 a 3 perguntam se a pessoa quer retorno; notas 4 e 5 oferecem o elogio e, no [Teste do convite ao Google], o convite. Quem segue sem anonimato fica com o caso ligado à avaliação e ao cartaz; o anônimo guarda só o local que confirmou.
_Evitar_: mandar quem chega pelo site à tela de nota (a nota é sempre de um cartaz).

**Manifestação guiada**:
O formulário público em cinco passos: identificação (com identificação ou anônimo, escolhido primeiro), sobre o quê, quando e onde, o que aconteceu e contato. Substitui o formulário de tela única do [Canal aberto]. Quem se identifica deixa telefone ou e-mail, ao menos um, com o aviso de que as respostas saem por e-mail.
_Evitar_: tornar obrigatório o que serve só para localizar o atendimento (paciente, profissionais, quarto).

**Nome público do ponto**:
O nome do local que o paciente vê na tela de nota e no cartaz ("Emergência adulta"), no lugar do nome interno do setor. Mora no [Ponto de escuta], ao lado da descrição do local, que é o que aparece no painel.
_Evitar_: mostrar ao paciente o nome do setor da taxonomia ("Você leu o QR de Auditoria").

**Código de acompanhamento**:
O código mostrado uma vez ao manifestante anônimo, junto com o protocolo, para acompanhar o caso na [Página de acompanhamento]. Só o hash é guardado. A [Notificação de incidente] anônima ganha o mesmo código.
_Evitar_: guardar o código em claro; mostrá-lo de novo depois da confirmação.

**Página de acompanhamento**:
A página pública onde o manifestante informa o protocolo e o [Código de acompanhamento] (anônimo) ou o protocolo e o contato cadastrado (identificado) e vê só o estado em linguagem simples, a data da última movimentação e a resposta institucional. Nunca mostra setor interno, responsável nem anotação.
_Evitar_: mostrar o nome da área ou do responsável; usar a página para mandar e-mail novo ao manifestante.

**Acionamento de resposta**:
O envio do caso a um setor que precisa responder dentro do prazo: é a [Validação e acionamento] de sempre. Na fase 2 um caso pode ter até três.

**Acionamento de ciência**:
O envio a um setor que só confirma o recebimento, por um botão no e-mail, sem login (ADR 0088). Usado no elogio ("Elogio recebido") e no [Núcleo de Segurança do Paciente] ("Recebido pelo NSP"). O tipo do acionamento é decidido pelo sistema, nunca pelo ouvidor. O do elogio não tem prazo de área nem entra nos vencidos, e reenvia o e-mail uma vez depois de 5 dias úteis; o do Núcleo tem prazo e cobrança em degraus.
_Evitar_: confundir com o [Acionamento de resposta]; deixar o ouvidor escolher o tipo.

**Núcleo de Segurança do Paciente**:
O setor que recebe, em ciência e em paralelo à área, todo caso que descreve um incidente relacionado à assistência (RDC 36/2013): queda, erro de medicação, identificação errada, lesão por pressão, infecção, problema em procedimento, exame trocado ou atrasado com impacto clínico, falha de equipamento, piora ou óbito inesperado. É um setor da taxonomia, com a presidência do NSP como titular no cadastro de [Responsável do setor]. É a única exceção ao sigilo reforçado: recebe o relato integral e o paciente atendido mesmo no caso sigiloso, mas o nome de quem manifestou só quando o caso não é sigiloso. O e-mail só traz o link; o conteúdo fica na tela. É também o primeiro [Colegiado] do app, com módulo próprio (seção Segurança do Paciente).
_Evitar_: "NSP" sozinho em texto para o paciente; estender a exceção de sigilo a outro setor; deixar a investigação do Núcleo bloquear o encerramento do caso.

**Em análise pelo NSP**:
O selo do caso que o ouvidor confirmou para o [Núcleo de Segurança do Paciente]. Na resposta de um caso com o selo, o agente aponta frases que admitem ou negam falha antes do envio.

**Assunto (do caso)**:
A linha que o [Agente de triagem] escreve para cada caso, sem nome de pessoa nem dado clínico identificável ("Demora no resultado de tomografia"). É o que listas, painel e e-mails de cobrança mostram no lugar do começo do relato. Caso sem assunto mostra que ele não foi gerado.
_Evitar_: confundir com a categoria, que é rótulo do ouvidor; mostrar nome de paciente em lista.

**Agente de triagem**:
O agente de IA que lê toda manifestação e toda avaliação com comentário na chegada (ADR 0087) e só sugere: o [Assunto (do caso)], o apontamento ao [Núcleo de Segurança do Paciente] com uma justificativa simples e uma técnica, e a marca [Para revisar]. Nunca classifica tipo, gravidade, sigilo nem área. Se falhar ou passar do teto diário, o caso entra na fila sem assunto e sem alerta, e o ouvidor decide sozinho.
_Evitar_: tratar a sugestão como decisão; mandar ao paciente ou a um setor texto dele sem confirmação humana.

**Para revisar**:
A marca que o [Agente de triagem] põe na [Avaliação] cujo comentário sugere gravidade (incidente, agressão, assédio, risco à vida, menção a processo ou imprensa), qualquer que seja a nota. Não é alerta em tempo real: vira um contador no Painel que leva à aba Avaliações filtrada. O ouvidor tira a marca convertendo a avaliação ou arquivando a revisão com um motivo curto.

**Converter em manifestação**:
A ação do ouvidor que transforma uma [Avaliação] em caso de ouvidoria: canal `qr`, setor e ponto do cartaz, o comentário como relato, tipo vazio (sigiloso até a classificação) e T0 igual à hora da avaliação. A avaliação convertida guarda o cartaz e a ligação, porque a pessoa não pediu anonimato.

**Pronto para encerrar**:
A marca do elogio cujo setor já clicou em "Elogio recebido". O caso volta ao ouvidor, que encerra; o manifestante identificado recebe o aviso de que o elogio foi entregue à equipe.

**Teste do convite ao Google**:
O convite para avaliar no Google mostrado só às notas 4 e 5 do QR, quando a chave geral e a chave do ponto estão ligadas (ADR 0089). Quem liga é a diretoria executiva, com auditoria de cada mudança. Dura 60 dias, mas não se desliga sozinho: no fim, a Central de Comando só lembra de reavaliar. A diretoria aceitou o risco de punição pela política do Google.
_Evitar_: oferecer incentivo, pedir conteúdo ou menção a profissional, dar meta de avaliações à equipe.

**API da Ana**:
Os endpoints de serviço `/api/ana/*`: leitura das tabelas do Dados do Atendimento, registro e consulta de protocolo de ouvidoria. Autenticação por **API key de serviço** dedicada (header), fora do fluxo JWT do Supabase Auth; a chave vive no vault da plataforma da Ana e o escopo é restrito a esses endpoints. Nos endpoints de escrita, campo crítico é NOT NULL e validado (o cliente tem falha silenciosa conhecida que enviaria vazio com HTTP 200; o banco recusa). O registro de protocolo aceita, opcionalmente, os campos do Dossiê da [Manifestação] (relato integral, nome, contato, vínculo e a gravidade sugerida com grau de confiança, guardada à parte em `classificacao_ia`); o POST sem eles continua valendo. A Ana registra manifestação, não classifica caso: status, desfecho, [Tipo da manifestação] e sigilo são decisão do ouvidor e o endpoint recusa quem tentar mandá-los. Por isso o caso dela entra **sem tipo**, logo sigiloso, até o ouvidor classificar. A consulta de protocolo devolve o índice do caso comum e, do sigiloso, só o andamento: protocolo, estado e data.
_Evitar_: reusar a key para outros consumidores; endpoint anônimo; expor esses endpoints no fluxo JWT comum.

**Modo de resposta (API da Ana)**:
O degrau de detalhe que a [API da Ana] escolhe **pelo tamanho** da resposta, para caber no teto de leitura do cliente (a plataforma da Ana corta toda resposta de tool em 4.000 caracteres, sem aviso). São três, do mais rico ao mais magro: `completo` (todos os campos), `resumo` (a vitrine: nome e valor) e `indice` (só os nomes, cada item em texto e não em objeto, porque repetir o nome do campo em cada linha é o que faz o degrau mais magro estourar). O endpoint monta o `completo`; se passar de 3.500 caracteres, desce um degrau, e depois outro. Tirar campo é permitido, **tirar linha nunca**: cortar a lista é o defeito que a regra existe para matar (ADR 0032). O corpo sempre declara o `modo` e a `dica` do gesto seguinte. Cada GET de tabela aceita um filtro por termo (`?exame=`, `?especialidade=`, `?procedimento=`), com termo vazio valendo como sem filtro.

**Espelho da Global Health**:
A seção somente leitura da tela Dados do Atendimento que mostra ao vivo o que a agenda online da Global Health publica (ADR 0038). Só o Super admin vê, como o resto da tela (ADR 0101). Quatro elos encadeados: especialidades publicadas, convênios aceitos e profissionais da especialidade, planos do convênio, horários livres. Botão "Atualizar" dispara a chamada; nada é gravado no banco (espelho, não cópia). O backend é o único que fala com a Global Health (o token nunca chega ao navegador), sempre a base de homologação, só leitura. Falha de rede aparece como falha, e bloco vazio diz por quê. Responde as quatro perguntas de quando a Ana não acha horário: especialidade não publicada, convênio fora da lista, médico desligado no Painel, ou agenda sem horário livre.
_Evitar_: chamar de integração de agendamento (não agenda nada), gravar o que a Global Health respondeu.
_Evitar_: paginação; cortar a lista para caber; supor que a mesma chamada devolve sempre a mesma forma.

## Segurança do Paciente (o módulo do Núcleo)

O módulo em que o [Núcleo de Segurança do Paciente] funciona de ponta a ponta: constituição, notificação de incidente, triagem, investigação, plano de ação, reuniões e prestação de contas (ADR 0095). Entra em quatro fases. O Núcleo continua recebendo os casos da Ouvidoria pelo [Acionamento de ciência].

**Colegiado**:
Um grupo formal do hospital com regimento, composição e reuniões próprias. O Núcleo de Segurança do Paciente é o primeiro e o [Comitê de Conduta] é o segundo; as comissões (prontuário, óbito, ética) vêm depois, na mesma estrutura.
_Evitar_: "comissão" para o Núcleo; cadastro de membros por módulo.

**Participação**:
O papel de uma pessoa num [Colegiado], sempre com vigência (início e fim). Participação vencida não recebe caso nem conta para quórum.
_Evitar_: "membro" sem dizer de quê; apagar participação encerrada (o histórico responde quem compunha o Colegiado em qualquer data).

**Presidência (do Núcleo)**:
A pessoa que coordena o Núcleo e decide a triagem, a designação e as aprovações. "Presidência" e "coordenação" são a mesma pessoa; o [Suplente em exercício] responde nas ausências.
_Evitar_: "coordenação" como papel separado; "secretário" (não existe: a secretaria é da Presidência, com a automação).

**Suplente em exercício**:
O suplente da Presidência dentro de um período de ausência registrado, com início e fim, pela Presidência ou pelo [Acesso pleno ao NSP]. Nesse período ele tem os poderes da Presidência, inclusive a triagem e a identidade de quem notificou. Fora dele, é membro. Na reunião, também é suplente em exercício quem conduz a ata na falta da Presidência.
_Evitar_: suplente com poderes da Presidência sem período registrado; período sem fim.

**Membro do Núcleo**:
Quem tem [Participação] vigente no Núcleo e o [Termo de Adesão] assinado. Sem Termo válido, vê painel, calendário e agenda, e não abre caso, investigação nem ata.
_Evitar_: tratar o cadastrado sem Termo como membro pleno.

**Termo de Adesão**:
O documento que cada membro assina ao entrar no Núcleo ou renovar a vigência: o Termo mais o Regimento vigente na íntegra, num único documento, com um único signatário.
_Evitar_: pedir nova assinatura por revisão só de redação do Regimento.

**Acesso pleno ao NSP**:
A permissão nominal de quem vê e edita tudo no módulo, inclusive a identidade de quem notificou. Hoje é do Diretor Executivo. Não vem do super admin, que só alcança a configuração técnica.
_Evitar_: dar leitura de caso a super admin; excluir registro (todo perfil corrige, com histórico).

**Responsável técnico**:
A pessoa que responde pelo hospital perante a vigilância sanitária, hoje o Diretor Técnico. É uma marca no cadastro do usuário, de uma pessoa só por vez, que o Super admin troca. Assina pela Direção os documentos do Núcleo: o Ato de designação sozinho, o Regimento e o Plano de Segurança do Paciente junto com a Presidência (ADR 0112). Sem ninguém marcado, o envio trava.
_Evitar_: confundir com o [Acesso pleno ao NSP], que é permissão de ver e editar e não assina nada; mandar documento do Núcleo para a Diretoria Executiva.

**Notificação de incidente**:
O relato de um incidente relacionado à assistência, feito por um profissional, com ou sem login, ou vindo de um caso da Ouvidoria. Quem notifica conta o que aconteceu e não classifica.
_Evitar_: "notificação" sozinha (confunde com a [Notificação da Ouvidoria], que é o registro de um e-mail); "denúncia"; nome de paciente no relato.

**Triagem (do Núcleo)**:
A confirmação, pela Presidência, da classificação que o agente sugere para cada [Notificação de incidente]. O agente sempre sugere e a Presidência sempre confirma, ajusta ou encaminha.
_Evitar_: confundir com a [Triagem de e-mail] e com o [Agente de triagem] da Ouvidoria; tratar a sugestão como decisão.

**Faixa (A a E)**:
A prioridade de um caso do Núcleo, da mais grave para a mais leve: A (óbito ou evento que nunca deveria ocorrer), B (dano grave), C (dano moderado), D (dano leve ou sem dano), E (quase erro ou circunstância de risco). Na dúvida entre duas, vale a mais alta.
_Evitar_: "never event" e "near miss" fora de parênteses; rebaixar caso grave.

**Pergunta de esclarecimento**:
Uma das até duas perguntas que o agente faz a quem notificou, depois do registro, quando a resposta pode mudar a classificação. Nunca bloqueia o envio e pode ficar sem resposta.
_Evitar_: perguntar antes de registrar; pergunta que não muda a classificação.

**Registro rápido**:
A [Notificação de incidente] lançada pela Presidência ou por um [Membro do Núcleo] a partir de busca ativa, ronda, reunião rápida de segurança ou auditoria, com relato, setor, data e origem numa tela só.
_Evitar_: usar o registro rápido para notificação espontânea de outra pessoa.

**Encaminhamento (do Núcleo)**:
O envio de uma [Notificação de incidente] a outro canal (Ouvidoria, Canal de Conduta, Segurança do Trabalho, queixa técnica) ou o encerramento como fora de escopo, com destino e motivo de uma frase, depois da confirmação da Presidência. O protocolo do Núcleo é preservado. Um caso pode ter o Núcleo e outro destino ao mesmo tempo. Ao Canal de Conduta nenhum conteúdo é transferido.
_Evitar_: "transferir" ao Canal de Conduta; encaminhar só pela sugestão do agente.

**Prazo legal**:
O prazo que a norma impõe ao hospital: 72 horas corridas para notificar óbito e evento que nunca deveria ocorrer, o 15º dia útil do mês seguinte para os demais incidentes e 60 dias corridos para a complementação. Ninguém o altera pela tela e o relógio dele nunca para.
_Evitar_: editar ou pausar prazo legal; prazo interno mais frouxo que o legal.

**Prazo interno**:
Os demais prazos do Regimento (confirmação a quem notificou, comunicação à Direção, triagem, investigação, reunião de análise), editáveis pela Presidência e pelo [Acesso pleno ao NSP], com histórico. A mudança não retroage. Só o prazo da investigação aceita parar o relógio, com motivo.
_Evitar_: confundir com o [Prazo legal]; mudança que alcança caso já classificado.

**Período de sombra**:
As primeiras semanas de operação, em que toda triagem é confirmada uma a uma e o app mede a concordância entre a sugestão do agente e a decisão da Presidência, eixo por eixo.
_Evitar_: tratar a concordância como nota do agente sem olhar os erros para baixo.

**Aprovação em lote**:
A confirmação de várias triagens das faixas D e E num gesto só, que nasce desligada e só a Diretoria Executiva liga, na pendência "Recalibrar o agente do NSP", com concordância de 90% ou mais nas últimas 4 semanas. Faixas A, B e C nunca vão em lote.
_Evitar_: lote ligado por padrão; lote com caso de faixa C ou mais grave.

**Notificação externa**:
A comunicação de um incidente à vigilância sanitária, com prazo legal. O app prepara o texto e guarda o protocolo; quem envia é a Presidência, no sistema da ANVISA.
_Evitar_: confundir com a [Notificação de incidente]; "parar o relógio" de prazo legal.

## Canal de Conduta

O módulo em que quem trabalha no hospital relata conduta grave e o [Comitê de Conduta] apura o caso até a medida (ADR 0097). Tem um lado público, sem login, e o lado do Comitê.

**Canal de Conduta**:
O canal próprio, sem login, em que quem trabalha no hospital, com qualquer vínculo, relata conduta grave (assédio, discriminação, violência, fraude, desvio) e acompanha o caso por protocolo e código. Pode relatar sem dizer quem é.
_Evitar_: "o Canal" solto em texto que também fala da Ouvidoria (o [Canal aberto] é dela); "denúncia"; tratar aqui salário, escala ou atendimento a paciente.

**Comitê de Conduta**:
O [Colegiado] que trata os casos do [Canal de Conduta]: três membros votantes e um ou dois suplentes, cada um com [Participação] vigente e termo assinado.
_Evitar_: "comissão de ética"; "secretário" (não existe); suplente lendo caso sem convocação.

**Coordenação (do Comitê)**:
O membro que confirma a triagem, conduz o rito rápido, convoca e aprova os retornos. Também decide o [Afastamento cautelar].
_Evitar_: "presidência" (no Canal, Presidente é quem decide a medida); confundir com a [Presidência (do Núcleo)].

**Segundo leitor**:
O membro que vê a mesma fila de triagem da Coordenação e pode contestar a triagem.
_Evitar_: tratar como revisor opcional.

**Triagem (do Comitê)**:
A confirmação, pela Coordenação, do que o agente sugere para cada relato: se é do canal, a categoria e o [Rito].
_Evitar_: confundir com a [Triagem (do Núcleo)], a [Triagem de e-mail] e o [Agente de triagem] da Ouvidoria; tratar a sugestão como decisão.

**Rito**:
O caminho do caso, cada um com prazo próprio contado do envio do relato: Encaminhamento, Rápido, Completo ou Especial.
_Evitar_: "fluxo"; prazo contado da triagem.

**Rota Especial**:
O [Rito] do relato que envolve a Direção, a Presidência ou a família proprietária. Quem apura é o [Grupo Especial], sem nenhum diretor.
_Evitar_: mostrar o caso a quem ele pode envolver; mudar o grupo de um caso aberto.

**Grupo Especial**:
Os três que apuram um caso da [Rota Especial]: o membro não diretor do Comitê, um suplente não diretor e um membro eleito da CIPA.
_Evitar_: diretor no grupo.

**Apurador designado**:
A pessoa de fora do Comitê que apura um caso do rito completo e só vê esse caso.
_Evitar_: dar a ele a lista de casos.

**Citado**:
A pessoa apontada no caso como envolvida. Nunca vê o caso, em nenhum perfil.
_Evitar_: "acusado" antes da apuração; "denunciado".

**Afastamento cautelar**:
O afastamento remunerado de alguém durante o caso, que não é punição. Nunca recai sobre quem relatou.
_Evitar_: tratar como medida disciplinar.

**Termo de declaração**:
O depoimento reduzido a escrito, assinado à caneta pelo depoente e por quem conduziu a conversa.
_Evitar_: "ata do depoimento"; termo com conclusão ou interpretação.

**Ata de deliberação**:
A ata com a decisão do Comitê e o fundamento dela, assinada pelos três votantes.
_Evitar_: confundir com a ata das Reuniões; resumo de quem disse o quê.

**Trava de robustez**:
A lista que precisa estar completa para um caso concluir como procedente.
_Evitar_: concluir como procedente só com relato anônimo.

**Matriz de Consequências**:
A lista fechada de medidas que o Comitê pode recomendar.
_Evitar_: medida fora da lista.

**Trilha do caso**:
A linha do tempo de atos e documentos de um caso do Canal. Não se edita nem se apaga.
_Evitar_: substituir documento (correção entra como nova versão); confundir com a trilha de movimentos da Ouvidoria.

**Recomendação do Comitê**:
O que a Direção lê de um caso: a página de conclusão e a [Ata de deliberação]. O Presidente só lê, e a diretoria executiva registra a decisão sobre a medida.
_Evitar_: "dossiê de uma página"; entregar o [Dossiê do caso] à Direção.

**Dossiê do caso**:
O pacote baixável com tudo do caso, disponível só ao Comitê.
_Evitar_: "dossiê" solto (a Ouvidoria tem o Dossiê dela, e a Direção recebe a [Recomendação do Comitê]).

## Tecnologia (Demandas, Quadro e Entregas)

Desde 02/11/2026 (ADR 0077) a aba Tecnologia era o chat do diretor com o agente, em que o card nascia no GitHub. Só o Super admin vê (ADR 0050). Desde 11/11/2026 (ADR 0084) a aba mostra também o que a Vitta abre pelo terminal ([Origem]), e cada card abre como [Documento do card]; desde 12/11/2026 (ADR 0090) a lista virou o [Quadro]. Desde 25/11/2026 (ADR 0113) a aba é **só informação**, o [Quadro] e as [Entregas]: o [Diretor prototipador] planeja e prototipa no Claude Code dele e abre o [PRD do diretor] no GitHub, a conversa da Vitta com ele é card, comentário e atribuição no GitHub ([Tarefa do diretor]), e o agente saiu da aba para virar o [Assistente do app], de manual e de bug.

**Demanda**:
Um bug ou uma melhoria do app ou da Ana, como o hospital acompanha na aba Tecnologia: o espelho de uma issue-raiz de produto do GitHub (ver [Vínculo com o desenvolvimento]) ou o relato de bug ainda em conversa no [Assistente do app]. Melhoria nasce do [PRD do diretor] ou da Vitta; bug nasce do [Roteiro do bug] ou da Vitta (ver [Origem]). Na tela aparece como um card no [Quadro] (no celular, uma linha da lista), com o título, o selo Bug ou Melhoria e a [Etapa] (ADR 0079). Fica **totalmente apartada** das Pendências de Ata: Demanda é assunto de tecnologia entre o hospital e a Vitta, Pendência é compromisso operacional do hospital.
_Evitar_: chamar de Pendência, tarefa ou ticket; tipo além de bug ou melhoria; Prioridade, Prazo ou raia (aposentados em 02/11/2026); "Demandas TI" (TI é o analista de TI do hospital, um terceiro); Demanda que age (a aba só mostra; quem age é o GitHub).

**Número da Demanda**:
O número próprio de cada [Demanda], sequencial no app e um só para os dois [Projetos] (ADR 0093), que nasce já na conversa Registrada (as que existiam antes ganham número pela ordem de criação). Aparece como "Demanda 42", sem cerquilha, no topo do [Documento do card] e discreto na linha da lista. Todo mundo que vê a Demanda vê o número, inclusive o diretor; é a referência que circula fora do app ("vê a demanda 42"). Vem junto do **Link da Demanda**: o botão "Copiar link" copia "Demanda 42: <título>" e, na linha de baixo, o endereço que abre a aba Tecnologia já naquele card, o mesmo que o sino e o e-mail usam. Fica só no app, sem ir para a issue.
_Evitar_: confundir com o número da issue (`#1571`); cerquilha no Número da Demanda; reaproveitar número de Demanda apagada.

**Assistente do app**:
O agente de IA do app inteiro, num ícone de robô no canto inferior direito, para todo usuário logado (ADR 0113). Abre com sugestões ("Relatar um bug", "Tirar uma dúvida") e o campo livre. Responde dúvida de uso pelo Manual e pelo [Kit de conhecimento], dizendo de onde tirou, e conduz o [Roteiro do bug]. Não planeja melhoria: melhoria é do [PRD do diretor]. Não lê o código e roda sempre no Sonnet 5.5, sem escolha de modelo. Sem nome próprio: nome próprio compete com a Ana.
_Evitar_: nome de persona; agente que cria o card sem o clique; melhoria pelo Assistente; jargão do repositório na conversa (número de issue, label, tabela); Assistente de Tecnologia (o chat da aba, aposentado em 25/11/2026).

**Roteiro do bug**:
O caminho do [Assistente do app] quando a pessoa relata um bug: uma pergunta por vez, no máximo cinco, Onde, O que aconteceu, O que esperava, Como repetir e o print. Sem desafio de negócio. Termina num resumo com o clique de envio e vira uma issue única `type:bug`, com esses rótulos e critérios de aceite. O bug do Super admin nasce `ready-for-agent` (a onda pega sem ninguém da Vitta assumir); o dos demais nasce `needs-triage`, para a Vitta ou o diretor conferirem antes. Só entra o que a pessoa disse; rótulo sem resposta sai "não informado".
_Evitar_: o grill da melhoria num bug; critério de aceite inventado além do que a pessoa descreveu; print no corpo da issue.

**Diretor prototipador**:
O papel do diretor no desenvolvimento desde 25/11/2026 (ADR 0113): planeja e prototipa no Claude Code dele, numa cópia local do app com dados fictícios, e entrega o [PRD do diretor] e o PR rascunho. É colaborador do repositório para receber e passar card, mas não mergeia: o Claude dele nega o merge, e o CI reprova o PR dele até um [Desenvolvedor] assumir. Recebe a [Tarefa do diretor].
_Evitar_: diretor mergeando ou subindo; protótipo contra produção ou com dado real; "desenvolvedor" para o diretor.

**PRD do diretor**:
O card de uma melhoria que o [Diretor prototipador] abre no GitHub pelo Claude Code dele, depois do grill e do protótipo: a issue-raiz com a label `origem:diretor`, no formato do modelo do `/setup-diretor` (bloco "Para o diretor", Problema, Solução, Histórias de usuário, Decisões de negócio, "Ficou em aberto"), com o link do PR rascunho do protótipo e, quando há, do [Arquivo de apoio]. Nasce `needs-triage`; a Vitta faz o Refino, fatia pelo `/to-issues` e desenvolve. Quem grava `CONTEXT.md` e ADR é a sessão da Vitta.
_Evitar_: PRD do diretor escrito no app (o Planejamento da Demanda, aposentado em 25/11/2026); anexo no card público; número de issue dentro do bloco "Para o diretor".

**Tarefa do diretor**:
O card atribuído ao diretor quando um trabalho depende dele, inclusive no meio de um PRD (ADR 0113). É pergunta (`needs-info`) ou coisa a fazer (`ready-for-human`). Ele devolve com um comentário e, quando há, o link do [Arquivo de apoio]: na pergunta, reatribui a quem pediu e o card volta a `ready-for-agent`; na coisa a fazer, fecha o card, e o bloqueio nativo solta as fatias. Fica sabendo pela notificação do GitHub. As "Perguntas para o diretor" do Refino são Tarefas do diretor.
_Evitar_: Pendência (é a Ação da Ata); Pedido da Vitta (aposentado em 25/11/2026); mensagem de WhatsApp para o que é Tarefa do diretor; label própria no lugar do dono.

**Arquivo de apoio**:
A especificação, a planilha ou a memória de cálculo que o diretor quer que a Vitta consulte na hora do código (ADR 0113). Mora no repositório privado `hospital-arquivos`, numa pasta por card; o card, público, leva só o link. Quem grava é o Claude do diretor.
_Evitar_: anexo no card ou no PR públicos; arquivo pelo WhatsApp; arquivo só no `local/` do Mac de quem recebeu.

**Vínculo com o desenvolvimento**:
A ligação de uma Demanda com **uma** issue-raiz do GitHub do [Projeto] dela (o [PRD do diretor], a issue do bug ou a raiz que a Vitta abre), identificada pelo projeto e pelo número da issue (ADR 0093). Nasce quando o espelho vê a issue-raiz de produto (ADR 0113). As fatias são sub-issues dessa raiz e nunca se vinculam uma a uma. Quem vê a Demanda vê a Etapa, O que muda e o número da raiz e de cada parte (ADR 0100), sem depender de ter login do GitHub.
_Evitar_: vincular fatia em vez da raiz; Demanda com mais de uma issue; vínculo digitado por número (aposentado).

**Desenvolvedor**:
Um sócio da Vitta que desenvolve: refina, fatia, implementa e sobe. Não é perfil nem permissão no app, e desde 25/11/2026 (ADR 0113) não muda o que a pessoa vê na aba Tecnologia: o login do GitHub no cadastro serve só para dar nome ao [Responsável]. No GitHub, é quem assume o PR rascunho do diretor e o leva pela [Subida].
_Evitar_: "perfil de tecnologia", "engenheiro de IA"; eixo de permissão próprio para a aba; visão da aba diferente para quem tem GitHub.

**Responsável**:
O dono da issue-raiz no GitHub (o assignee): o card cai na fila dele (ADR 0083). Pode ser um [Desenvolvedor] ou o diretor. O [Diretor prototipador] pode pôr o card que abre no nome de quem vai desenvolver; sem escolha, cai no Pedro. Sempre derivado do GitHub, como a [Etapa], e nunca editado no app.
_Evitar_: dois Responsáveis; card sem Responsável; trocar pelo app; confundir com o Responsável do setor da Ouvidoria.

**Etapa**:
Onde a Demanda está na entrega, em palavras do diretor, sempre derivada do GitHub e nunca editada à mão: **Registrada** (conversa sem card), **Em análise**, **Planejada**, **Em desenvolvimento**, **Entregue**, **Em produção** e **Não será feita**. Num PRD, vem com "X de Y partes entregues". **Entregue** é o fechamento da issue (o merge); **Em produção** é a [Subida] que levou aquele fechamento ao ar, com a versão ("Em produção desde v0.165.0"; ADR 0069). Um PR aberto já conta como Em desenvolvimento. Na [Ana], a última Etapa é Entregue, porque ela não tem Subida com versão (ADR 0093). Num PRD, depois que a primeira parte começa, a Demanda fica Em desenvolvimento até a raiz fechar, mesmo entre uma onda e outra, sem voltar para Planejada (ADR 0092). É o que a lista lateral mostra em cada conversa.
_Evitar_: Etapa digitada; Entregue como "deploy confirmado" (é o fechamento; o deploy é Em produção).

**Card de implantação**:
O card do que o hospital faz para pôr uma entrega em uso, depois do código: teste de aceite, configuração, abertura, treinamento (ADRs 0111 e 0113). Tem a label `implantacao`, não segura nenhuma fatia e é atribuído ao diretor, que delega e fecha quando o hospital terminou. O PRD fecha com a última fatia de código, sem esperar a implantação: a Demanda fica Em produção, e o [Documento do card] mostra a seção Implantação ("Implantação 1 de 3"), também como selo no [Quadro], lendo esses cards. Problema achado na implantação vira bug novo, sem reabrir o PRD.
_Evitar_: Pendência (é a Ação da Ata); card que segura código como Card de implantação; reabrir o PRD por problema achado na implantação; Pedido de implantação (o registro do app, aposentado em 25/11/2026).

**Subida**:
O passo que leva PRs verdes até produção (`fechar_onda.py`): merge pela API, versão, build, health, registro. Antes chamado de rabo.

**Portão do push**:
As conferências rápidas do CI que rodam no Mac antes de todo push de branch: número e recibo da migration, travessão nos templates, `uv.lock`, `ruff` e o teste do `encoding="utf-8"`. Reprovou, o push para e o PR nem chega ao CI. A suíte inteira do pytest fica só com o CI.
_Evitar_: pré-CI; hook (é o mecanismo, não o nome); suíte inteira no portão.

**O que muda**:
O que a entrega acrescenta para quem pediu, em linguagem de leigo, vindo do bloco "Para o diretor" da issue e **nunca digitado no app** (ADR 0054, decisão 7). Aparece como uma seção do [Documento do card]; sem o bloco, "Descrição em preparação". Até cinco tópicos (ADR 0084).
_Evitar_: título de parte, número de issue, link ou label na tela do diretor; texto corrido com a fala do diretor transcrita.

**Origem**:
De onde a Demanda veio (ADRs 0084 e 0113): **Pedido do diretor**, quando a issue-raiz tem a label `origem:diretor` ([PRD do diretor]); **Relato no app**, quando o bug nasceu do [Roteiro do bug]; ou **Vitta**, quando a issue-raiz do app (PRD ou bug) foi aberta pelo terminal. Aparece como selo na lista e é um dos filtros. Ferramenta e skills (`.claude/`, `tools/`, `docs/`) não viram Demanda.
_Evitar_: label manual para mostrar ao diretor; Demanda para issue de ferramenta; parte (fatia) virando Demanda.

**Projeto**:
De qual sistema do hospital a Demanda é (ADR 0093): **Aplicativo do Hospital**, este app, ou **Ana**, a agente de atendimento, com repositório privado próprio. Da Ana viram Demanda só as raízes de produto (PRD ou issue solta, sem as partes e sem as de ferramenta), sempre da [Origem] Vitta. O [Roteiro do bug] cria card apenas no Aplicativo do Hospital. Aparece como selo no card e é um filtro do [Quadro] e das [Entregas].
_Evitar_: "Produto" (é o módulo do kit de conhecimento) ou "Sistema"; criar card da Ana pelo [Assistente do app]; Demanda da Ana Em produção; levar conteúdo do repositório da Ana para o deste app, que é público.

**Documento do card**:
O que abre quando se clica numa Demanda (ADR 0084): seções fixas, Em uma frase, [O que muda] (até cinco tópicos), Partes (agrupadas por [Onda], cada uma com o número, a Etapa, as datas e o que a trava), [Demonstração] e Implantação, quando há [Card de implantação], e Datas (criado, entregue, em produção). É lido do bloco "Para o diretor" da issue, que tem formato fixo e limite de tamanho tanto no [PRD do diretor] quanto no `/to-prd` do terminal. Nunca digitado no app.
_Evitar_: texto corrido; documento editável à mão; seção sem limite.

**Onda**:
No [Documento do card], o grupo de partes de uma Demanda que entram juntas (ADR 0100). Calculada pelas dependências entre as partes: a Onda 1 não espera nenhuma outra parte da Demanda, e cada parte fica uma Onda depois da maior Onda das que ela espera, contando os bloqueios já resolvidos, para a sequência não mudar quando uma parte fecha. Enquanto uma bloqueadora está aberta, a parte diz "Espera a #1884" (ou "de outro pedido", quando a bloqueadora é de outra Demanda). No fluxo de desenvolvimento é o mesmo lote que uma sessão da onda pega.
_Evitar_: Onda digitada ou lida do texto "Ondas previstas" do PRD; confundir com [Etapa], que é onde a Demanda está.

**Quadro**:
A tela principal da aba Tecnologia (ADR 0090): os cards das Demandas em cinco colunas pela [Etapa], Registrada, Em análise, Planejada, Em desenvolvimento e Entregue (que junta Entregue e Em produção dos últimos 30 dias e leva às [Entregas]), com a barra de filtros em cima. Só leitura: a coluna é a Etapa que vem do GitHub, e ninguém arrasta card. O card abre num painel à direita com o [Documento do card]. Não tem botão de pedido novo (ADR 0113). No celular continua a lista.
_Evitar_: arrastar card entre colunas; coluna de Estado, Prioridade ou Prazo (o Quadro aposentado em 02/11/2026); raia por pessoa; confundir com as [Entregas], o retrato do que já foi entregue.

**Entregas**:
A segunda aba da Tecnologia (ADR 0084, emendada pela 0092): o ritmo de pedidos e entregas por semana e o que cada entrega fez. Em cima, quantos pedidos chegaram e quantas entregas saíram nas últimas 4 semanas e o gráfico das últimas 12; embaixo, as entregas agrupadas por semana, cada uma com o [Tamanho da entrega], a versão, o [O que muda] e a [Demonstração], que abrem ao passar o mouse. Contada por card. Entram todas as [Origens], e todos veem a mesma tela. Ninguém move nada ali.
_Evitar_: chamar de Painel (aposentado em 02/11/2026) ou de [Quadro]; contar por parte; mover card pela aba; tempo por Etapa, prazo de parado ou números por pessoa (a aba mostra o ritmo, não cobra quem entrega).

**Tamanho da entrega**:
P, M ou G, pelo número de partes da Demanda: até 1 parte é P, de 2 a 5 é M, 6 ou mais é G (ADR 0092). Calculado, nunca estimado nem digitado. Todo bug é P.
_Evitar_: story points; tamanho escolhido à mão; tamanho pelo tempo que a entrega levou.

**Ajuste do plano**:
A sub-issue `ready-for-human` do Pedro na issue-raiz de uma Demanda, que diz o que muda em cada card a partir do que o diretor pediu e trava as fatias iniciais ainda não começadas até o plano ser revisto (ADR 0108). Quem revê é o agente, num grill em lote que segue as próprias recomendações: ele ajusta o PRD e os cards, fecha o Ajuste e monta as ondas. A única parada do Pedro é o "Posso lançar?". Nasce do Validar da [Apresentação do PRD] com observação, que grava só no GitHub (ADR 0113). O texto é a observação do diretor, como ele escreveu na página, sem passar pelo app nem pela IA.
_Evitar_: dado de paciente na issue; abrir o Ajuste sem travar as fatias iniciais.

**Apresentação do PRD**:
A página na Vercel (`https://planos-hsm.vercel.app/<PRD>`) em que o diretor lê o plano de um PRD, Parte por Parte, antes do trabalho começar, e valida pelo link do e-mail, que leva o código de validação. A página mostra a qualquer pessoa o estado real lido do GitHub (validado, com a data e a observação, ou para validar), e a validação só vale para a versão que ele viu: republicar volta a pedir validação. O PRD guarda o marcador `<!-- apresentacao: <url> -->`, e o card no [Quadro] e no [Documento do card] ganha o atalho "Ver o plano", sem o código (ADR 0108).
_Evitar_: estado guardado só no navegador de quem validou; o código de validação no app ou no GitHub; confundir com a [Demonstração], que mostra o que já foi entregue.

**Demonstração**:
A página na Vercel do que um card entregue mudou, feita pelo `/divulgar` (ADR 0045; sem vídeo desde que o Estúdio de Vídeos saiu) numa sessão aberta pelo botão "Gerar demonstração" do PedroOS, sempre por clique do Pedro (ADR 0084). A sessão grava na issue-raiz o marcador `<!-- demonstracao: <url> -->`, o webhook leva o link ao card e o card ganha o selo "Tem demonstração". Nem todo card tem. Quando fica pronta, o diretor recebe aviso por sino e e-mail, como recebe quando o card entra Em produção, com o resumo montado do [Documento do card], sem IA.
_Evitar_: vídeo gerado pela Subida; link digitado no app; resumo do aviso escrito por IA.

**Anexo da Demanda**:
O print de tela que a pessoa manda ao relatar um bug no [Assistente do app], guardado junto da Demanda (ADR 0069). Vive só no app, em guarda privada, e **nunca vai para o GitHub**: o repositório é público. A issue ganha só a frase de contagem ("Anexos: 2 imagens na Demanda"); quem desenvolve busca os arquivos pelo app. O binário é apagado 30 dias depois de Em produção ou quando a issue fecha como Não será feita (ADR 0077); fica o registro de que existiu, marcado apagado. Documento do diretor para a melhoria não é Anexo da Demanda: é [Arquivo de apoio].
_Evitar_: imagem no corpo ou no comentário da issue; link assinado na issue; binário parado na guarda depois do prazo; confundir com o anexo da Ata Guiada, que é efêmero.

**Kit de conhecimento**:
O conjunto de textos que o [Assistente do app] recebe a cada conversa, junto do Manual: um arquivo por módulo (Ana, Integração Ana x MV, Reuniões, Ouvidoria, POPs, Contas médicas, Central de Comando, Site, Infra) mais um sobre a própria aba Tecnologia, cada um com a seção **"O que já foi decidido"**. Escrito para o leitor diretor, em linguagem de uso, sem número de issue, label, nome de tabela ou vocabulário interno. Vive no código do backend e viaja no deploy; é **curado por gente**: mudou o comportamento de um módulo, o arquivo dele muda no mesmo PR. É a língua em que o agente fala, e o que ele sabe da casa: ele não lê o código (ADR 0113).
_Evitar_: gerar o kit por script a partir do glossário; busca vetorial; kit desatualizado (vira agente mentindo).

**Aposentados em 02/11/2026** (ADR 0077): Tipo da Demanda (os sete), Produto com dono, Estado da Demanda, Prioridade, Prazo, o Quadro de Estado manual (voltou com outro sentido na ADR 0090), Painel, a Conversa espelhada com a issue, o formulário à mão, o Roteiro por Tipo e o botão "Planejar com a IA". Quem ler esses nomes em ADR antiga (0050, 0054, 0056, 0069, 0075) está lendo histórico.

**Aposentados em 25/11/2026** (ADR 0113): o Assistente de Tecnologia como chat da aba, o Planejamento da Demanda, o "Criar o card" e o Envio falhou, a Revisão com o código de hoje, o Apagar a Demanda, a escolha de modelo por Demanda, a Conversa da Demanda, a Mensagem pelo terminal, o Envio aos desenvolvedores, o Pedido da Vitta (Pergunta da Vitta, Passo a passo da Vitta e Pedido de implantação), a lista Esperando você e o Me explique. Quem ler esses nomes nas ADRs 0077 a 0111 está lendo histórico.

## Central de Comando (números do ecossistema digital)

**Central de Comando**:
O lugar da diretoria para acompanhar, e no futuro operar, o ecossistema digital do hospital, em português claro e na identidade do app. Hoje são os **números**: o site (Google Analytics) e o Instagram, sempre somente leitura. O que ainda não existe (Blog, Editor do Site, Mapa de Calor, Google Ads) aparece como [O que vem por aí], nunca como item de menu vazio. Vive na área de Administração, numa seção própria do menu, e **só o Super admin vê**, sem eixo de permissão próprio: quem precisa ver precisa ser Super admin (mesma troca da aba Tecnologia, ADR 0050). Princípio que atravessa tudo: **honestidade do dado**, o que não é medido aparece como não medido, nunca como zero nem como número inventado.
_Evitar_: "dashboard de marketing", "BI"; definir a Central como somente leitura (os números são, o Blog não será); `perfil_central` ou qualquer papel novo só para ela; número estimado no lugar de dado que a fonte não entrega.

**Conector**:
A ligação que a pessoa adiciona no próprio Claude, no celular ou no computador, para perguntar sobre os dados do app. Só lê. Um só, com gate por ferramenta: as da [Central de Comando] são do Super admin; as de Reuniões e da Ouvidoria são só de quem tem `diretoria_executiva` no [Perfil da Ouvidoria] (ADR 0085). Entrega o que a tela de quem conectou entrega, com a mesma regra de atraso e de prazo da tela.
_Evitar_: "MCP" para o diretor (é o nome técnico); "integração"; um Conector por módulo.

**O que vem por aí**:
O bloco no pé da Visão Geral da [Central de Comando] que conta à diretoria o que ainda vai nascer ali, em linguagem de leigo. É o único lugar onde funcionalidade futura aparece: o menu só lista o que funciona.
_Evitar_: item de menu "em breve"; tela inteira só para dizer que algo não existe; prometer data.

**Site**:
O site institucional do hospital no domínio oficial, fonte dos números do Google na [Central de Comando]. É um só: a distinção antiga entre "Site Oficial" e "Site Novo" morreu quando o novo assumiu o domínio.
_Evitar_: "Site Novo", "Site Oficial (atual)"; confundir com o app (o app é de uso interno, o Site é público).

**Visitantes**:
Quantas **pessoas diferentes** acessaram o [Site] no período; a mesma pessoa em várias idas conta uma vez. É o número-manchete da Central e bate de propósito com os "usuários ativos" que o Google mostra por padrão, para quem for conferir.
_Evitar_: "acessos", "usuários", "sessões" como sinônimo.

**Visita**:
Uma **ida** ao [Site]. Um Visitante pode ter várias Visitas. Só aparece onde a conta é por ida.
_Evitar_: somar Visitas e chamar de Visitantes; "sessão" na tela.

**Área do site**:
Um grupo de páginas do [Site] que fala de um mesmo serviço do hospital (Maternidade, Emergência 24h, Centro de Imagem, Centro Médico, Laboratório), somadas para dizer qual parte do site atrai mais gente. O agrupamento é interpretação da Central: o Google só conhece páginas soltas. Catálogo fechado; só entra serviço que tem página própria. O número fala do **site**, não da procura real pelo serviço.
_Evitar_: "Braço" (jargão do manual de marca, nome antigo); chamar de [Setor] ou ligar à taxonomia de Setores (Setor é o organograma de quem trabalha no hospital, inclui quem não tem página; nome igual é coincidência, não vínculo); ler o ranking como demanda do serviço.

**Origem do público**:
De onde veio quem chegou ao [Site]: busca, acesso direto, redes sociais, indicação de outro site. Sempre com o qualificador "do público".
_Evitar_: "origem" solto ou "canal" (o [Canal de origem] é da Ouvidoria e diz por onde a manifestação chegou, outro assunto).

**Não identificado** / **Outros**:
Os dois rótulos gentis para o que o Google não classificou: "Não identificado" para origem desconhecida, "Outros" para a soma das fatias pequenas. A tela nunca mostra o termo técnico cru da fonte.
_Evitar_: `(not set)`, `(other)`, "desconhecido".

**Contatos gerados**:
Quantas vezes alguém, no [Site], clicou para falar com o hospital (WhatsApp, Fale Conosco). Cada canal de contato tem um estado honesto: **medido**, **em construção** (o Site ainda não avisa quando acontece) ou **não medido**.
_Evitar_: chamar de agendamento ou de lead; mostrar zero para canal que não é medido.

**Ao vivo**:
Quantas pessoas estão no [Site] **neste momento**. É o único número em tempo real da Central; vem de uma fonte separada e se renova sozinho a cada poucos segundos.
_Evitar_: confundir com [Atualizar agora]; guardar esse número.

**Atualizar agora**:
A ação que manda a Central buscar números novos na hora, sem esperar a renovação automática de hora em hora. Vale para os números de tendência, não para o [Ao vivo]. Se a fonte falhar, a tela mantém o último número bom e avisa que não conseguiu atualizar.
_Evitar_: zerar a tela quando a fonte falha; esconder de quando é o número.

**Alcance**:
Quantas **contas diferentes** viram o conteúdo do Instagram do hospital no período. É o "Visitantes" do Instagram: conta pessoas.
_Evitar_: "impressões"; somar com [Visualizações].

**Visualizações**:
Quantas **vezes** o conteúdo do Instagram foi exibido no período; a mesma pessoa conta várias vezes. É a "Visita" do Instagram.
_Evitar_: "impressões"; tratar como pessoas.

**Seguidores**:
Total de contas que seguem o perfil **agora**. É estoque, não fluxo: não muda ao trocar o período. O que varia por período é o **crescimento** (quem chegou menos quem saiu).
_Evitar_: variação percentual de Seguidores por período (o que se compara é o crescimento).

**Interações**:
A soma de curtidas, comentários, salvamentos e compartilhamentos no período. É o número-manchete do engajamento e o critério das [Principais publicações]. O lado "pessoas" do mesmo assunto são as **Contas que engajaram**.
_Evitar_: "engajamento" como número único sem dizer se são ações ou pessoas.

**Principais publicações**:
As publicações permanentes (imagem, carrossel, Reels, vídeo) com mais [Interações] no período.
_Evitar_: "top posts"; incluir Stories.

**Objetivo**:
Uma direção que a diretoria quer para o ecossistema digital ("Crescer no Instagram", "Gerar mais contatos"), vista por uma lente própria: os números que importam para ela e **sugestões** que sempre dizem o porquê, ou seja, qual dado as disparou. Catálogo fechado; Objetivo sem dado ainda aparece como em construção. Não tem alvo numérico.
_Evitar_: chamar de meta (o app já usa "metas" no menu de Reuniões, e "Meta" é também o nome da empresa dona do Instagram: nesta seção a empresa não é citada, diz-se "Instagram"); sugestão sem o dado que a justifica.

## Contas médicas

**Envio**:
O ato de subir para o app os PDFs da Conta e do Prontuário exportados do MV. Quem envia fica gravado no envio (`cm_envio.usuario_id`), não na conta. Qualquer perfil com "Enviar contas" envia, inclusive o [Apoio ao faturamento]. Quem envia acompanha em "Meus envios" o que ainda não ficou pronto (falta o outro arquivo, processando, erro) e recebe o aviso de envio processado (ADR 0073).
_Evitar_: tratar quem enviou como dono da conta; mandar a faturista resolver arquivo que falta.

**Fila de contas**:
A lista comum das contas com Guia pronto que ninguém pegou, em ordem de envio, nunca por valor. Toda faturista vê a mesma Fila. Quem analisa vê também as contas em análise e as concluídas de todas, cada uma com o nome de quem está com ela, e filtra por "Minhas" (as que ela pegou); a conta de outra faturista aparece na lista e na busca, mas ela não abre. Conta que espera arquivo, processa ou deu erro não entra na Fila (ADR 0073, que emendou a decisão 10 da ADR 0070; a visão das contas das colegas é do grill de 18/11/2026).
_Evitar_: fila por faturista; mostrar na Fila conta sem Guia; esconder da faturista com quem está a conta que ela procura.

**Puxar a conta**:
Abrir o Guia de uma conta livre da [Fila de contas]: nesse clique a conta passa a ser da faturista, e só um clique ganha. Na tela, o botão da conta livre diz "Pegar", para ninguém virar dona sem querer. O "Concluir e abrir a próxima" puxa a primeira livre. A faturista pode **devolver à fila** a conta que puxou e não vai terminar, e a coordenação devolve a de qualquer uma; as marcações ficam.
_Evitar_: distribuir conta antes do trabalho; duas faturistas na mesma conta.

**Faturista da conta**:
Quem puxou a conta e a analisa (`cm_conta.faturista_id`). É dela o Retorno da Validação e é ela quem conta na Produção do Painel. Não é quem enviou.
_Evitar_: contar produção para quem enviou.

**Apoio ao faturamento**:
Perfil de Contas médicas que só envia: sobe Conta e Prontuário, vê "Meus envios", não puxa conta nem aparece na Produção. Nasceu para a secretária do diretor (ADR 0073); o nome de tela espera a confirmação dele.

## Texto e comunicação

**Manual do usuário**:
O manual dentro do app (ADR 0094), aberto pelo item Manual no rodapé da barra lateral, com duas abas. **Aplicativo do Hospital**: uma página por módulo, com as tarefas em passo a passo, prints de tela com dados fictícios e fluxogramas; cada pessoa vê só os módulos que acessa. **Ana**: o [Retrato da Ana], só para Super admin. Sem vídeo. Muda junto com a tela: todo PRD com tela tem uma **Fatia de manual**, só com texto, print e fluxograma.
_Evitar_: vídeo no manual; site fora do app; print com dado real; página de módulo que a pessoa não acessa; o manual aposentado em 05/11/2026 (o site na Vercel com vídeo por módulo, ADR 0078).

**Régua de texto**:
A passagem obrigatória de todo texto que alguém de fora vai ler (texto de tela, PDF, hover do Hospital OS, mensagem, legenda de vídeo, página de divulgação) pela skill `humanizer` antes de gravar, mais o lint que trava no CI os cacoetes que dão para pegar por regex (ADR 0071). A voz é a do canal: a amostra aprovada manda no tom, a skill só tira o cacoete.
_Evitar_: "não é X, é Y"; fecho de uma linha que repete o parágrafo; tríade forçada; rótulo em negrito em tudo; texto para fora gravado sem a passagem.

**Caixa alta**:
Texto todo em letra maiúscula, aplicado só na exibição (CSS na tela, `text-transform` nos PDFs, filtro `upper` no título dos e-mails), nunca gravado assim no banco (ADR 0080). Vale para o Texto curto que vem pronto no aplicativo e para os títulos escritos pela IA; o que a equipe digita aparece como foi escrito.
_Evitar_: gravar o texto em maiúscula; assunto de e-mail em caixa alta.

**Texto curto**:
O texto que fica em Caixa alta, definido pelo tipo de elemento e não pelo número de palavras: item de menu, título e subtítulo, botão, aba, nome de campo, cabeçalho de coluna e etiqueta de situação.
_Evitar_: decidir pelo tamanho da frase.

**Texto corrido**:
O texto com maiúscula e minúscula: parágrafo, aviso (toast), mensagem de erro, texto de ajuda, placeholder, corpo de diálogo, o texto de cada aviso do sino e a conversa da Tecnologia.

**Vídeo de percepção de valor**:
O vídeo de uma entrega (PRD) feito para o diretor ver o sistema funcionando (ADR 0026, ADR 0045): a unidade é o que mudou, não a tarefa.

## Diálogo de exemplo

> **Dev:** Como o Colaborador resolve a Pendência?
> **Facilitador:** Ele entra no app, abre a Pendência e marca como concluída com uma Anotação. Fecha na hora, sem eu validar. Quem nunca entrou faz o mesmo pelo link pessoal do e-mail de segunda.
> **Dev:** E se a Ata sai errada depois de PROCESSANDO?
> **Facilitador:** Ela fica em AGUARDANDO_VALIDACAO. Eu peço uma correção (vai pra CORRIGINDO), a IA reescreve, e só então eu aprovo — aí cria o Envelope na ClickSign e vai pra AGUARDANDO_ASSINATURA.
> **Dev:** E quando a reunião é só operacional, sem precisar de assinatura?
> **Facilitador:** Aí eu clico em "Finalizar sem assinatura": as Pendências saem na hora e a Ata fica APROVADA, sem passar pelo ClickSign. É definitivo — não dá pra assinar depois.
> **Dev:** E se a reunião nem teve Transcrição — foi um bate-papo rápido?
> **Facilitador:** Aí eu faço uma **Ata Guiada**: converso com o agente (ou dito por voz), ele monta um resumo e o quadro de ações perguntando quem faz o quê e até quando. Reviso e finalizo sem assinatura — mesmas Pendências, sem Transcrição nem PDF.
> **Dev:** Se o prazo de uma Pendência estoura?
> **Facilitador:** Ela fica atrasada, com o prazo vencido à vista, até o responsável concluir ou fazer uma Repactuação com justificativa. Repactuar depois de vencer conta como atraso dele.
