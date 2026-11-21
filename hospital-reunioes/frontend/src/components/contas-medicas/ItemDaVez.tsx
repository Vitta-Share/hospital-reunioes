"use client";

/**
 * O Item da vez da Mesa de trabalho (issue #1952, PRD #1933; antes a linha
 * aberta do Guia, issue #1121).
 *
 * A Linha em que a faturista está, grande: a posição, o dia e o setor, o
 * verbo, o nome, o código que copia com um clique, o que fazer (quantidade e
 * quando), o valor, o motivo e a Evidência já aberta. Embaixo, Feito, Não
 * procede e Bloqueado, cada um com a Legenda. Marcada, mostra o estado e o
 * Desfazer. A Validar não tem botão: o item já foi para a validação. A tela
 * não decide nada; quem recusa é o servidor.
 */

import { useState } from "react";
import { Copy } from "lucide-react";

import { Ditar, juntarDitado } from "@/components/contas-medicas/Ditar";
import { Dica } from "@/components/ui/Dica";
import { Legenda } from "@/components/ui/Legenda";
import {
  DICA_DO_NIVEL,
  ETIQUETA_SE_NECESSARIO,
  type LinhaGuia,
  type MotivoNaoProcede,
  MOTIVOS_NAO_PROCEDE,
  motivoInicialDoNaoProcede,
  ROTULO_ACAO,
  ROTULO_NIVEL,
  ROTULO_REENVIO,
  reais,
  textoDaLinha,
  valorComSinal,
} from "@/lib/contas-medicas/guia";

export interface Marcacao {
  estado: "FEITO" | "NAO_PROCEDE" | "BLOQUEADO";
  motivo?: MotivoNaoProcede;
  texto?: string;
}

interface Props {
  linha: LinhaGuia;
  posicao: number;
  total: number;
  /** "03/10 · CTI": o dia e o setor do grupo da Linha. */
  grupo: string;
  concluida: boolean;
  ocupado: boolean;
  onMarcar: (marcacao: Marcacao) => void;
  onDesfazer: () => void;
  onCopiar: (codigo: string) => void;
}

export const ETIQUETA =
  "inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-[0.04em]";

export const ESTADO_MARCADO: Record<string, { rotulo: string; cor: string }> = {
  FEITO: { rotulo: "Feito", cor: "bg-[#DCFCE7] text-[#166534]" },
  NAO_PROCEDE: { rotulo: "Não procede", cor: "bg-[#F1F5F9] text-[#475569]" },
  BLOQUEADO: { rotulo: "Bloqueado", cor: "bg-[#FEF3C7] text-[#92400E]" },
};

export const COR_DO_REENVIO = {
  CORRIGIDA: "bg-[#DCFCE7] text-[#166534]",
  AINDA_NA_CONTA: "bg-[#FEE2E2] text-[#991B1B]",
} as const;

const BOTAO = "px-4 py-2 rounded-lg text-sm font-semibold uppercase tracking-[0.04em] disabled:opacity-50";
const ROTULO = "text-xs font-semibold uppercase tracking-[0.04em] text-slate-500";

export function ItemDaVez({ linha, posicao, total, grupo, concluida, ocupado, onMarcar, onDesfazer, onCopiar }: Props) {
  const [naoProcedeAberto, setNaoProcedeAberto] = useState(false);
  const [motivo, setMotivo] = useState<MotivoNaoProcede | null>(() => motivoInicialDoNaoProcede(linha));
  const [texto, setTexto] = useState("");

  const nome = linha.descricao ?? linha.codigo ?? "Linha do guia";
  const validar = linha.acao === "VALIDAR";
  const marcado = validar ? undefined : ESTADO_MARCADO[linha.estado];
  // A Validação decidiu (issue #1142): com ação, volta para a faturista lançar;
  // sem ação (Validar descartado), não há nada a fazer no MV.
  const decidida = linha.estado === "DECIDIDA";

  const textoObrigatorio = motivo === "OUTRO";
  const podeConfirmar = motivo !== null && (!textoObrigatorio || texto.trim() !== "");

  function confirmarNaoProcede() {
    if (!motivo) return;
    const limpo = texto.trim();
    onMarcar({ estado: "NAO_PROCEDE", motivo, ...(limpo ? { texto: limpo } : {}) });
    setNaoProcedeAberto(false);
  }

  return (
    <div className="space-y-4 min-w-0">
      <p className="text-xs text-slate-500">
        <span>
          Item {posicao} de {total}
        </span>
        <span aria-hidden="true"> · </span>
        <span>{grupo}</span>
      </p>

      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`${ETIQUETA} ${validar ? "bg-[#FEF3C7] text-[#92400E]" : "bg-[#EEEEF6] text-primary"}`}>
          {ROTULO_ACAO[linha.acao]}
        </span>
        {marcado && <span className={`${ETIQUETA} ${marcado.cor}`}>{marcado.rotulo}</span>}
        {linha.reenvio && (
          <span className={`${ETIQUETA} ${COR_DO_REENVIO[linha.reenvio]}`}>{ROTULO_REENVIO[linha.reenvio]}</span>
        )}
        {linha.nivel_evidencia === "PRESCRITO_SN" && (
          <span className={`${ETIQUETA} bg-[#FEF3C7] text-[#92400E]`}>{ETIQUETA_SE_NECESSARIO}</span>
        )}
        {decidida && !validar && (
          <span className={`${ETIQUETA} bg-[#FEF3C7] text-[#92400E]`}>Decidida na validação</span>
        )}
        {linha.nao_conferido && <span className={`${ETIQUETA} bg-[#F1F5F9] text-[#475569]`}>Não conferido</span>}
        {linha.confianca === "BAIXA" && (
          <span className={`${ETIQUETA} bg-[#FEF3C7] text-[#92400E]`}>conferir evidência</span>
        )}
      </div>

      <h2 className="text-2xl font-bold text-slate-900 break-words">
        <span className="normal-case">{nome}</span>
      </h2>
      <p className="text-lg text-slate-800 break-words">{textoDaLinha(linha)}</p>

      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {linha.codigo && (
          <div>
            <dt className={ROTULO}>Código</dt>
            <dd>
              <button
                type="button"
                aria-label={`Copiar código ${linha.codigo}`}
                onClick={() => onCopiar(linha.codigo as string)}
                className="inline-flex items-center gap-1.5 font-mono text-lg normal-case text-primary hover:underline"
              >
                {linha.codigo}
                <Copy className="w-4 h-4" aria-hidden="true" />
              </button>
            </dd>
          </div>
        )}
        {!validar && linha.valor_diferenca != null && (
          <div>
            <dt className={ROTULO}>Valor</dt>
            <dd className="text-lg font-semibold text-slate-900">{valorComSinal(linha.valor_diferenca)}</dd>
          </div>
        )}
        {linha.regra_codigo && (
          <div>
            <dt className={ROTULO}>Regra</dt>
            <dd className="text-sm text-slate-700">{linha.regra_codigo}</dd>
          </div>
        )}
      </dl>

      {linha.motivo && <p className="text-sm text-slate-700 break-words">{linha.motivo}</p>}

      {(linha.evidencia_pagina != null || linha.evidencia_trecho) && (
        <div className="rounded-lg bg-slate-50 border border-border px-3 py-2 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={ROTULO}>Evidência</span>
            {linha.evidencia_pagina != null && (
              <span className="text-xs font-semibold text-slate-700">Prontuário, p. {linha.evidencia_pagina}</span>
            )}
            {linha.nivel_evidencia && (
              <Dica texto={DICA_DO_NIVEL[linha.nivel_evidencia]}>
                <span tabIndex={0} className={`${ETIQUETA} bg-[#EEEEF6] text-primary`}>
                  {ROTULO_NIVEL[linha.nivel_evidencia]}
                </span>
              </Dica>
            )}
          </div>
          {linha.evidencia_trecho && (
            <blockquote className="text-sm text-slate-600 break-words border-l-2 border-border pl-2">
              {linha.evidencia_trecho}
            </blockquote>
          )}
        </div>
      )}

      {validar && decidida ? (
        <p className="text-sm text-slate-500">Decidida na validação, sem ação no MV</p>
      ) : validar ? (
        <div className="text-sm text-[#92400E] space-y-0.5">
          <p>Nada a decidir aqui: o item já foi para a validação</p>
          {linha.valor_diferenca != null && (
            <p className="font-semibold">Em jogo: R$ {reais(Math.abs(linha.valor_diferenca))}</p>
          )}
        </div>
      ) : marcado ? (
        !concluida && (
          <button
            type="button"
            onClick={onDesfazer}
            disabled={ocupado}
            className={`${BOTAO} border border-border text-slate-700 bg-white`}
          >
            Desfazer
          </button>
        )
      ) : (
        !concluida && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 border-t border-border pt-4">
            <div>
              <button
                type="button"
                onClick={() => onMarcar({ estado: "FEITO" })}
                disabled={ocupado}
                className={`${BOTAO} w-full bg-primary text-white`}
              >
                Feito
              </button>
              <Legenda className="text-xs">Você já corrigiu no MV. A tela passa para o próximo item.</Legenda>
            </div>
            <div>
              <button
                type="button"
                onClick={() => setNaoProcedeAberto((aberto) => !aberto)}
                disabled={ocupado}
                className={`${BOTAO} w-full border border-border text-slate-700 bg-white`}
              >
                Não procede
              </button>
              <Legenda className="text-xs">O item está errado. Diga o motivo, que vai para a gestão.</Legenda>
            </div>
            <div>
              <button
                type="button"
                onClick={() => onMarcar({ estado: "BLOQUEADO" })}
                disabled={ocupado}
                className={`${BOTAO} w-full border border-border text-slate-700 bg-white`}
              >
                Bloqueado
              </button>
              <Legenda className="text-xs">O MV não deixou lançar, por falta de cadastro ou de preço.</Legenda>
            </div>
          </div>
        )
      )}

      {naoProcedeAberto && !validar && !marcado && !concluida && (
        <fieldset className="rounded-lg border border-border px-3 py-2 space-y-2">
          <legend className="px-1 text-xs font-semibold text-slate-700">Por que não procede?</legend>
          <div className="flex flex-col gap-1">
            {MOTIVOS_NAO_PROCEDE.map((opcao) => (
              <label key={opcao.valor} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="radio"
                  name={`motivo-${linha.id}`}
                  value={opcao.valor}
                  checked={motivo === opcao.valor}
                  onChange={() => setMotivo(opcao.valor)}
                />
                {opcao.rotulo}
              </label>
            ))}
          </div>
          <textarea
            aria-label="Motivo do Não procede"
            value={texto}
            onChange={(evento) => setTexto(evento.target.value)}
            placeholder={textoObrigatorio ? "Escreva o motivo" : "Conte mais, se quiser"}
            rows={2}
            className="w-full rounded-lg border border-border px-2 py-1.5 text-sm"
          />
          <Ditar
            campo="Motivo do Não procede"
            aoTranscrever={(ditado) => setTexto((atual) => juntarDitado(atual, ditado))}
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              aria-label="Confirmar Não procede"
              onClick={confirmarNaoProcede}
              disabled={!podeConfirmar || ocupado}
              className={`${BOTAO} bg-primary text-white`}
            >
              Confirmar
            </button>
            <button
              type="button"
              onClick={() => setNaoProcedeAberto(false)}
              className={`${BOTAO} border border-border text-slate-700 bg-white`}
            >
              Cancelar
            </button>
          </div>
        </fieldset>
      )}
    </div>
  );
}
