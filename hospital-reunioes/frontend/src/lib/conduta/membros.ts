/**
 * A tela Membros do Comitê de Conduta (issue #1822, PRD #1786, ADR 0097).
 * Os tipos do que a API devolve e os rótulos da tela.
 */
export { chamarNsp as chamarConduta, formatarDia, hojeLocal } from "@/lib/seguranca-do-paciente/membros";

export type Cadeira = "coordenacao" | "segundo_leitor" | "membro" | "suplente";
export type Situacao = "vigente" | "a_comecar" | "vencida" | "encerrada";

export interface MembroDoComite {
  id: string;
  participante_id: string;
  nome: string | null;
  papel: Cadeira;
  cadeira: string;
  e_diretor: boolean;
  vigencia_inicio: string;
  vigencia_fim: string;
  encerrada_em: string | null;
  termo_assinado: boolean;
  situacao: Situacao;
}

export interface ListaDeMembros {
  data: string | null;
  pode_cadastrar: boolean;
  membros: MembroDoComite[];
}

export interface LinhaDoRegistro {
  acao: "inclusao" | "encerramento" | "perfil_dado" | "perfil_tirado";
  pessoa: string | null;
  autor: string | null;
  detalhe: string;
  registrado_em: string;
}

export const ROTA_DOS_MEMBROS = "/api/comite-de-conduta/membros";

export const CADEIRAS: readonly { valor: Cadeira; rotulo: string }[] = [
  { valor: "coordenacao", rotulo: "Coordenação" },
  { valor: "membro", rotulo: "Membro" },
  { valor: "segundo_leitor", rotulo: "Membro e segundo leitor" },
  { valor: "suplente", rotulo: "Suplente" },
];

export const LABEL_SITUACAO: Record<Situacao, string> = {
  vigente: "Vigente",
  a_comecar: "A começar",
  vencida: "Vencida",
  encerrada: "Encerrada",
};

export const COR_SITUACAO: Record<Situacao, string> = {
  vigente: "bg-emerald-50 text-emerald-700",
  a_comecar: "bg-sky-50 text-sky-700",
  vencida: "bg-amber-50 text-amber-800",
  encerrada: "bg-slate-100 text-slate-600",
};

export const LABEL_ACAO_DO_REGISTRO: Record<LinhaDoRegistro["acao"], string> = {
  inclusao: "Entrou no Comitê",
  encerramento: "Saiu do Comitê",
  perfil_dado: "Recebeu o perfil de cadastro",
  perfil_tirado: "Perdeu o perfil de cadastro",
};
