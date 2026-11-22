/**
 * O caminho do caso depois da votação, no lado do Comitê (issue #1835): o
 * envio à Direção, a decisão da medida que a Direção registrou, o retorno e a
 * correção de processo. Os tipos que a API devolve na tela do caso e as
 * chamadas que saem dela. O servidor decide o que vale.
 */
import { createClient } from "@/lib/supabase/client";

export interface DecisaoDaMedida {
  decisao: string;
  codigo: "aplicada" | "aplicada_com_ajuste" | "nao_aplicada";
  justificativa: string | null;
  decidida_em: string;
  registrada_em: string | null;
}

export interface VersaoDoRetorno {
  versao: number;
  origem: "agente" | "coordenacao";
  autor: string;
  criado_em: string | null;
  denunciante: string;
  acusado: string;
}

export interface RetornoDoCaso {
  em_aberto: boolean;
  pode_redigir: boolean;
  pode_aprovar: boolean;
  bloqueio_da_aprovacao: string | null;
  versoes: VersaoDoRetorno[];
  aprovado: { versao: number; aprovado_em: string | null; aprovado_por: string } | null;
}

export interface CorrecaoEscolhida {
  texto: string;
  responsavel: string;
  prazo_em: string;
  escolhida_por: string;
  escolhida_em: string | null;
}

export interface CorrecoesDoCaso {
  sugeridas: string[];
  escolhidas: CorrecaoEscolhida[];
  pode_escolher: boolean;
}

export interface MedidaERetorno {
  com_medida: boolean;
  pode_enviar_a_direcao: boolean;
  bloqueio_do_envio: string | null;
  enviado_a_direcao_em: string | null;
  decisao: DecisaoDaMedida | null;
  comunicacoes: { versao: number; enviado_em: string }[];
  retorno: RetornoDoCaso;
  correcoes: CorrecoesDoCaso | null;
}

async function cabecalho(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return { Authorization: `Bearer ${session?.access_token ?? ""}` };
}

/** A última cópia da comunicação da medida, decifrada pelo backend, como endereço local do navegador. */
export async function abrirComunicacaoDaMedida(casoId: string): Promise<string> {
  const res = await fetch(`/api/comite-de-conduta/casos/${casoId}/medida/comunicacao`, { headers: await cabecalho() });
  if (!res.ok) throw new Error("A cópia da comunicação da medida não pôde ser aberta agora.");
  return URL.createObjectURL(await res.blob());
}
