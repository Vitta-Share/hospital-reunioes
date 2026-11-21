/**
 * O relatório de apuração e a cronologia dos fatos (issue #1832): os tipos que
 * a API devolve na tela do caso e a abertura da cópia assinada, que sai só
 * pelo backend.
 */
import { createClient } from "@/lib/supabase/client";

export type TipoDoTexto = "relatorio" | "cronologia";

export interface VersaoDoTexto {
  versao: number;
  origem: "agente" | "edicao";
  autor: string;
  criado_em: string | null;
  texto: string;
}

export interface AssinaturaDoRelatorio {
  situacao: "gerado" | "enviado" | "assinado";
  erro: string | null;
  assinado_em: string | null;
  tem_copia: boolean;
}

export interface TextoDaApuracao {
  texto: string;
  versao: number;
  limite: number;
  versoes: VersaoDoTexto[];
  /** Só no relatório do rito Completo; null quando a última versão não foi à assinatura. */
  assinatura?: AssinaturaDoRelatorio | null;
}

export async function abrirRelatorioAssinado(casoId: string): Promise<string> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/relatorio/assinado`, {
    headers: { Authorization: `Bearer ${session?.access_token ?? ""}` },
  });
  if (!res.ok) throw new Error("O relatório assinado não pôde ser aberto agora.");
  return URL.createObjectURL(await res.blob());
}
