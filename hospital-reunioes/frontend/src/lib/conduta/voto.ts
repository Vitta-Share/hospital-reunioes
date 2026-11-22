/**
 * O voto e a trava de robustez (issue #1833): os tipos que a API devolve na
 * tela do caso, a Matriz de Consequências e o envio e a abertura da ciência
 * do Código, que sai só pelo backend.
 */
import { createClient } from "@/lib/supabase/client";

export type Resultado = "procedente" | "parcialmente_procedente" | "improcedente" | "inconclusivo";

export const RESULTADOS: { valor: Resultado; rotulo: string }[] = [
  { valor: "procedente", rotulo: "Procedente" },
  { valor: "parcialmente_procedente", rotulo: "Parcialmente procedente" },
  { valor: "improcedente", rotulo: "Improcedente" },
  { valor: "inconclusivo", rotulo: "Inconclusivo" },
];

export const COM_MEDIDA: Resultado[] = ["procedente", "parcialmente_procedente"];

/** A Matriz de Consequências (especificação, 6.6). */
export const MEDIDAS: { valor: string; rotulo: string }[] = [
  { valor: "orientacao_registrada", rotulo: "Orientação registrada" },
  { valor: "advertencia_escrita", rotulo: "Advertência escrita" },
  { valor: "suspensao", rotulo: "Suspensão (1 a 30 dias)" },
  { valor: "dispensa_por_justa_causa", rotulo: "Dispensa por justa causa" },
  { valor: "rescisao_de_contrato", rotulo: "Rescisão de contrato (PJ, cooperado, terceiro, fornecedor)" },
  { valor: "comunicacao_a_autoridade", rotulo: "Comunicação a autoridade ou conselho profissional" },
];

export interface VotoRegistrado {
  resultado: Resultado;
  medida: string | null;
  dias_de_suspensao: number | null;
  justificativa: string;
}

export interface RodadaFechada {
  rodada: number;
  votos: (VotoRegistrado & { membro: string })[];
  resultado: Resultado | null;
  medida: string | null;
  reuniao_curta: boolean;
}

export interface Votacao {
  rodada: number;
  votantes: number;
  votaram: number;
  meu_voto: VotoRegistrado | null;
  pode_votar: boolean;
  bloqueio_do_voto: string | null;
  reuniao_curta_convocada: boolean;
  rodadas: RodadaFechada[];
  resultado: { resultado: Resultado; medida: string | null } | null;
  concluida: Resultado | null;
  pode_concluir: boolean;
  bloqueio_da_conclusao: string | null;
}

export interface ItemDaTrava {
  item: string;
  rotulo: string;
  preenchimento: { atendido: boolean; texto: string } | null;
  confirmacoes: string[];
  confirmacoes_precisas: number;
  confirmado: boolean;
  pode_confirmar: boolean;
  bloqueio: string | null;
}

export interface Trava {
  itens: ItemDaTrava[];
  preenchida_em: string | null;
  pode_preencher: boolean;
  ciencia: { versao: number; enviado_em: string; enviado_por: string }[];
}

export function rotuloDoResultado(resultado: string | null): string {
  return RESULTADOS.find((r) => r.valor === resultado)?.rotulo ?? "Sem resultado";
}

export function rotuloDaMedida(voto: Pick<VotoRegistrado, "medida" | "dias_de_suspensao">): string | null {
  if (!voto.medida) return null;
  if (voto.medida === "suspensao") {
    const dias = voto.dias_de_suspensao ?? 0;
    return `Suspensão de ${dias} dia${dias === 1 ? "" : "s"}`;
  }
  return MEDIDAS.find((m) => m.valor === voto.medida)?.rotulo ?? voto.medida;
}

async function cabecalho(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return { Authorization: `Bearer ${session?.access_token ?? ""}` };
}

async function falha(res: Response): Promise<Error> {
  const corpo = await res.json().catch(() => null);
  if (res.status === 413 && typeof corpo?.detail !== "string") return new Error("O arquivo é grande demais.");
  return new Error(typeof corpo?.detail === "string" ? corpo.detail : "Não foi possível concluir. Tente de novo.");
}

/** A ciência do Código que o DP registrou fora do aplicativo. */
export async function anexarCiencia(casoId: string, arquivo: File): Promise<void> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/trava/ciencia`, {
    method: "POST",
    headers: await cabecalho(),
    body: corpo,
  });
  if (!res.ok) throw await falha(res);
}

/** A última ciência anexada, decifrada pelo backend, como endereço local do navegador. */
export async function abrirCiencia(casoId: string): Promise<string> {
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/trava/ciencia`, { headers: await cabecalho() });
  if (!res.ok) throw await falha(res);
  return URL.createObjectURL(await res.blob());
}
