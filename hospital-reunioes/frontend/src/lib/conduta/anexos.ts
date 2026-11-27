/**
 * Os anexos do relato, do lado do Comitê (issue #1844). O arquivo chega
 * decifrado pelo backend, já sem os dados de origem, e a abertura fica na
 * trilha. Nada de URL do bucket.
 */

import { createClient } from "@/lib/supabase/client";

export type TipoDoAnexo = "imagem" | "pdf" | "audio";

export interface AnexoDoRelato {
  id: string;
  tipo: TipoDoAnexo;
  origem: "relato" | "complemento";
  enviado_em: string;
}

export const ROTULOS_DO_ANEXO: Record<TipoDoAnexo, string> = { imagem: "Imagem", pdf: "PDF", audio: "Áudio" };

/** O anexo como endereço local do navegador. Quem chama solta o endereço
 * (`URL.revokeObjectURL`) quando fecha. */
export async function abrirAnexo(casoId: string, anexoId: string): Promise<string> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/anexos/${anexoId}`, {
    headers: { Authorization: `Bearer ${session?.access_token ?? ""}` },
  });
  if (!res.ok) {
    const corpo = await res.json().catch(() => null);
    throw new Error(typeof corpo?.detail === "string" ? corpo.detail : "Não foi possível abrir o anexo. Tente de novo.");
  }
  return URL.createObjectURL(await res.blob());
}
