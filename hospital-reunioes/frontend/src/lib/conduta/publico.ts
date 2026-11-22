/**
 * O lado público do Canal de Conduta (issue #1846): os endereços das telas e a
 * leitura sem login.
 *
 * A leitura não manda cookie nem token de login (`credentials: "omit"`) e não
 * passa pelo cache. Com o canal fechado a API responde 404, e a leitura
 * devolve `null` para a tela dizer que a página não existe.
 */

export const ENDERECO_DO_CANAL = "/conduta";
export const ENDERECO_DA_PROTECAO = "/conduta/protecao";
export const ENDERECO_DO_DP = "/conduta/departamento-pessoal";
/** O formulário público da Ouvidoria, para paciente e acompanhante. */
export const ENDERECO_DA_OUVIDORIA = "/manifestacao";
/** O PDF do Código de Conduta vigente hoje, num endereço que não muda (issue #1841). */
export const ENDERECO_DO_CODIGO = "/api/conduta/codigo-de-conduta";

export const ROTA_DA_PROTECAO = "/api/conduta/protecao";
export const ROTA_DOS_TEXTOS = "/api/conduta/textos";

export interface TextoVigente {
  texto: string;
  versao: number;
  versao_id: string;
}

export interface BlocoDaProtecao {
  chave: string;
  titulo: string;
  texto: string;
  /** Nulo quando a coordenação ainda não salvou: é o texto inicial. */
  versao: number | null;
  versao_id: string | null;
}

export interface PaginaDeProtecao {
  /** O dia da versão arquivada mostrada; nulo é a de hoje. */
  em: string | null;
  blocos: BlocoDaProtecao[];
  /** Sem o contato salvo nas Configurações, nulo: o bloco não aparece. */
  encarregado: TextoVigente | null;
  /** Os dias em que a página mudou, do mais novo ao mais antigo. */
  versoes: string[];
}

export class FalhaDoCanal extends Error {}

export async function lerDoCanal<T>(caminho: string): Promise<T | null> {
  const res = await fetch(caminho, { credentials: "omit", cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new FalhaDoCanal("Não foi possível abrir a página. Tente de novo.");
  return (await res.json()) as T;
}

/** "15/11/2026", de um dia "2026-11-15". */
export function diaCurto(dia: string): string {
  const [ano, mes, d] = dia.split("-");
  return `${d}/${mes}/${ano}`;
}
