/**
 * Os documentos do Núcleo (issue #1767): tipos, rótulos e as chamadas da tela.
 *
 * Cada tipo tem versões e uma única vigente. Publicar uma versão nova troca a
 * vigente e guarda a anterior; não existe apagar nem editar, a correção é uma
 * versão nova.
 */

export type TipoDeDocumento =
  | "ato_designacao"
  | "regimento"
  | "plano_seguranca_paciente"
  | "termo"
  | "ata"
  | "outro";

export type NaturezaDaRevisao = "material" | "redacao";

export interface DocumentoDoNucleo {
  id: string;
  tipo: TipoDeDocumento;
  versao: number;
  titulo: string;
  natureza_revisao: NaturezaDaRevisao | null;
  vigente: boolean;
  tem_texto: boolean;
  tem_arquivo_assinado: boolean;
  publicado_em: string | null;
  publicado_por: string | null;
}

export interface NovaVersao {
  tipo: TipoDeDocumento;
  titulo: string;
  texto: string;
  natureza_revisao: NaturezaDaRevisao | null;
}

/** A ordem em que os tipos aparecem na tela e no seletor. */
export const TIPOS: { tipo: TipoDeDocumento; rotulo: string }[] = [
  { tipo: "ato_designacao", rotulo: "Ato de designação" },
  { tipo: "regimento", rotulo: "Regimento" },
  { tipo: "plano_seguranca_paciente", rotulo: "Plano de Segurança do Paciente" },
  { tipo: "termo", rotulo: "Termo" },
  { tipo: "ata", rotulo: "Ata" },
  { tipo: "outro", rotulo: "Outro" },
];

export const ROTULO_DA_NATUREZA: Record<NaturezaDaRevisao, string> = {
  material: "Revisão material",
  redacao: "Revisão de redação",
};

const ROTA = "/api/nsp/documentos";

async function detalheDoErro(res: Response, padrao: string): Promise<string> {
  try {
    const corpo = await res.json();
    if (typeof corpo?.detail === "string") return corpo.detail;
    if (Array.isArray(corpo?.detail) && typeof corpo.detail[0]?.msg === "string") {
      return corpo.detail[0].msg.replace(/^Value error, /, "");
    }
  } catch {
    // resposta sem JSON (ex.: 500 do proxy)
  }
  return padrao;
}

export async function listarDocumentos(token: string): Promise<{ documentos?: DocumentoDoNucleo[]; erro?: string }> {
  const res = await fetch(ROTA, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return { erro: await detalheDoErro(res, "Não foi possível carregar os documentos.") };
  const corpo = (await res.json()) as { documentos: DocumentoDoNucleo[] };
  return { documentos: corpo.documentos };
}

export async function lerTexto(token: string, id: string): Promise<{ texto?: string; erro?: string }> {
  const res = await fetch(`${ROTA}/${encodeURIComponent(id)}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return { erro: await detalheDoErro(res, "Não foi possível abrir o documento.") };
  const corpo = (await res.json()) as { texto: string | null };
  return { texto: corpo.texto ?? "" };
}

/** Publica a versão seguinte do tipo. Devolve a mensagem de erro, ou `null`. */
export async function publicarVersao(token: string, nova: NovaVersao): Promise<string | null> {
  const res = await fetch(ROTA, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ ...nova, texto: nova.texto.trim() || null }),
  });
  return res.ok ? null : detalheDoErro(res, "Não foi possível publicar a versão.");
}
