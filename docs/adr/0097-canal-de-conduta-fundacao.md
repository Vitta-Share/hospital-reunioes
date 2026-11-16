---
status: accepted
amends: 0082, 0088, 0095
---

# Canal de Conduta: fundação, sigilo do conteúdo e exceções de IA

Decisão do Pedro no Refino de 16/11/2026 (grill no terminal, duas rodadas), sobre a Demanda #1786 e a especificação da Diretoria Executiva de 15/11/2026 (módulo Canal de Conduta, versão 1.0). A especificação fica no anexo da Demanda, fora do repositório. As 39 decisões de negócio do diretor estão na issue e valem como premissa. Aqui ficam as decisões técnicas e as regras antigas que elas mudam.

## Decisões

1. **O conteúdo dos casos é cifrado na aplicação, com a chave no Coolify.** Relato, mensagens, depoimentos, votos e nomes ficam cifrados em tabelas próprias do módulo (`conduta_*`). O que serve a lista e prazo (rito, etapa, datas, categoria) fica em claro. A cifra protege backup, dump e a leitura pelo Studio. Não protege de quem opera o deploy, que alcança a chave. A promessa da página pública de que a Vitta não lê se apoia no aditivo de sigilo que o diretor exigiu antes do lançamento, e esse limite é dito a ele por escrito.

2. **Os arquivos do caso também são cifrados e só saem pelo backend.** Anexo, áudio de depoimento e PDF assinado ficam em bucket próprio, cifrados, sem URL assinada: o backend confere o acesso, decifra e entrega. O áudio aceita até 300 MB, para caber um depoimento de duas horas.

3. **O Comitê de Conduta é o segundo Colegiado (emenda a decisão 3 da ADR 0095).** Usa as mesmas tabelas de Colegiado e Participação, com o papel novo `coordenacao`. O serviço de membros e de termo, hoje preso ao Núcleo, passa a receber o Colegiado como parâmetro, numa fatia de preparação. Quem cadastra membros tem um perfil nominal do módulo no cadastro da pessoa. Dar ou tirar esse perfil avisa o Comitê e entra na trilha, como toda inclusão ou saída de membro.

4. **Um portão único de acesso ao caso.** Toda rota do lado do Comitê passa pelo mesmo portão, que autoriza pela atribuição ao caso, barra o impedido e o Citado, e grava a leitura na mesma chamada. O super admin não passa por cima. Um teste de varredura reprova rota do módulo que não use o portão.

5. **O Citado é ligado ao cadastro quando a pessoa existe nele.** Ligado, o portão barra a pessoa em qualquer perfil, e se ela for membro o impedimento é automático. Nome sem cadastro fica como texto.

6. **Terceira exceção à decisão 1 da ADR 0082: o agente lê o relato sem clique de membro.** Ele roda uma vez quando a pessoa abre a revisão do relato, na página pública, e uma vez na entrada do caso. O teto é de 100 leituras por dia. Passado o teto, ou com o agente fora do ar, o aviso de assunto fora do canal não aparece e o caso entra para triagem manual: o relato nunca fica retido. O modelo é `claude-sonnet-5-5`. Os outros agentes do módulo rodam depois de um clique e já cabem na ADR 0082.

7. **Nenhum nome vai à IA.** O relato passa pela pseudonimização antes de sair do app (ADR 0034). No termo de declaração e na ata, que precisam dos nomes, a troca usa marcadores numerados reversíveis: o nome vira marcador na ida e volta a ser nome dentro do app. O possível impedimento por nome é conferido pelo app, sem IA.

8. **O protocolo do Canal é aleatório.** Sem ordem e sem contagem. Número em sequência contaria os casos para quem relata e deixaria um buraco na fila comum a cada caso da Rota Especial, visível justamente a quem o caso pode envolver. A numeração da Ouvidoria não é tocada.

9. **A trilha do caso é uma cadeia.** Além do trigger que bloqueia alteração e do código de integridade de cada arquivo, cada linha carrega o código da anterior. Linha apagada ou trocada por quem tem o banco aparece na conferência.

10. **Nada de IP.** O limite de envios da página pública usa uma chave embaralhada, com sal trocado a cada 24 horas e guardado só em memória. O log das rotas do módulo sai sem endereço. O log do proxy fica fora do app e é conferido no servidor antes da abertura.

11. **O canal nasce fechado.** Uma chave de abertura em variável do Coolify mantém a rota pública em 404 e esconde a saída "Sou colaborador" da Ouvidoria. As fatias sobem para produção com o canal fechado, e quem abre é o Pedro, depois do aditivo assinado, do layout aprovado e do teste de anonimato.

12. **O apurador e o membro da CIPA entram por convite feito dentro do caso.** Quem não tem login ganha um cadastro mínimo, sem acesso a outro módulo, e só abre o caso depois do termo assinado. O super admin não participa.

13. **Uma tabela só para as assinaturas do Canal.** Todos os documentos do módulo que vão à ClickSign usam a mesma tabela, que vira o quarto destino do webhook. O app guarda a cópia do PDF assinado.

14. **A sinalização da Ouvidoria ao Canal é a segunda exceção ao sigilo do relato (emenda a ADR 0088).** Por decisão do diretor, o Comitê recebe o relato integral sem o nome de quem manifestou, e a manifestação continua aberta na Ouvidoria. No sentido contrário, o Canal manda ao Núcleo só uma nota do Comitê.

15. **O teste de aceite do agente é um comando manual.** São 12 casos fictícios, três vezes cada, com o resultado no corpo do PR, fora do CI. O teste de acesso e de anonimato por quem não desenvolveu é uma parada humana antes da abertura.

## Alternativas consideradas

- **Sem cifra, só o portão da aplicação, como no Núcleo**: rejeitada. O aceite da Diretoria pede conteúdo cifrado, e o Studio mostraria o relato a quem abre a tabela.
- **Chave guardada pelo Comitê, fora do servidor**: rejeitada. O agente só rodaria com membro logado, e perder a chave seria perder os casos.
- **Arquivos em claro no bucket privado, com URL assinada**: rejeitada. O áudio do depoimento é o dado mais sensível do módulo, e o volume é de poucos casos por ano.
- **Transcrição crua para a IA no termo e na ata**: rejeitada. O nome do acusado e a acusação ficariam até 30 dias no fornecedor.
- **Lista fixa de termos no lugar do agente na página pública**: rejeitada. O aceite mede o aviso de assunto fora do canal caso a caso.
- **Chave de abertura no banco, virada pela coordenação**: rejeitada. A abertura depende de condições de fora do app.
- **Login do apurador criado antes pelo Admin**: rejeitada. O pedido avisaria o super admin na hora em que um caso da Rota Especial começa.

## Consequências

- Trocar a chave da cifra exige recifrar o módulo, e perder a chave é perder os casos. A guarda da chave entra no procedimento de backup.
- Todo download de arquivo do Canal passa pelo backend. Com o volume previsto isso não pesa. Se o volume mudar, a decisão 2 precisa ser revista.
- Não há busca por texto dentro do relato. Os casos parecidos são achados pelos metadados em claro.
- A fatia de preparação mexe em código do Núcleo que está em produção. Ela sobe antes de qualquer tela do Canal e não muda o comportamento do Núcleo.
- Job novo que chame IA continua precisando de ADR que emende a 0082.
