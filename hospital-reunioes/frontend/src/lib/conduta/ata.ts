/**
 * A ata de deliberação e a reunião do Comitê (issue #1834): os tipos que a API
 * devolve na tela do caso, o envio da transcrição da reunião (só ela: sem
 * seletor de tipo e sem áudio) e a abertura da cópia assinada, que sai só pelo
 * backend.
 */
import { createClient } from "@/lib/supabase/client";

export interface VotoDaAta {
  membro: string;
  resultado: string;
  medida: string | null;
  justificativa: string;
}

export interface DocumentoDaAta {
  versao: number;
  identificacao: { rito: string; data: string; presentes: string[]; impedimentos: string[]; suplentes: string[] };
  resumo: string;
  provas: string[];
  defesa: string;
  deliberacao: string;
  fundamentos: string;
  medida: string | null;
  votos: VotoDaAta[];
  correcao: string[];
  encaminhamentos: string[];
  /** Os Pontos a confirmar: Sugestão, fora da ata. */
  pontos: { rotulo: string; itens: string[] };
  assinatura: { situacao: "gerado" | "enviado" | "assinado"; erro: string | null; assinado_em: string | null; tem_copia: boolean } | null;
}

export interface AtaDoCaso {
  documento: DocumentoDaAta | null;
  pode_gerar: boolean;
  bloqueio_da_geracao: string | null;
  pode_enviar: boolean;
}

export interface ItemDaReuniao {
  item: string;
  rotulo: string;
  automatico: boolean;
  estado: "feito" | "pendente";
  marcado_por?: string;
  marcado_em?: string;
}

export interface ReuniaoDoComite {
  transcricoes: { versao: number; enviado_em: string; enviado_por: string }[];
  lista: ItemDaReuniao[];
  pode_anexar: boolean;
  pode_marcar: boolean;
  pode_concluir: boolean;
  bloqueio_da_conclusao: string | null;
  concluida_em: string | null;
  concluida_por: string | null;
  transcricao_eliminada_em: string | null;
}

/** Os formatos aceitos no botão da transcrição da reunião. Nenhum de áudio. */
export const FORMATOS_DA_TRANSCRICAO = ".txt,.vtt,.pdf,.docx";

async function cabecalho(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return { Authorization: `Bearer ${session?.access_token ?? ""}` };
}

/** ANEXAR TRANSCRIÇÃO DA REUNIÃO DO COMITÊ: só o arquivo, sem tipo. */
export async function anexarTranscricaoDaReuniao(casoId: string, arquivo: File): Promise<void> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/reuniao/transcricao`, {
    method: "POST",
    headers: await cabecalho(),
    body: corpo,
  });
  if (!res.ok) {
    const detalhe = await res.json().catch(() => null);
    throw new Error(typeof detalhe?.detail === "string" ? detalhe.detail : "A transcrição não foi anexada. Tente de novo.");
  }
}

/** A cópia da ata assinada, decifrada pelo backend, como endereço local do navegador. */
export async function abrirAtaAssinada(casoId: string): Promise<string> {
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/ata/assinada`, { headers: await cabecalho() });
  if (!res.ok) throw new Error("A ata assinada não pôde ser aberta agora.");
  return URL.createObjectURL(await res.blob());
}
