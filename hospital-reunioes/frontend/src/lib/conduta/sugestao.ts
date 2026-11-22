/**
 * A sugestão do agente de triagem na tela do caso (issue #1827). O servidor
 * manda cada item pronto para mostrar: o título, o valor, a justificativa e o
 * trecho do relato. A tela não interpreta nada.
 */
export type RespostaASugestao = "confirmo" | "discordo";

export interface ItemDaSugestao {
  item: string;
  titulo: string;
  rotulo: string;
  valor: string;
  justificativa: string;
  trecho: string;
  resposta: RespostaASugestao | null;
  motivo: string | null;
}

export interface SugestaoDoAgente {
  situacao: "sugerida" | "manual" | "aguardando";
  motivo: string | null;
  itens: ItemDaSugestao[];
  pode_responder: boolean;
  possivel_impedimento: { membro: string; motivo: string }[];
}
