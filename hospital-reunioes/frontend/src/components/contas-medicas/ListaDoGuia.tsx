"use client";

/**
 * A lista da Mesa de trabalho (issue #1952, PRD #1933): todas as Linhas da
 * conta por dia e setor, com a contagem de cada grupo. Cada Linha mostra o
 * estado, o verbo, o nome e o valor, e o clique a torna o Item da vez. A
 * marcada fica apagada. O cabeçalho de cada dia tem o "Faltou isto" e o
 * "Marcar o dia como feito". A lista rola sozinha, ao lado do Item da vez.
 */

import { COR_DO_REENVIO, ESTADO_MARCADO, ETIQUETA } from "@/components/contas-medicas/ItemDaVez";
import {
  type GrupoGuia,
  ROTULO_ACAO,
  ROTULO_ESTADO,
  ROTULO_REENVIO,
  rotuloDoGrupo,
  valorComSinal,
} from "@/lib/contas-medicas/guia";

const COR_DO_ESTADO: Record<string, string> = {
  ABERTA: "bg-[#EEEEF6] text-primary",
  EM_VALIDACAO: "bg-[#FEF3C7] text-[#92400E]",
  DECIDIDA: "bg-[#FEF3C7] text-[#92400E]",
};

interface Props {
  grupos: GrupoGuia[];
  idDaVez: string | null;
  concluida: boolean;
  ocupado: boolean;
  onEscolher: (linhaId: string) => void;
  onFaltouIsto: (dia: string) => void;
  onMarcarODia: (grupo: GrupoGuia) => void;
}

function contagem(n: number): string {
  return n === 1 ? "1 item" : `${n} itens`;
}

export function ListaDoGuia({ grupos, idDaVez, concluida, ocupado, onEscolher, onFaltouIsto, onMarcarODia }: Props) {
  return (
    <section
      aria-label="Itens da conta"
      className="min-w-0 space-y-4 overflow-y-auto max-h-[60vh] min-[1000px]:max-h-[calc(100vh-16rem)] pr-1"
    >
      {grupos.map((grupo) => {
        const rotulo = rotuloDoGrupo(grupo);
        return (
          <section key={rotulo} aria-label={rotulo} className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <h2 className="text-xs font-semibold uppercase tracking-[0.04em] text-slate-500">{rotulo}</h2>
              <span className="text-xs text-slate-400">{contagem(grupo.linhas.length)}</span>
              <div className="ml-auto flex flex-wrap items-center gap-3">
                {grupo.data && (
                  <button
                    type="button"
                    onClick={() => onFaltouIsto(grupo.data as string)}
                    className="text-xs font-semibold text-primary hover:underline"
                  >
                    Faltou isto
                  </button>
                )}
                {!concluida && grupo.linhas.some((linha) => linha.estado === "ABERTA" && linha.acao !== "VALIDAR") && (
                  <button
                    type="button"
                    onClick={() => onMarcarODia(grupo)}
                    disabled={ocupado}
                    className="text-xs font-semibold text-primary hover:underline disabled:opacity-50"
                  >
                    Marcar o dia como feito
                  </button>
                )}
              </div>
            </div>
            <ul className="space-y-1">
              {grupo.linhas.map((linha) => {
                const daVez = linha.id === idDaVez;
                const marcado = linha.acao === "VALIDAR" ? undefined : ESTADO_MARCADO[linha.estado];
                return (
                  <li key={linha.id}>
                    <button
                      type="button"
                      aria-current={daVez ? "true" : undefined}
                      onClick={() => onEscolher(linha.id)}
                      className={`w-full rounded-lg border px-3 py-2 text-left flex flex-wrap items-center gap-x-2 gap-y-1 ${
                        daVez ? "border-primary bg-[#EEEEF6]" : "border-border bg-white hover:border-slate-300"
                      } ${marcado ? "opacity-60" : ""}`}
                    >
                      <span className={`${ETIQUETA} ${marcado?.cor ?? COR_DO_ESTADO[linha.estado] ?? ""}`}>
                        {ROTULO_ESTADO[linha.estado]}
                      </span>
                      <span className="text-xs font-semibold text-slate-500">{ROTULO_ACAO[linha.acao]}</span>
                      <span className="min-w-0 flex-1 break-words text-sm text-slate-800 normal-case">
                        {linha.descricao ?? linha.codigo ?? "Linha do guia"}
                      </span>
                      {linha.reenvio && (
                        <span className={`${ETIQUETA} ${COR_DO_REENVIO[linha.reenvio]}`}>
                          {ROTULO_REENVIO[linha.reenvio]}
                        </span>
                      )}
                      {linha.valor_diferenca != null && (
                        <span className="text-sm text-slate-600">{valorComSinal(linha.valor_diferenca)}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </section>
  );
}
