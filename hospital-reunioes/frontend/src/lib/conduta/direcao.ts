/**
 * A Recomendação do Comitê para a Direção (issue #1835): o Presidente só lê a
 * página de conclusão e a ata assinada; a diretoria executiva também registra
 * a decisão do Presidente sobre a medida e anexa a cópia da comunicação. Toda
 * chamada vai ao portão da Direção, que grava cada leitura na trilha.
 */
import type { DecisaoDaMedida } from "@/lib/conduta/retorno";
import { createClient } from "@/lib/supabase/client";

const BASE = "/api/comite-de-conduta/direcao";

export interface RecomendacaoNaLista {
  id: string;
  protocolo: string;
  enviado_a_direcao_em: string | null;
  decisao: string | null;
}

export interface ListaDaDirecao {
  recomendacoes: RecomendacaoNaLista[];
  registra_decisao: boolean;
}

export interface Recomendacao {
  id: string;
  protocolo: string;
  rito: string;
  categoria: string | null;
  resultado: string;
  medida_recomendada: string | null;
  relatorio: string | null;
  votacao_concluida_em: string | null;
  enviado_a_direcao_em: string | null;
  tem_ata_assinada: boolean;
  decisao: DecisaoDaMedida | null;
  comunicacoes: { versao: number; enviado_em: string }[];
  pode_registrar: boolean;
  pode_anexar_comunicacao: boolean;
}

export const DECISOES = [
  { valor: "aplicada", rotulo: "Aplicada", justificativa: false },
  { valor: "aplicada_com_ajuste", rotulo: "Aplicada com ajuste", justificativa: true },
  { valor: "nao_aplicada", rotulo: "Não aplicada", justificativa: true },
] as const;

export type Decisao = (typeof DECISOES)[number]["valor"];

async function cabecalho(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return { Authorization: `Bearer ${session?.access_token ?? ""}` };
}

async function falha(res: Response, padrao: string): Promise<Error> {
  const corpo = await res.json().catch(() => null);
  return new Error(typeof corpo?.detail === "string" ? corpo.detail : padrao);
}

export async function chamarDirecao<T>(caminho: string, opcoes: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers = await cabecalho();
  if (opcoes.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE}${caminho}`, {
    method: opcoes.method ?? "GET",
    headers,
    body: opcoes.body !== undefined ? JSON.stringify(opcoes.body) : undefined,
  });
  if (!res.ok) throw await falha(res, "Não foi possível concluir. Tente de novo.");
  return (await res.json()) as T;
}

/** A ata assinada, decifrada pelo backend, como endereço local do navegador. */
export async function abrirAtaDaRecomendacao(casoId: string): Promise<string> {
  const res = await fetch(`${BASE}/recomendacoes/${casoId}/ata`, { headers: await cabecalho() });
  if (!res.ok) throw await falha(res, "A ata assinada não pôde ser aberta agora.");
  return URL.createObjectURL(await res.blob());
}

/** A cópia da comunicação da medida que o DP fez, em PDF, JPG ou PNG. */
export async function anexarComunicacaoDaMedida(casoId: string, arquivo: File): Promise<void> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  const res = await fetch(`${BASE}/recomendacoes/${casoId}/comunicacao`, {
    method: "POST",
    headers: await cabecalho(),
    body: corpo,
  });
  if (!res.ok) throw await falha(res, "A cópia não foi anexada. Tente de novo.");
}
