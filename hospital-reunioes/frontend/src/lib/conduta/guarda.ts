/**
 * O papel original e a guarda do caso (issue #1838; especificação, 9.3 e 9.4
 * e Anexo E.2): os tipos que a API devolve na tela do caso e o "IMPRIMIR
 * ETIQUETA", que sai do backend em PDF.
 */
import { createClient } from "@/lib/supabase/client";

export interface Original {
  rotulo: string;
  situacao: "Aguardando" | "Assinado";
}

export interface Lacre {
  por: string;
  em: string;
  local: string;
}

export interface GuardaDoCaso {
  encerrado: boolean;
  guardar_ate: string | null;
  vencida: boolean;
  originais: Original[];
  lacre: Lacre | null;
  local_padrao: string | null;
  pode_lacrar: boolean;
  pode_imprimir: boolean;
  congelado_em: string | null;
  pode_congelar: boolean;
  eliminado_em: string | null;
}

/** "2031-11-10" vira "10/11/2031", sem passar por fuso; o instante
 * ("2031-11-11T02:00:00+00:00") sai no dia de São Paulo. */
export function dataBr(iso: string | null): string {
  if (!iso) return "";
  if (iso.length > 10) {
    return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short" }).format(new Date(iso));
  }
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

/** IMPRIMIR ETIQUETA: a folha A4 do envelope, salva pelo navegador. */
export async function baixarEtiqueta(casoId: string, protocolo: string): Promise<void> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/etiqueta`, {
    headers: { Authorization: `Bearer ${session?.access_token ?? ""}` },
  });
  if (!res.ok) {
    const detalhe = await res.json().catch(() => null);
    throw new Error(typeof detalhe?.detail === "string" ? detalhe.detail : "A etiqueta não pôde ser gerada agora.");
  }
  const endereco = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = endereco;
  link.download = `etiqueta-${protocolo}.pdf`;
  link.click();
  URL.revokeObjectURL(endereco);
}
