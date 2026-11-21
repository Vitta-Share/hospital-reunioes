"use client";

import { useState } from "react";
import { Archive, ArchiveRestore } from "lucide-react";

import { Dica } from "@/components/ui/Dica";
import {
  DICA_DO_ARQUIVAR,
  DICA_DO_DESARQUIVAR,
  agruparPorCompetencia,
  alvoDoMes,
  botaoDaConfirmacao,
  dicaDoArquivarOMes,
  perguntaDoMes,
  tituloDaCompetencia,
} from "@/lib/contas-medicas/arquivo";
import type { ItemDaFila } from "@/lib/contas-medicas/envio";

import { ListaDeContas } from "./ListaDeContas";

/**
 * As etapas Concluídas e Arquivadas (issue #1958, ADR 0105): as contas
 * agrupadas por Competência, o mês mais recente primeiro, cada grupo com o
 * número de contas. Em Concluídas, cada conta que a pessoa pode arquivar tem
 * "Arquivar", e o cabeçalho do mês tem "Arquivar o mês", que pergunta na
 * própria lista antes de arquivar. Em Arquivadas, cada conta que a pessoa
 * pode mexer tem "Desarquivar". Pode a faturista da conta e quem tem o
 * painel completo (`todas`); o servidor confere de novo.
 */

const BOTAO = "inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold";
const SECUNDARIO = `${BOTAO} border border-border text-slate-700 hover:bg-slate-50`;

export function ContasPorCompetencia({
  etapa,
  contas,
  todasDoMes,
  todas,
  onArquivar,
  onDesarquivar,
  onArquivarOMes,
}: {
  etapa: "concluidas" | "arquivadas";
  /** As contas que a tela mostra, já recortadas por "Todas" ou "Minhas". */
  contas: ItemDaFila[];
  /** As contas do mês sem o recorte: é delas que o "Arquivar o mês" conta. */
  todasDoMes: (mes: string | null) => ItemDaFila[];
  todas: boolean;
  onArquivar: (conta: ItemDaFila) => void;
  onDesarquivar: (conta: ItemDaFila) => void;
  onArquivarOMes: (mes: string) => void;
}) {
  const [confirmando, setConfirmando] = useState<string | null>(null);
  const pode = (conta: ItemDaFila) => todas || Boolean(conta.minha);

  const extra = (conta: ItemDaFila) => {
    if (!pode(conta)) return null;
    if (etapa === "arquivadas") {
      return (
        <Dica texto={DICA_DO_DESARQUIVAR} abrePara="esquerda">
          <button type="button" onClick={() => onDesarquivar(conta)} className={SECUNDARIO}>
            <ArchiveRestore className="h-3.5 w-3.5" aria-hidden="true" />
            Desarquivar
          </button>
        </Dica>
      );
    }
    return (
      <Dica texto={DICA_DO_ARQUIVAR} abrePara="esquerda">
        <button type="button" onClick={() => onArquivar(conta)} className={SECUNDARIO}>
          <Archive className="h-3.5 w-3.5" aria-hidden="true" />
          Arquivar
        </button>
      </Dica>
    );
  };

  return (
    <div className="divide-y divide-border">
      {agruparPorCompetencia(contas).map(({ competencia, contas: doMes }) => {
        const titulo = tituloDaCompetencia(competencia);
        const alvo = competencia ? alvoDoMes(todasDoMes(competencia), todas) : [];
        const perguntando = competencia !== null && confirmando === competencia;
        return (
          <section key={competencia ?? "sem-mes"} aria-label={titulo}>
            <div className="flex flex-wrap items-center justify-between gap-2 bg-slate-50 px-5 py-2">
              <h3 className="text-sm font-semibold text-slate-800">
                {titulo}{" "}
                <span className="font-normal text-slate-500">
                  {doMes.length === 1 ? "1 conta" : `${doMes.length} contas`}
                </span>
              </h3>
              {etapa === "concluidas" && competencia && alvo.length > 0 && !perguntando && (
                <Dica texto={dicaDoArquivarOMes(todas)} abrePara="esquerda">
                  <button type="button" onClick={() => setConfirmando(competencia)} className={SECUNDARIO}>
                    <Archive className="h-3.5 w-3.5" aria-hidden="true" />
                    Arquivar o mês
                  </button>
                </Dica>
              )}
            </div>
            {perguntando && (
              <div
                role="group"
                aria-label="Confirmar o arquivar do mês"
                className="flex flex-wrap items-center justify-between gap-3 border-y border-amber-100 bg-amber-50 px-5 py-3"
              >
                <p className="text-sm text-amber-900">{perguntaDoMes(alvo, competencia)}</p>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setConfirmando(null)} className={SECUNDARIO}>
                    Cancelar
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmando(null);
                      onArquivarOMes(competencia);
                    }}
                    className={`${BOTAO} bg-primary text-white hover:bg-primary/90`}
                  >
                    {botaoDaConfirmacao(alvo)}
                  </button>
                </div>
              </div>
            )}
            <ListaDeContas contas={doMes} abreAlheias={todas} extra={extra} />
          </section>
        );
      })}
    </div>
  );
}
