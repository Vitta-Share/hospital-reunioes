import type { SituacaoDaConta } from "@/lib/contas-medicas/envio";

/**
 * O tom da etiqueta de situação (issue #1951): livre neutro, em análise azul,
 * concluída verde, com pendência âmbar. Vermelho só no Erro. Na conta que
 * ainda não ficou pronta, o cartão do envio segue como era: esperando em
 * neutro e Processando em azul.
 */
export type Tom = "neutro" | "azul" | "verde" | "ambar" | "vermelho";

const TOM_DA_SITUACAO: Record<SituacaoDaConta, Tom> = {
  AGUARDANDO_ARQUIVO: "neutro",
  NA_FILA: "neutro",
  PROCESSANDO: "azul",
  A_FAZER: "neutro",
  EM_CORRECAO: "azul",
  RETORNO: "azul",
  CONCLUIDA: "verde",
  CONCLUIDA_COM_PENDENCIA: "ambar",
  ERRO: "vermelho",
};

export const COR_DO_TOM: Record<Tom, string> = {
  neutro: "bg-slate-100 text-slate-600",
  azul: "bg-[#DBEAFE] text-[#1E40AF]",
  verde: "bg-[#DCFCE7] text-[#166534]",
  ambar: "bg-[#FEF3C7] text-[#92400E]",
  vermelho: "bg-[#FEE2E2] text-[#991B1B]",
};

export function tomDaSituacao(situacao: SituacaoDaConta): Tom {
  return TOM_DA_SITUACAO[situacao] ?? "neutro";
}
