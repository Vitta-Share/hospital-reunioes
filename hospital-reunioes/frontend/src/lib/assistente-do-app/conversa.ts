/**
 * A conversa do Assistente do app, o robô do canto da tela (issue #2267, ADR
 * 0113, decisão 8).
 *
 * O backend responde pelo Kit de conhecimento e pelas páginas do Manual que a
 * tela manda. As páginas moram em `public/manual/<pasta>/pagina.md`, fora da
 * imagem do backend, e quem escolhe quais vão é a mesma conta do Manual pelo
 * menu (`paginasVisiveis`): página de módulo que a pessoa não acessa não sai
 * daqui. A pasta de cada página é o id do módulo dela.
 */

import type { CurrentParticipante } from "@/hooks/useCurrentParticipante";
import { createClient } from "@/lib/supabase/client";
import {
  MODULOS_DO_MANUAL,
  lerPagina,
  paginasVisiveis,
  type PaginaDoManual,
} from "@/lib/manual/paginas";

export interface FalaDoAssistente {
  role: "user" | "assistant";
  content: string;
}

export const ROTA_DA_CONVERSA = "/api/assistente-do-app/conversa";
export const FALHA_DA_CONVERSA = "O assistente não conseguiu responder. Mande a pergunta de novo.";

type Buscar = typeof fetch;

/** As páginas do Manual que a pessoa vê, lidas do `public/manual`. */
export async function paginasDoManualDe(
  participante: CurrentParticipante | null,
  buscar: Buscar = fetch
): Promise<PaginaDoManual[]> {
  if (!participante) return [];
  const lidas = await Promise.all(
    MODULOS_DO_MANUAL.map(async ({ id }) => {
      try {
        const res = await buscar(`/manual/${id}/pagina.md`);
        return res.ok ? lerPagina(id, await res.text()) : null;
      } catch {
        return null;
      }
    })
  );
  return paginasVisiveis(
    lidas.filter((p): p is PaginaDoManual => p !== null),
    participante
  );
}

/** Manda a conversa ao backend e devolve a fala do assistente. */
export async function perguntarAoAssistente(
  mensagens: FalaDoAssistente[],
  participante: CurrentParticipante | null,
  buscar: Buscar = fetch
): Promise<string> {
  const paginas = await paginasDoManualDe(participante, buscar);
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const res = await buscar(ROTA_DA_CONVERSA, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session?.access_token ?? ""}`,
    },
    body: JSON.stringify({
      mensagens,
      paginas_do_manual: paginas.map(({ modulo, titulo, corpo }) => ({ modulo, titulo, corpo })),
    }),
  });
  if (!res.ok) {
    const corpo = await res.json().catch(() => null);
    throw new Error(typeof corpo?.detail === "string" ? corpo.detail : FALHA_DA_CONVERSA);
  }
  const { resposta } = (await res.json()) as { resposta: string };
  return resposta;
}
