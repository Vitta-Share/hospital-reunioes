/** O período de sombra e a recalibração do agente do Núcleo (issue #2001, Anexo F, seções 4, 5 e 7). */

export const ORIENTACAO_DA_RECALIBRACAO =
  "Leia os itens da auditoria e registre a decisão sobre o agente: manter, ajustar ou ligar a aprovação em lote.";

export const SEM_DADOS_NESTA_FASE = "Sem dados nesta fase";

export interface EixoDaConcordancia {
  eixo: string;
  rotulo: string;
  acatadas: number;
  total: number;
  percentual: number | null;
}

export interface ErroParaBaixo {
  notificacao_id: string;
  protocolo: string | null;
  sugerido: string;
  decidido: string;
  grave_ou_obito: boolean;
}

export interface Concordancia {
  versoes: { prompt: string; base: string };
  casos: number;
  eixos: EixoDaConcordancia[];
  erros_para_baixo: ErroParaBaixo[];
}

export interface ItemDoAnexoF {
  numero: number;
  secao: number;
  titulo: string;
  sinal: string;
  com_dados: boolean;
  linhas: string[];
  alerta: boolean;
}

export interface Recalibracao {
  marco: number;
  devida_em: string;
  decisao: string | null;
  decidido_por: string | null;
  decidido_em: string | null;
}

export interface TelaDaRecalibracao {
  recalibracoes: Recalibracao[];
  decisoes: { valor: string; rotulo: string }[];
  itens: ItemDoAnexoF[];
  pode_decidir: boolean;
}

export const ROTULO_DO_DANO: Record<string, string> = {
  nao_se_aplica: "não se aplica",
  nenhum: "nenhum",
  leve: "leve",
  moderado: "moderado",
  grave: "grave",
  obito: "óbito",
};
