/**
 * A trilha do caso com as gavetas e o Dossiê (issue #1837; especificação, 9.1
 * e 9.2): os tipos que a API devolve na tela do caso e o "BAIXAR DOSSIÊ", que
 * sai só pelo backend, decifrado, e fica registrado na trilha.
 */
import { createClient } from "@/lib/supabase/client";

export interface ItemDaTrilha {
  tipo: "ato" | "documento";
  acao: string | null;
  titulo: string;
  autor: string;
  data: string | null;
  origem: "Aplicação" | "Upload" | "ClickSign";
  /** No ato, o código da linha na cadeia; no documento, o código de integridade do arquivo. */
  codigo: string | null;
  versao: number | null;
}

export interface Gaveta {
  rotulo: string;
  origem: "Upload" | "ClickSign";
  obrigatoria: boolean;
  situacao: "Aguardando" | "Assinado";
}

export interface TrilhaDoCaso {
  linha_do_tempo: ItemDaTrilha[];
  gavetas: Gaveta[];
  conferencia: { intacta: boolean; linhas_adulteradas: number[]; texto: string };
  pode_baixar_dossie: boolean;
}

/** As leituras do caso ficam no registro de acessos; a tela mostra à parte. */
export const ACOES_DE_LEITURA = new Set(["leitura", "abriu_arquivo"]);

async function cabecalho(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return { Authorization: `Bearer ${session?.access_token ?? ""}` };
}

/** BAIXAR DOSSIÊ: o pacote ZIP do caso, salvo pelo navegador. */
export async function baixarDossie(casoId: string, protocolo: string): Promise<void> {
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/dossie`, { headers: await cabecalho() });
  if (!res.ok) {
    const detalhe = await res.json().catch(() => null);
    throw new Error(typeof detalhe?.detail === "string" ? detalhe.detail : "O Dossiê não pôde ser baixado agora.");
  }
  const endereco = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = endereco;
  link.download = `dossie-${protocolo}.zip`;
  link.click();
  URL.revokeObjectURL(endereco);
}
