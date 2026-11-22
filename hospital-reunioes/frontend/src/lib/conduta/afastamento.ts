/**
 * O afastamento cautelar do Canal de Conduta (issue #1836): os tipos que a API
 * devolve e as chamadas que não cabem no `chamarComite` (o PDF do parecer).
 *
 * Quem decide o que cada pessoa pode fazer é o servidor: cada afastamento
 * chega com `pode_registrar_entrega` e `pode_anexar_parecer`.
 */
import { createClient } from "@/lib/supabase/client";

export type ResultadoDoAfastamento = "afastar" | "nao_afastar";
export type DestinoDoPedido = "dp" | "juridico";

export interface Afastamento {
  id: string;
  rota: "comum" | "especial";
  quem: string;
  motivo: string;
  registrado_em: string;
  /** No caso comum, a decisão do coordenador; na Rota Especial, o que o parecer definiu (null antes dele). */
  resultado: ResultadoDoAfastamento | null;
  entregas: Record<DestinoDoPedido, string | null>;
  parecer: { anexado_em: string; ciencia_de: string[] | null } | null;
  pode_registrar_entrega: boolean;
  pode_anexar_parecer: boolean;
}

/** O pedido ao DP e ao Jurídico: só quem afastar e o motivo. */
export interface PedidoDeAfastamento extends Omit<Afastamento, "quem" | "motivo"> {
  pedido: { quem: string; motivo: string; texto: string };
  aviso: string;
}

/** O que a coordenação vê na lista dos pedidos da Rota Especial: nada do caso. */
export interface ItemDosPedidos {
  id: string;
  caso_id: string;
  registrado_em: string;
  resultado: ResultadoDoAfastamento | null;
  parecer_anexado: boolean;
}

export const RESULTADOS: { valor: ResultadoDoAfastamento; rotulo: string }[] = [
  { valor: "afastar", rotulo: "Afastar" },
  { valor: "nao_afastar", rotulo: "Não afastar" },
];

export const DESTINOS_DO_PEDIDO: { valor: DestinoDoPedido; rotulo: string }[] = [
  { valor: "dp", rotulo: "DP" },
  { valor: "juridico", rotulo: "Jurídico" },
];

export function doPedido(pedido: PedidoDeAfastamento): Afastamento {
  const { pedido: dados, ...resto } = pedido;
  return { ...resto, quem: dados.quem, motivo: dados.motivo };
}

export function caminhoDoAfastamento(casoId: string, afastamentoId: string): string {
  return `/casos/${casoId}/afastamentos/${afastamentoId}`;
}

async function cabecalho(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return { Authorization: `Bearer ${session?.access_token ?? ""}` };
}

async function falha(res: Response): Promise<Error> {
  const corpo = await res.json().catch(() => null);
  return new Error(typeof corpo?.detail === "string" ? corpo.detail : "Não foi possível concluir. Tente de novo.");
}

/** Anexa o parecer do Jurídico em PDF. Na Rota Especial, com o que ele definiu. */
export async function anexarParecer(
  casoId: string,
  afastamentoId: string,
  arquivo: File,
  resultado: ResultadoDoAfastamento | null,
): Promise<void> {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo);
  if (resultado) corpo.append("resultado", resultado);
  const res = await fetch(`/api/comite-de-conduta${caminhoDoAfastamento(casoId, afastamentoId)}/parecer`, {
    method: "POST",
    headers: await cabecalho(),
    body: corpo,
  });
  if (!res.ok) throw await falha(res);
}

/** O parecer decifrado pelo backend, como endereço local do navegador. */
export async function abrirParecer(casoId: string, afastamentoId: string): Promise<string> {
  const res = await fetch(`/api/comite-de-conduta${caminhoDoAfastamento(casoId, afastamentoId)}/parecer`, {
    headers: await cabecalho(),
  });
  if (!res.ok) throw await falha(res);
  return URL.createObjectURL(await res.blob());
}
