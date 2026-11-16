/**
 * Os membros do Núcleo (issue #1766): os tipos que a API devolve, os rótulos
 * da tela e a chamada autenticada às rotas do módulo.
 */
import { createClient } from "@/lib/supabase/client";

export type Papel = "presidencia" | "suplente" | "membro";

export type EstadoDoMembro =
  | "cadastrado"
  | "documento_gerado"
  | "aguardando_assinatura"
  | "ativo"
  | "a_vencer"
  | "em_carencia"
  | "vencido"
  | "encerrado";

export interface Membro {
  id: string;
  participante_id: string;
  nome: string | null;
  papel: Papel;
  area: string | null;
  conselho_profissional: string | null;
  registro_profissional: string | null;
  registro_uf: string | null;
  vigencia_inicio: string;
  vigencia_fim: string;
  encerrada_em: string | null;
  termo_gerado_em?: string | null;
  termo_enviado_em?: string | null;
  termo_assinado_em: string | null;
  estado: EstadoDoMembro;
  /** O servidor diz se há Termo à espera da assinatura (issue #1769). */
  termo_pendente?: boolean;
  /** Na resposta do cadastro, da renovação, da edição e do reenvio: por que o Termo não saiu (issues #1768 e #1769). */
  aviso_termo?: string | null;
}

/** O último envio do Termo de Adesão de um membro (issue #1768). */
export interface EnvioDoTermo {
  situacao: "gerado" | "enviado" | "assinado" | "cancelado" | null;
  erro: string | null;
  enviado_em: string | null;
  documento_url: string | null;
}

export interface LinhaDaTrilha {
  acao: string;
  campo: string | null;
  valor_anterior: string | null;
  valor_novo: string | null;
  motivo?: string | null;
  autor: string | null;
  created_at: string;
}

export const PAPEIS: Papel[] = ["presidencia", "suplente", "membro"];

export const LABEL_PAPEL: Record<Papel, string> = {
  presidencia: "Presidência",
  suplente: "Suplente da Presidência",
  membro: "Membro",
};

export const LABEL_ESTADO: Record<EstadoDoMembro, string> = {
  cadastrado: "Cadastrado",
  documento_gerado: "Documento gerado",
  aguardando_assinatura: "Aguardando assinatura",
  ativo: "Ativo",
  a_vencer: "A vencer",
  em_carencia: "Em carência",
  vencido: "Vencido",
  encerrado: "Encerrado",
};

export const COR_ESTADO: Record<EstadoDoMembro, string> = {
  cadastrado: "bg-slate-100 text-slate-600",
  documento_gerado: "bg-slate-100 text-slate-600",
  aguardando_assinatura: "bg-amber-100 text-amber-700",
  ativo: "bg-emerald-100 text-emerald-700",
  a_vencer: "bg-amber-100 text-amber-700",
  em_carencia: "bg-orange-100 text-orange-700",
  vencido: "bg-red-100 text-red-700",
  encerrado: "bg-slate-100 text-slate-500",
};

export const LABEL_CAMPO: Record<string, string> = {
  papel: "Papel",
  area: "Área",
  vigencia_inicio: "Início da vigência",
  vigencia_fim: "Fim da vigência",
  encerrada_em: "Encerrada em",
  conselho_profissional: "Conselho",
  registro_profissional: "Número do registro",
  registro_uf: "UF do registro",
};

export const LABEL_ACAO: Record<string, string> = {
  cadastro: "Cadastro",
  edicao: "Edição",
  renovacao: "Renovação",
  mudanca_de_papel: "Mudança de papel",
  encerramento: "Encerramento",
  termo_enviado: "Termo enviado para assinatura",
  termo_reenviado: "Termo reenviado",
  termo_assinado: "Termo assinado",
  liberacao_manual: "Liberação sem assinatura",
};

/** As ações da trilha que são do Termo: a tela não mostra o "de, para" delas. */
export const ACOES_DO_TERMO = new Set(["termo_enviado", "termo_reenviado", "termo_assinado", "liberacao_manual"]);

/** "2027-06-30" vira "30/06/2027", sem passar por fuso. */
export function formatarDia(iso: string | null): string {
  if (!iso) return "";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

/** O dia, em São Paulo, de um carimbo de data e hora. */
export function diaDoCarimbo(carimbo: string): string {
  return new Date(carimbo).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

export function registroDoMembro(m: Membro): string {
  if (!m.conselho_profissional && !m.registro_profissional) return "Sem registro";
  const uf = m.registro_uf ? `/${m.registro_uf}` : "";
  return [m.conselho_profissional, `${m.registro_profissional ?? ""}${uf}`].filter(Boolean).join(" ");
}

/**
 * O membro tem um Termo à espera da assinatura (issue #1769). Vale a conta do
 * servidor (`termo_pendente`), que também enxerga a revisão material do
 * Regimento e o Termo novo que nem chegou a ser gerado. Sem ela: nunca
 * assinou, ou o último documento foi gerado depois da última assinatura.
 */
export function termoPendente(m: Membro): boolean {
  if (typeof m.termo_pendente === "boolean") return m.termo_pendente;
  if (!m.termo_assinado_em) return true;
  if (!m.termo_gerado_em) return false;
  return new Date(m.termo_gerado_em).getTime() > new Date(m.termo_assinado_em).getTime();
}

export function situacaoDoTermo(m: Membro): string {
  return m.termo_assinado_em ? `Assinado em ${diaDoCarimbo(m.termo_assinado_em)}` : "Sem Termo";
}

export function hojeLocal(): string {
  const agora = new Date();
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  const dia = String(agora.getDate()).padStart(2, "0");
  return `${agora.getFullYear()}-${mes}-${dia}`;
}

/** Chama uma rota do módulo com o token da sessão. Erro vira exceção com a mensagem do servidor. */
export async function chamarNsp<T>(caminho: string, opcoes: { method?: string; body?: unknown } = {}): Promise<T> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const headers: Record<string, string> = { Authorization: `Bearer ${session?.access_token ?? ""}` };
  if (opcoes.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(caminho, {
    method: opcoes.method ?? "GET",
    headers,
    body: opcoes.body !== undefined ? JSON.stringify(opcoes.body) : undefined,
  });
  if (!res.ok) {
    const corpo = await res.json().catch(() => null);
    const detalhe = typeof corpo?.detail === "string" ? corpo.detail : "Não foi possível concluir. Tente de novo.";
    throw new Error(detalhe);
  }
  return (await res.json()) as T;
}
