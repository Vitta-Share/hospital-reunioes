# Protótipo 2B de todas as telas: decisões do grill

Grill de 27/11/2026. O Pedro aceitou todas as recomendações. Base: o Início do designer (novidades-eight.vercel.app, modelo 2B), copiado sem mudança. O protótipo mora na branch `prototype/front-2b-todas-as-telas` e nunca entra na main.

Para rodar: `python3 -m http.server 8830 --directory docs/comunicacao/prototipos/front-2b` e abrir http://127.0.0.1:8830/#inicio. O link "Todas as telas" no topo lista as 74 telas, e o "Ver como" troca o perfil (Facilitadora, Colaborador, Secretária, Faturista, Super admin).

## Fundação (vale para todas as telas)

1. **Cabeçalho de módulo.** Toda capa de módulo usa o herói do Início em versão baixa: foto com véu, frase escrita por regra a partir dos números, e 3 ou 4 cartões clicáveis subindo sobre a foto.
2. **Subtelas em abas do módulo.** Ficam logo abaixo do resumo, sempre visíveis e com contador. O menu lateral continua curto, como o designer desenhou. Só o NSP mantém o submenu, que já era do desenho dele.
3. **Gaveta ou página.** Item leve abre numa gaveta à direita, sem sair da lista: Pendência, Reunião no Calendário, ficha de POP, caso da Ouvidoria do setor, Documento do card. Objeto pesado tem página própria, com etapas no topo e "O que fazer agora" ao lado: Reunião, Ata Guiada, Dossiê, caso do NSP, caso do Comitê, Mesa de trabalho e Elaboração de POP.
4. **Ações.** Cada linha tem uma ação principal escura e as outras no menu de três pontos. Nada fica escondido no hover. Toda ação destrutiva fica separada, em vermelho, e pede confirmação num modal do app (nunca o confirm() do navegador). Todo resultado aparece num aviso flutuante.
5. **Busca Ctrl+K.** Acha telas, pessoas, Reuniões, itens da fila e protocolos.
6. **Pendências.** Gaveta com as ações no rodapé e uma linha do tempo única, com histórico, comentários e @menção. No Quadro o arraste funciona e pede só a anotação daquela mudança. Lista, Quadro e Concluídas dividem os mesmos filtros.
7. **Lista de Reuniões.** Tela nova, com busca e os grupos Precisam de você, Próximas e Já aconteceram. O Calendário ganha as visões Mês, Semana e Lista.
8. **Números pessoais.** Ficam só no Início. O Perfil vira a conta, e o Dashboard mostra o hospital e os setores.
9. **"Ver como" e "Todas as telas".** Ficam no protótipo enquanto ele serve para revisão.
10. **Onde mora.** Na branch descartável, com um link na Vercel para o designer.
11a. **Uma foto do site por módulo.** O herói de cada módulo usa uma foto do próprio hospitalsaomatheus.com.br, escolhida pelo assunto, e o Início fica com a foto do designer. Meu trabalho: posto de enfermagem. Reuniões: conversa à mesa. POPs: registro na prancheta no centro cirúrgico. Ouvidoria: recepção. Segurança do Paciente: leito do CTI. Contas médicas: médico preenchendo documento. Comitê de Conduta: recepção sem pessoas. Administração: corredor. Central e Tecnologia: tomógrafo. Secretaria: consultório. Conta: quarto. Telas públicas: alta com a família (Ouvidoria), emergência (Notificar) e recepção (Conduta e links). As fotos ficam em `assets/modulos/`, e a regra fica em `N.fotoDaTela` (perfis.js).

11b. **Filtros em dropdown** (pedido do Pedro, 27/11). Todo filtro usa o dropdown dos botões "Todas" e "Prioridade" do Início (`N.filtro`). Valor exclusivo (período, "De quem", papel, responsável, situação ativa ou arquivada) usa seleção única. Recorte por categoria (estado, situação, faixa, rito, setor, operadora, tipo, origem, projeto, gravidade, ponto, nota) usa seleção múltipla, com caixa de marcar e "Limpar a seleção", e nada marcado vale como todos. Forma de ver (Mês, Semana, Lista; Composição de hoje ou passada) usa o seletor segmentado do designer. Grupo que é aba com contador usa as abas sublinhadas do Início.
11c. **Hover.** Nenhuma ação depende do hover. Onde ajuda decidir antes de clicar, um cartão de prévia acompanha o ponteiro (`data-previa`): Reuniões no Calendário e na lista, setores do Dashboard, casos da Fila e do NSP, contas da Esteira, cards da Tecnologia, Colaboradores. Ele também aparece no foco do teclado. No Comitê, a prévia mostra só metadados, nunca o relato. Linhas e cartões clicáveis mudam de fundo ou de borda no hover, e o dia do Calendário mostra "+ Agendar".

11d. **O cartão do Calendário é o de hoje, com a assinatura.** No hover, o cartão da Reunião mostra o mesmo que o app de hoje: título, situação e tipo, série, horário, objetivo, Participantes com o Facilitador marcado e "+N mais". Mantém também os links "Ver detalhe" e "Excluir toda a série recorrente". Passa a mostrar ainda a data e a hora em que a Ata foi assinada por todos (ou aprovada sem assinatura, ou quantos já assinaram e quando foi a última assinatura), com o "PDF assinado". O cartão fica preso ao lado da Reunião e aceita clique. A data da assinatura aparece também no bloco verde da página da Reunião, na gaveta do Calendário e, por pessoa, na aba Signatários.

## Reuniões e metas

11. Cada linha da lista tem um botão que muda com o estado: Validar a Ata, Casar os nomes, Assinar, Começar a Ata ou Abrir.
12. A Resolução de nomes acontece numa aba da Reunião, com a Ata ao lado.
13. Reuniões e metas não tem abas de módulo, porque o menu já leva às três telas.
14. Ao concluir, a Ata Guiada volta para a Reunião, já na aba do Quadro de atribuições.
15. Os cartões do Dashboard mostram a variação da semana num texto curto colorido.

## POPs

16. Uma tabela só, com chips de estado, e o que está com a pessoa sobe para o topo.
17. Na Elaboração, o POP vivo e a conversa ficam lado a lado, e a correção pode ser apontada por seção, como na Ata Guiada.

## Ouvidoria

18. Sete abas fixas do módulo, com contador. Acaba o botão "Atalhos".
19. O Dossiê ganha abas internas e "O que fazer agora" fixo ao lado.
20. A Facilitadora vê a "Ouvidoria do setor" e responde numa gaveta.
21. A ação principal do card na Fila muda com o estado: Validar, Cobrar, Encerrar ou Arquivar.

## Segurança do Paciente e Notificar

22. Na fila de triagem, os casos graves ficam fixos no topo, e o resto segue do mais antigo para o mais novo.
23. Para confirmar a triagem de um caso grave, cada campo tem uma caixa "Conferi", e o Confirmar só libera depois de todas marcadas.
24. A Recalibração vira um cartão em Configuração. A pendência aponta para ele.
25. O Notificar logado é uma página com herói e 4 passos, dentro do app, com a identificação já preenchida.

## Contas médicas

26. A Mesa de trabalho é tela de foco: não tem as abas do módulo, só "Voltar à Esteira".
27. O Item da vez fica num cartão fixo à direita da lista.
28. A Validação é aba do módulo e, no menu, fica dentro de Operadoras.
29. A Mesa tem os atalhos de teclado I (inclui), N (não se aplica) e J (próximo), com legenda.
30. A busca da Esteira acha a conta em qualquer etapa e diz onde ela está e com quem.

## Comitê de Conduta

31. O Guia é uma aba fixa do módulo, e cada caso tem o link "Como funciona o rito X".
32. O caso tem as etapas do rito no topo, abas internas e a ação da etapa ao lado.
33. A lista mostra só metadados. O relato fica numa aba própria, e cada leitura entra na Trilha do caso.
34. As ações raras ficam em botões de contorno na coluna lateral. O impedimento fica separado, em vermelho.
35. Na primeira entrada, um modal com 5 cartões e "Não mostrar de novo".

## Administração

36. Na lista de Colaboradores, Editar fica visível e o resto vai para os três pontos. Desativar fica separado, em vermelho, e pede motivo.
37. A ficha do Colaborador tem um seletor de papel por módulo e o Super admin como interruptor. A faixa interna (role) aparece só como etiqueta discreta.
38. Acertos de setor vira uma aba de Cadastros, com contador.
39. O período da Central de Comando são chips de 7, 28 e 90 dias, que valem para todas as abas.
40. O Documento do card da Tecnologia abre sempre numa gaveta larga, no Quadro e nas Entregas.
41. O "O que muda" das Entregas abre e fecha por clique, dentro da linha.

## Telas públicas

42. Todo fluxo público abre com uma tela de entrada antes do passo 1.
43. Um acompanhamento só para Ouvidoria e NSP. O tipo sai do protocolo.
44. O login tem a faixa "Não trabalha no hospital?", com os quatro canais públicos.
45. O link do Responsável do setor continua valendo para todos, com "Entrar no app" no topo e um convite no recibo.
46. Nas Pendências pelo link, Concluir, Pedir novo prazo e Só anotar ficam visíveis em cada Pendência.

## Próximo passo

É a porta A (PRD e fatias): o trabalho muda o que se vê em todos os módulos e não cabe numa sessão. Quando o designer devolver o desenho das telas, o caminho é `/to-prd` com este arquivo e o link do protótipo, e depois `/to-issues`, módulo por módulo.
