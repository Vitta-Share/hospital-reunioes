/**
 * O lado do Comitê do Canal de Conduta (issue #1824): os tipos que a API
 * devolve, os rótulos da tela e a chamada autenticada às rotas do módulo.
 *
 * Quem decide o que cada pessoa pode fazer é o servidor: a caixa "O QUE FAZER
 * AGORA" chega pronta, com o motivo do botão bloqueado.
 */
import type { Afastamento } from "@/lib/conduta/afastamento";
import type { AnexoDoRelato } from "@/lib/conduta/anexos";
import type { AtaDoCaso, ReuniaoDoComite } from "@/lib/conduta/ata";
import type { Depoimento } from "@/lib/conduta/depoimentos";
import type { GuardaDoCaso } from "@/lib/conduta/guarda";
import type { MensagensDoCaso } from "@/lib/conduta/mensagens";
import type { TextoDaApuracao } from "@/lib/conduta/relatorio";
import type { VerificacaoDeRetaliacao } from "@/lib/conduta/retaliacao";
import type { MedidaERetorno } from "@/lib/conduta/retorno";
import type { TrilhaDoCaso } from "@/lib/conduta/trilha";
import type { Trava, Votacao } from "@/lib/conduta/voto";
import { createClient } from "@/lib/supabase/client";
import type { SugestaoDoAgente } from "@/lib/conduta/sugestao";

export type Rito = "encaminhamento" | "rapido" | "completo" | "especial";
export type Escopo = "dentro" | "fora" | "misto";
export type Situacao = "em_triagem" | "em_andamento" | "encerrado";

export interface ItemDaMinhaVez {
  id: string;
  protocolo: string;
  etapa: string | null;
  rito: Rito | null;
  acao: string;
  prazo_em: string | null;
  prazo_vencido: boolean;
  faltam_dias: number | null;
}

export interface CasoDaLista {
  id: string;
  protocolo: string;
  etapa: string | null;
  rito: Rito | null;
  categoria: string | null;
  situacao: Situacao;
  prazo_em: string | null;
  prazo_vencido: boolean;
  faltam_dias: number | null;
  /** De onde o caso veio: a página pública ou a sinalização do ouvidor (issue #1849). */
  origem?: "canal" | "ouvidoria" | null;
  /** Conteúdo eliminado ao fim da guarda (issue #1838). */
  eliminado_em?: string | null;
}

export interface Caixa {
  frase: string;
  botao: string | null;
  como_fazer: string[];
  acao: string | null;
  bloqueio: string | null;
}

export interface Contestacao {
  escopo: Escopo;
  categoria: string;
  rito: Rito;
  destino: string | null;
  motivo: string;
  votos: number;
  resultado: "mantida" | "acatada" | null;
}

/** A nota do Comitê ao Núcleo de Segurança do Paciente (issue #1850). */
export interface NotaAoNucleo {
  texto: string;
  escrita_em: string | null;
  /** Sem data, a nota espera a coordenação enviar. */
  enviada_em: string | null;
}

/** Quem foi convidado para o caso e o termo dele (issue #1825). */
export interface Convidado {
  participante_id: string;
  nome: string | null;
  motivo: "apurador" | "cipa";
  papel: string;
  termo: "assinado" | "aguardando_assinatura" | "nao_enviado";
}

export interface MembroDoCaso {
  id: string;
  nome: string | null;
  papel: string;
}

export interface ContestacaoDeParticipacao {
  id: string;
  contestado: string | null;
  motivo: string;
  votos: number;
  resultado: "confirmada" | "rejeitada" | null;
  pode_decidir: boolean;
}

export interface Citado {
  id: string;
  nome: string | null;
  ligado: boolean;
}

export interface CasoAberto extends CasoDaLista {
  membros_do_caso: MembroDoCaso[];
  pode_contestar_participacao: boolean;
  contestacoes_de_participacao: ContestacaoDeParticipacao[];
  citados: Citado[];
  /** Nulo depois da eliminação ao fim da guarda (issue #1838). */
  relato: string | null;
  // O nome de quem relatou com identificação (issue #1843); nulo no anônimo.
  relator_nome?: string | null;
  // Os anexos do relato, já sem os dados de origem (issue #1844).
  anexos?: AnexoDoRelato[];
  escopo: Escopo | null;
  destino: string | null;
  papel: string | null;
  trilho: { nome: string; estado: "concluida" | "atual" | "pendente" }[];
  o_que_fazer_agora: Caixa;
  contestacao: Contestacao | null;
  pode_contestar: boolean;
  prorrogacao: { justificativa: string | null; bloqueio: string | null } | null;
  orientacao: string | null;
  triagem_em: string | null;
  conferida_em: string | null;
  encerrado_em: string | null;
  desfecho: string | null;
  sugestao_do_agente?: SugestaoDoAgente;
  notas_ao_nsp?: NotaAoNucleo[];
  /** Os cartões da Apuração (issue #1830). */
  depoimentos: Depoimento[];
  avanco_da_apuracao: string | null;
  /** O relatório de apuração e a cronologia dos fatos (issue #1832). */
  relatorio?: TextoDaApuracao | null;
  cronologia?: TextoDaApuracao | null;
  pode_redigir_relatorio?: boolean;
  /** O "Não sei" no passo 3 ou o sinal do agente, num caso da fila comum (issue #1829). */
  aviso_de_rota_especial?: string | null;
  pode_desviar?: boolean;
  rota_especial?: RotaEspecialDoCaso | null;
  /** O voto e a trava de robustez (issue #1833). */
  votacao?: Votacao | null;
  trava?: Trava | null;
  /** A ata de deliberação e a reunião do Comitê (issue #1834). */
  ata?: AtaDoCaso | null;
  reuniao?: ReuniaoDoComite | null;
  /** O afastamento cautelar (issue #1836). */
  rota?: "comum" | "especial" | null;
  afastamentos?: Afastamento[];
  pode_registrar_afastamento?: boolean;
  /** A decisão da Direção, o retorno e a correção de processo (issue #1835). */
  medida_e_retorno?: MedidaERetorno | null;
  /** A verificação de retaliação do caso concluído (issue #1839). */
  verificacao_de_retaliacao?: VerificacaoDeRetaliacao | null;
  /** A trilha do caso com as gavetas e o Dossiê (issue #1837). */
  trilha?: TrilhaDoCaso | null;
  /** O papel original, a guarda e o congelamento (issue #1838). */
  guarda?: GuardaDoCaso | null;
  /** A conversa com quem relatou pela página de acompanhamento (issue #1845). */
  mensagens?: MensagensDoCaso | null;
}

/** O que o Grupo Especial vê do caso dele (issue #1829). */
export interface RotaEspecialDoCaso {
  selo: { selado_em: string; codigo: string; confere: boolean } | null;
  nao_respondido_no_prazo: boolean;
  entrega: { destinatario: string; entregue_em: string } | null;
  pode_registrar_entrega: boolean;
}

/** O que se vê da Rota Especial de fora do grupo: só a contagem (issue #1829). */
export interface ContagemDaRotaEspecial {
  recebidos: number;
  concluidos: number;
  em_aberto: number;
}

export const RITOS: { valor: Rito; rotulo: string; prazo: string }[] = [
  { valor: "encaminhamento", rotulo: "Encaminhamento", prazo: "5 dias úteis" },
  { valor: "rapido", rotulo: "Rápido", prazo: "20 dias corridos" },
  { valor: "completo", rotulo: "Completo", prazo: "30 dias corridos, prorrogável uma vez" },
];

export const ESCOPOS: { valor: Escopo; rotulo: string }[] = [
  { valor: "dentro", rotulo: "Dentro do canal" },
  { valor: "fora", rotulo: "Fora do canal" },
  { valor: "misto", rotulo: "Misto" },
];

export const CATEGORIAS: { valor: string; rotulo: string }[] = [
  { valor: "A", rotulo: "A. Conduta e relações" },
  { valor: "B", rotulo: "B. Patrimônio" },
  { valor: "C", rotulo: "C. Integridade nos negócios" },
  { valor: "D", rotulo: "D. Registros e informação" },
  { valor: "E", rotulo: "E. Segurança e conformidade" },
  { valor: "F", rotulo: "F. Não sei classificar" },
];

export const DESTINOS: { valor: string; rotulo: string }[] = [
  { valor: "dp", rotulo: "Departamento Pessoal" },
  { valor: "ouvidoria", rotulo: "Ouvidoria" },
  { valor: "nsp", rotulo: "Núcleo de Segurança do Paciente" },
  { valor: "gestor", rotulo: "Liderança direta ou DP" },
];

/** Os motivos de impedimento da especificação (seção 3.3). */
export const MOTIVOS_DE_IMPEDIMENTO: { valor: string; rotulo: string }[] = [
  { valor: "parte", rotulo: "Parte do caso" },
  { valor: "chefia_direta", rotulo: "Chefia direta de envolvido" },
  { valor: "parentesco", rotulo: "Parentesco" },
  { valor: "relacao_pessoal", rotulo: "Relação pessoal" },
  { valor: "interesse", rotulo: "Interesse no resultado" },
];

export const SITUACOES:{ valor: Situacao; rotulo: string }[] = [
  { valor: "em_triagem", rotulo: "Em triagem" },
  { valor: "em_andamento", rotulo: "Em andamento" },
  { valor: "encerrado", rotulo: "Encerrado" },
];

const ETAPAS: Record<string, string> = {
  triagem: "Triagem",
  contestada: "Triagem contestada",
  encaminhamento: "Encaminhamento",
  apuracao: "Apuração",
  voto: "Voto",
  ata: "Ata",
  medida: "Medida",
  retorno: "Retorno",
  encerrado: "Encerrado",
  acompanhamento: "Acompanhamento",
};

export function rotuloDaEtapa(etapa: string | null): string {
  return ETAPAS[etapa ?? "triagem"] ?? etapa ?? "Triagem";
}

export function rotuloDoRito(rito: Rito | null): string {
  if (rito === "especial") return "Rota Especial";
  return RITOS.find((r) => r.valor === rito)?.rotulo ?? "Rito ainda não definido";
}

/** "Faltam 12 dias", "Vence hoje", "Venceu há 3 dias". */
export function textoDoPrazo(faltam: number | null, encerrado = false): string {
  if (encerrado) return "Encerrado";
  if (faltam === null) return "Prazo depois da triagem";
  if (faltam > 1) return `Faltam ${faltam} dias`;
  if (faltam === 1) return "Falta 1 dia";
  if (faltam === 0) return "Vence hoje";
  return faltam === -1 ? "Venceu há 1 dia" : `Venceu há ${-faltam} dias`;
}

export async function chamarComite<T>(caminho: string, opcoes: { method?: string; body?: unknown } = {}): Promise<T> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const headers: Record<string, string> = { Authorization: `Bearer ${session?.access_token ?? ""}` };
  if (opcoes.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api/comite-de-conduta${caminho}`, {
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
