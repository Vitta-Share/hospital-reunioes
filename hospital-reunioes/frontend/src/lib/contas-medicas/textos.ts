/**
 * Os textos da tela de contas de Contas médicas (issues #1951 e #1954, PRD
 * #1933): o nome, a Legenda e o estado vazio de cada etapa da Esteira, a dica
 * do "Pegar" e os textos do envio. Ficam aqui para o teste e o manual lerem a
 * mesma frase.
 */

/** As etapas da Esteira, na ordem do caminho da conta. */
export type Etapa = "envios" | "fila" | "em_analise" | "concluidas";

export const ETAPAS: Etapa[] = ["envios", "fila", "em_analise", "concluidas"];

export const NOME_DA_ETAPA: Record<Etapa, string> = {
  envios: "Envios",
  fila: "Fila",
  em_analise: "Em análise",
  concluidas: "Concluídas",
};

/** A Legenda de uma frase da etapa aberta. */
export const LEGENDA_DA_ETAPA: Record<Etapa, string> = {
  envios: "As contas enviadas que ainda estão sendo lidas ou esperam um arquivo.",
  fila: "As contas prontas que ninguém pegou, na ordem de envio.",
  em_analise: "As contas que uma faturista pegou e ainda não concluiu.",
  concluidas: "As contas que a faturista já concluiu.",
};

export const VAZIO_DA_ETAPA: Record<Etapa, string> = {
  envios: "Nenhum envio esperando o guia",
  fila: "Nenhuma conta livre na fila",
  em_analise: "Nenhuma conta em análise",
  concluidas: "Nenhuma conta concluída ainda",
};

/** A dica do botão da conta livre: pegar é virar dona (ADR 0105, decisão 3). */
export const DICA_DO_PEGAR = "A conta passa a ser sua quando você pega.";

/** O título do bloco das contas em análise da própria pessoa, na etapa Fila. */
export const CONTINUE_DE_ONDE_PAROU = "Continue de onde parou";

/** Os limites de cada envio, que o servidor também confere. */
const LIMITES_DO_ENVIO = "Até 10 atendimentos e 30 arquivos por envio, 100 MB por arquivo.";

/** A Legenda da área de envio (issue #1954): o que enviar e os limites. */
export const LEGENDA_DO_ENVIO = `Vários de uma vez, sem renomear: o app lê o tipo e o atendimento dentro de cada PDF. ${LIMITES_DO_ENVIO}`;

/** A dica do botão "Enviar contas" da barra (issue #1954). */
export const DICA_DO_ENVIAR = `Abre a área para enviar a conta e o prontuário do MV, em PDF. Também dá para soltar os arquivos em qualquer ponto da tela. ${LIMITES_DO_ENVIO}`;

/** O realce de quando a pessoa arrasta arquivos sobre a tela de contas. */
export const SOLTE_PARA_ENVIAR = "Solte os PDFs para enviar";

/** O cabeçalho das colunas da lista: a palavra "Atendimento" aparece só aqui. */
export const COLUNAS = ["Atendimento", "Operadora", "Período", "Andamento", "Com quem", ""] as const;
