/**
 * O arquivar de Contas médicas (issue #1958, PRD #1933, ADR 0105, decisões 6
 * a 10): as rotas, a Competência na tela, o agrupamento das contas por mês e
 * os textos. Quem decide quem arquiva e o que entra no mês é o servidor; a
 * tela só mostra o botão a quem pode e conta o que vai arquivar.
 */
import type { ItemDaFila } from "./envio";

export const ROTA_ARQUIVADAS = "/api/contas-medicas/arquivadas";

export function rotaDoArquivar(contaId: string): string {
  return `/api/contas-medicas/contas/${contaId}/arquivar`;
}

export function rotaDoDesarquivar(contaId: string): string {
  return `/api/contas-medicas/contas/${contaId}/desarquivar`;
}

export function rotaDoArquivarOMes(mes: string): string {
  return `/api/contas-medicas/competencias/${mes}/arquivar`;
}

const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** "2026-10" vira "outubro de 2026"; sem Competência, "sem mês". */
export function nomeDaCompetencia(mes: string | null | undefined): string {
  const [ano, numero] = (mes ?? "").split("-");
  const nome = MESES[Number(numero) - 1];
  return nome && ano ? `${nome} de ${ano}` : "sem mês";
}

/** O nome do mês com a primeira letra maiúscula, para o título do grupo. */
export function tituloDaCompetencia(mes: string | null | undefined): string {
  const nome = nomeDaCompetencia(mes);
  return nome.charAt(0).toUpperCase() + nome.slice(1);
}

export interface GrupoDaCompetencia {
  competencia: string | null;
  contas: ItemDaFila[];
}

/**
 * As contas por Competência, o mês mais recente primeiro; dentro do mês, na
 * ordem em que vieram. A conta sem Competência fica no fim.
 */
export function agruparPorCompetencia(contas: ItemDaFila[]): GrupoDaCompetencia[] {
  const grupos = new Map<string | null, ItemDaFila[]>();
  for (const conta of contas) {
    const mes = conta.competencia ?? null;
    grupos.set(mes, [...(grupos.get(mes) ?? []), conta]);
  }
  return Array.from(grupos, ([competencia, doMes]) => ({ competencia, contas: doMes })).sort((a, b) => {
    if (a.competencia === b.competencia) return 0;
    if (a.competencia === null) return 1;
    if (b.competencia === null) return -1;
    return a.competencia < b.competencia ? 1 : -1;
  });
}

const COM_PENDENCIA = "CONCLUIDA_COM_PENDENCIA";

function contas(n: number): string {
  return n === 1 ? "1 conta" : `${n} contas`;
}

/** O que "Arquivar o mês" leva: as da pessoa, ou todas para quem tem o painel completo. */
export function alvoDoMes(doMes: ItemDaFila[], todas: boolean): ItemDaFila[] {
  return todas ? doMes : doMes.filter((conta) => conta.minha);
}

export const O_QUE_E_ARQUIVAR = "Arquivar quer dizer que a conta já foi tratada no MV.";

/** A confirmação do "Arquivar o mês", na própria lista. */
export function perguntaDoMes(alvo: ItemDaFila[], mes: string | null): string {
  const pendencias = alvo.filter((conta) => conta.situacao === COM_PENDENCIA).length;
  const comPendencia =
    pendencias === 0 ? "Nenhuma tem pendência." : pendencias === 1 ? "1 tem pendência." : `${pendencias} têm pendência.`;
  return `Arquivar ${contas(alvo.length)} de ${nomeDaCompetencia(mes)}? ${comPendencia} ${O_QUE_E_ARQUIVAR}`;
}

export function botaoDaConfirmacao(alvo: ItemDaFila[]): string {
  return `Arquivar ${contas(alvo.length)}`;
}

/** O aviso depois do lote: quantas o servidor arquivou e quantas tinham pendência. */
export function resultadoDoMes(resposta: { arquivadas: number; com_pendencia: number }): string {
  if (resposta.arquivadas === 0) return "Nenhuma conta arquivada.";
  const quantas = resposta.arquivadas === 1 ? "1 conta arquivada" : `${resposta.arquivadas} contas arquivadas`;
  return resposta.com_pendencia > 0 ? `${quantas}, ${resposta.com_pendencia} com pendência.` : `${quantas}.`;
}

export const DICA_DO_ARQUIVAR = `Tira a conta da Esteira e leva para Arquivadas. ${O_QUE_E_ARQUIVAR}`;
export const DICA_DO_DESARQUIVAR = "Devolve a conta para Concluídas.";

export function dicaDoArquivarOMes(todas: boolean): string {
  const quais = todas ? "Arquiva todas as contas concluídas deste mês" : "Arquiva as suas contas concluídas deste mês";
  return `${quais}, inclusive as com pendência. ${O_QUE_E_ARQUIVAR}`;
}

export const FALHA_DO_ARQUIVAR = "Não consegui arquivar. Tente de novo.";
export const FALHA_DO_DESARQUIVAR = "Não consegui desarquivar. Tente de novo.";

/** Faz o POST e devolve a frase da recusa, ou nulo quando deu certo, com o corpo da resposta. */
export async function postar(
  rota: string,
  token: string,
  falha: string,
): Promise<{ recusa: string | null; corpo: unknown }> {
  try {
    const resposta = await fetch(rota, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
    const corpo = await resposta.json().catch(() => null);
    if (resposta.ok) return { recusa: null, corpo };
    const detalhe = (corpo as { detail?: unknown } | null)?.detail;
    return { recusa: typeof detalhe === "string" ? detalhe : falha, corpo };
  } catch {
    return { recusa: falha, corpo: null };
  }
}
