"use client";

import Link from "next/link";
import { Lock } from "lucide-react";

import { Dica } from "@/components/ui/Dica";
import { detalheDaConta, rotuloDaSituacao, type ItemDaFila } from "@/lib/contas-medicas/envio";
import { dataCurta } from "@/lib/contas-medicas/guia";
import { COLUNAS, DICA_DO_PEGAR, dicaDaContaAlheia } from "@/lib/contas-medicas/textos";

import { COR_DO_TOM, tomDaSituacao } from "./situacao";

/**
 * A lista de contas da etapa aberta (issue #1951): uma linha por conta, com o
 * número do atendimento em destaque e o rótulo do paciente ao lado, operadora,
 * período, andamento, com quem está e a ação. A palavra "Atendimento" fica só
 * no cabeçalho da coluna. Da tela média para cima as colunas se alinham; na
 * estreita, cada linha empilha os campos, sem rolagem lateral.
 */

const GRADE = "md:grid md:grid-cols-[minmax(0,1.5fr)_minmax(0,0.8fr)_minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,1fr)_7rem] md:items-center md:gap-4";

export function periodoDaConta(conta: ItemDaFila): string | null {
  return conta.periodo_inicio && conta.periodo_fim
    ? `${dataCurta(conta.periodo_inicio)} a ${dataCurta(conta.periodo_fim)}`
    : null;
}

/** Quantos itens e eventos a análise achou, só na conta pronta (issue #1419). */
function contagensDaConta(conta: ItemDaFila): string | null {
  if (conta.itens_lidos == null || conta.eventos_lidos == null) return null;
  const itens = `${conta.itens_lidos} ${conta.itens_lidos === 1 ? "item" : "itens"}`;
  return `${itens}, ${conta.eventos_lidos} ${conta.eventos_lidos === 1 ? "evento" : "eventos"}`;
}

/** O número em destaque, com algarismos tabulares, e o rótulo do paciente ao lado. */
export function NumeroEPaciente({ conta }: { conta: ItemDaFila }) {
  return (
    <span className="flex min-w-0 flex-wrap items-baseline gap-x-2">
      <span className="text-base font-semibold tabular-nums text-slate-900">{conta.numero_atendimento}</span>
      {conta.paciente_rotulo && <span className="text-sm text-slate-600">{conta.paciente_rotulo}</span>}
    </span>
  );
}

const BOTAO = "inline-flex items-center rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-wide";

/**
 * A ação da linha. A conta livre tem "Pegar": abrir o Guia dela é pegar (ADR
 * 0105, decisão 3). A conta da própria pessoa tem a ação sempre visível. A de
 * outra faturista mostra "Abrir" no hover e no foco do teclado para quem tem
 * o painel completo; para quem não tem, não há ação, só a dica de com quem a
 * conta está (ADR 0105, decisão 2, issue #1955).
 */
function AcaoDaConta({ conta, abreAlheias }: { conta: ItemDaFila; abreAlheias: boolean }) {
  const guia = `/contas-medicas/guia/${conta.id}`;
  if (conta.situacao === "A_FAZER") {
    return (
      <span data-acao="principal">
        <Dica texto={DICA_DO_PEGAR}>
          <Link href={guia} className={`${BOTAO} bg-primary text-white hover:bg-primary/90`}>
            Pegar
          </Link>
        </Dica>
      </span>
    );
  }
  const emAnalise = conta.situacao === "EM_CORRECAO" || conta.situacao === "RETORNO";
  if (!emAnalise && !conta.situacao.startsWith("CONCLUIDA")) return null;
  if (!conta.minha && !abreAlheias) {
    return (
      <span data-acao="nenhuma">
        <Dica texto={dicaDaContaAlheia(conta.com)} abrePara="esquerda">
          <span
            tabIndex={0}
            role="img"
            aria-label="Conta de outra faturista"
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <Lock className="h-4 w-4" aria-hidden="true" />
          </span>
        </Dica>
      </span>
    );
  }
  if (!conta.minha) {
    return (
      <span
        data-acao="secundaria"
        className="md:opacity-0 md:transition-opacity md:group-hover:opacity-100 md:group-focus-within:opacity-100"
      >
        <Link href={guia} className={`${BOTAO} border border-border text-primary hover:bg-slate-50`}>
          Abrir
        </Link>
      </span>
    );
  }
  return (
    <span data-acao="principal">
      <Link
        href={guia}
        className={`${BOTAO} ${emAnalise ? "bg-primary text-white hover:bg-primary/90" : "border border-border text-primary hover:bg-slate-50"}`}
      >
        {emAnalise ? "Continuar" : "Abrir"}
      </Link>
    </span>
  );
}

function LinhaDaConta({ conta, abreAlheias }: { conta: ItemDaFila; abreAlheias: boolean }) {
  // O valor da conta fica fora da lista (issue #1419): a Fila nunca anda por valor.
  const andamento = [detalheDaConta({ ...conta, valor_apontado: null }), contagensDaConta(conta)]
    .filter(Boolean)
    .join(", ");
  const periodo = periodoDaConta(conta);
  return (
    <li className={`group flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 ${GRADE}`}>
      <div className="min-w-0 basis-full md:basis-auto">
        <NumeroEPaciente conta={conta} />
        {conta.numero_conta && <p className="text-xs text-slate-500">conta {conta.numero_conta}</p>}
      </div>
      <span className="min-w-0 text-sm text-slate-700">{conta.operadora ?? ""}</span>
      <span className="min-w-0 text-sm text-slate-700">{periodo ?? ""}</span>
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <span
          data-tom={tomDaSituacao(conta.situacao)}
          className={`etiqueta rounded-full px-2.5 py-0.5 text-xs font-medium ${COR_DO_TOM[tomDaSituacao(conta.situacao)]}`}
        >
          {rotuloDaSituacao(conta)}
        </span>
        {andamento && <span className="text-xs text-slate-600">{andamento}</span>}
      </div>
      <span className="min-w-0 text-sm text-slate-600">{conta.com ? `com ${conta.com}` : ""}</span>
      <div className="md:justify-self-end">
        <AcaoDaConta conta={conta} abreAlheias={abreAlheias} />
      </div>
    </li>
  );
}

/** `abreAlheias`: a pessoa tem o painel completo e abre a conta de qualquer faturista. */
export function ListaDeContas({ contas, abreAlheias }: { contas: ItemDaFila[]; abreAlheias: boolean }) {
  return (
    <div>
      <div
        className={`etiqueta flex border-b border-border px-5 py-2 text-xs font-semibold text-slate-500 ${GRADE}`}
      >
        {COLUNAS.map((coluna, i) => (
          <span key={coluna || "acao"} className={i === 0 ? "" : "hidden md:block"}>
            {coluna}
          </span>
        ))}
      </div>
      <ul className="divide-y divide-border">
        {contas.map((conta) => (
          <LinhaDaConta key={conta.id} conta={conta} abreAlheias={abreAlheias} />
        ))}
      </ul>
    </div>
  );
}
