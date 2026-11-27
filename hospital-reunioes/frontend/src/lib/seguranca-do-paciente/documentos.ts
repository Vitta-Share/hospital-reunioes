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

/*
 * A assinatura eletrônica (issue #1771): o ato de designação, o Regimento e o
 * Plano vão para assinatura numa versão nova, que só vira a vigente quando
 * todos assinam. Até lá a anterior continua valendo.
 */

/** `diretoria_executiva` fica nos envios de antes do Responsável técnico (issue #2250, ADR 0112). */
export type QualidadeDoSignatario = "responsavel_tecnico" | "diretoria_executiva" | "presidencia";

export interface SignatarioDoDocumento {
  nome: string | null;
  qualidade: QualidadeDoSignatario;
  assinado_em: string | null;
}

export interface AssinaturaDoDocumento {
  documento_id: string;
  situacao: "gerado" | "enviado" | "assinado" | "cancelado";
  erro: string | null;
  enviado_em: string | null;
  assinado_em: string | null;
  pode_reenviar: boolean;
  signatarios: SignatarioDoDocumento[];
}

/** Os tipos que vão para assinatura eletrônica, com quem assina. */
export const TIPOS_COM_ASSINATURA: Partial<Record<TipoDeDocumento, string>> = {
  ato_designacao: "assinado pelo Responsável técnico",
  regimento: "assinado pelo Responsável técnico e pela Presidência do Núcleo",
  plano_seguranca_paciente: "assinado pelo Responsável técnico e pela Presidência do Núcleo",
};

export const ROTULO_DA_QUALIDADE: Record<QualidadeDoSignatario, string> = {
  responsavel_tecnico: "Responsável técnico",
  diretoria_executiva: "Diretoria Executiva",
  presidencia: "Presidência do Núcleo",
};

function cabecalhos(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function listarAssinaturas(token: string): Promise<AssinaturaDoDocumento[]> {
  const res = await fetch("/api/nsp/assinaturas-dos-documentos", { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) return [];
  const corpo = (await res.json()) as { assinaturas?: AssinaturaDoDocumento[] };
  return corpo.assinaturas ?? [];
}

/** Grava a versão nova fora da vigência e a manda para os signatários do tipo. */
export async function enviarParaAssinatura(
  token: string,
  nova: NovaVersao
): Promise<{ erro: string | null; aviso: string | null }> {
  const res = await fetch(`${ROTA}/assinatura`, {
    method: "POST",
    headers: cabecalhos(token),
    body: JSON.stringify({ ...nova, texto: nova.texto.trim() }),
  });
  if (!res.ok) return { erro: await detalheDoErro(res, "Não foi possível enviar para assinatura."), aviso: null };
  const corpo = (await res.json()) as { aviso?: string | null };
  return { erro: null, aviso: corpo.aviso ?? null };
}

/** Devolve a mensagem de erro, ou `null`. */
export async function reconsultarAssinatura(token: string, id: string): Promise<string | null> {
  const res = await fetch(`${ROTA}/${encodeURIComponent(id)}/assinatura/reconsultar`, {
    method: "POST",
    headers: cabecalhos(token),
  });
  return res.ok ? null : detalheDoErro(res, "Não foi possível reconsultar a assinatura.");
}

/** Devolve a mensagem de erro ou o aviso de falha do envio, ou `null`. */
export async function reenviarParaAssinatura(token: string, id: string): Promise<string | null> {
  const res = await fetch(`${ROTA}/${encodeURIComponent(id)}/assinatura/reenviar`, {
    method: "POST",
    headers: cabecalhos(token),
  });
  if (!res.ok) return detalheDoErro(res, "Não foi possível reenviar para assinatura.");
  const corpo = (await res.json()) as { aviso?: string | null };
  return corpo.aviso ?? null;
}

export async function linkDoArquivoAssinado(token: string, id: string): Promise<{ url?: string; erro?: string }> {
  const res = await fetch(`${ROTA}/${encodeURIComponent(id)}/arquivo-assinado`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return { erro: await detalheDoErro(res, "Não foi possível abrir o arquivo assinado.") };
  const corpo = (await res.json()) as { url: string };
  return { url: corpo.url };
}
