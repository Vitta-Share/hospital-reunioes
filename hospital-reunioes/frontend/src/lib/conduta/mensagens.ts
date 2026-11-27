/**
 * A área Mensagens da tela do caso (issue #1845; especificação, 5.3 e 6.1):
 * a conversa da coordenação com quem relatou, pela página de acompanhamento.
 * O servidor decide o que vale e quem pode.
 */

export interface MensagemDoCaso {
  id: string;
  tipo: "pergunta" | "complemento";
  de: "comite" | "relator";
  texto: string;
  enviada_em: string;
}

export interface MensagensDoCaso {
  itens: MensagemDoCaso[];
  /** Há pergunta enviada depois do último complemento. */
  aguardando_resposta: boolean;
  pode_perguntar: boolean;
  /** As perguntas que o agente sugeriu na triagem, para a coordenação escolher. */
  perguntas_sugeridas: string[];
  /** O dia em que o pedido sem resposta libera arquivar ("2026-12-07"). */
  arquivar_a_partir_de: string | null;
  pode_arquivar: boolean;
  arquivado: boolean;
  pode_reabrir: boolean;
}

export const LIMITE_DA_PERGUNTA = 2000;
