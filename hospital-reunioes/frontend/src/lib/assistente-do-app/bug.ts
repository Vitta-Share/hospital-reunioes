/**
 * O Roteiro do bug do Assistente do app (issue #2275, ADR 0113, decisão 8).
 *
 * Quatro perguntas de texto e o print, uma por vez, sem IA. As respostas
 * viram uma Demanda Registrada no backend (`/assistente-do-app/bug`), o print
 * vira Anexo dela e o clique de envio cria a issue. Nada é reenviado sozinho:
 * a falha volta com o motivo, e só o clique em "Tentar de novo" chama de novo.
 */

import { createClient } from "@/lib/supabase/client";

export type CampoDoBug = "onde" | "o_que_aconteceu" | "o_que_esperava" | "como_repetir";

export type RespostasDoBug = Record<CampoDoBug, string>;

/** As quatro perguntas de texto, na ordem do roteiro, com o rótulo do resumo. */
export const PERGUNTAS_DO_BUG: { campo: CampoDoBug; rotulo: string; pergunta: string }[] = [
  { campo: "onde", rotulo: "Onde", pergunta: "Em que tela ou parte do aplicativo aconteceu?" },
  { campo: "o_que_aconteceu", rotulo: "O que aconteceu", pergunta: "O que aconteceu?" },
  { campo: "o_que_esperava", rotulo: "O que esperava", pergunta: "O que você esperava que acontecesse?" },
  { campo: "como_repetir", rotulo: "Como repetir", pergunta: "Como fazer o problema acontecer de novo, passo a passo?" },
];

export const PERGUNTA_DO_PRINT = "Tem um print da tela? Mande aqui. Ele fica guardado só no aplicativo.";

export interface ResumoDoBug extends RespostasDoBug {
  titulo: string;
  criterios: string[];
}

export const ROTA_DO_BUG = "/api/assistente-do-app/bug";
export const FALHA_DO_BUG = "Não deu para guardar o relato agora. Tente de novo.";

type Buscar = typeof fetch;

async function token(): Promise<string> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? "";
}

async function chamar<T>(buscar: Buscar, url: string, init: RequestInit): Promise<T> {
  const res = await buscar(url, {
    ...init,
    headers: { ...(init.headers ?? {}), Authorization: `Bearer ${await token()}` },
  });
  if (!res.ok) {
    const corpo = await res.json().catch(() => null);
    throw new Error(typeof corpo?.detail === "string" ? corpo.detail : FALHA_DO_BUG);
  }
  return (await res.json()) as T;
}

/** As quatro respostas viram a Demanda Registrada; volta o id e o resumo. */
export function registrarBug(
  respostas: RespostasDoBug,
  buscar: Buscar = fetch
): Promise<{ demanda_id: string; resumo: ResumoDoBug }> {
  return chamar(buscar, ROTA_DO_BUG, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(respostas),
  });
}

/** O print vira Anexo da Demanda; volta quantos prints ela guarda. */
export async function anexarPrint(demandaId: string, arquivo: File, buscar: Buscar = fetch): Promise<number> {
  const corpo = new FormData();
  corpo.append("imagem", arquivo);
  const { prints } = await chamar<{ prints: number }>(buscar, `${ROTA_DO_BUG}/${demandaId}/print`, {
    method: "POST",
    body: corpo,
  });
  return prints;
}

/** O clique de envio: cria a issue. A falha sobe com o motivo do backend. */
export async function enviarBug(demandaId: string, buscar: Buscar = fetch): Promise<void> {
  await chamar(buscar, `${ROTA_DO_BUG}/${demandaId}/enviar`, { method: "POST" });
}
