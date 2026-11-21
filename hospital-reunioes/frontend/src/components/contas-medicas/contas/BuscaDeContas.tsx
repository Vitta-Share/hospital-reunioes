"use client";

import Link from "next/link";
import { AlertCircle, Loader2, Search, X } from "lucide-react";

import {
  DICA_DA_BUSCA,
  DIGITE_MAIS,
  ERRO_DA_BUSCA,
  MINIMO_DA_BUSCA,
  NOME_DA_BUSCA,
  REFINE_A_BUSCA,
  SEM_RESULTADO,
  type ItemDaBusca,
  type RespostaDaBusca,
} from "@/lib/contas-medicas/busca";
import { tituloDaCompetencia } from "@/lib/contas-medicas/arquivo";
import { rotuloDaSituacao } from "@/lib/contas-medicas/envio";
import { NOME_DA_ETAPA } from "@/lib/contas-medicas/textos";

import { ListaDeContas, Marcado, periodoDaConta } from "./ListaDeContas";

/**
 * A busca da tela de contas (issue #1956, ADR 0105, decisão 4): o campo da
 * barra do topo e os resultados, que ocupam o lugar da Esteira e da lista
 * enquanto há texto no campo. Quem procura é o servidor, em todas as etapas;
 * a tela marca o trecho digitado e, com um resultado só, mostra a conta em
 * destaque com o botão que cabe à pessoa.
 */

export function CampoDaBusca({ texto, onMudar }: { texto: string; onMudar: (texto: string) => void }) {
  return (
    <div className="relative w-full sm:w-80">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
      <input
        type="search"
        aria-label={NOME_DA_BUSCA}
        placeholder={DICA_DA_BUSCA}
        value={texto}
        onChange={(e) => onMudar(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onMudar("");
        }}
        className="w-full rounded-lg border border-border bg-white py-2 pl-9 pr-9 text-sm text-slate-900 placeholder:text-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
      />
      {texto && (
        <button
          type="button"
          aria-label="Limpar a busca"
          onClick={() => onMudar("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:text-slate-600"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

const BOTAO = "inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold uppercase tracking-wide";

/** O botão da conta em destaque: Pegar a livre, Continuar a sua em análise, Abrir a que pode abrir. */
function BotaoDoDestaque({ conta }: { conta: ItemDaBusca }) {
  if (!conta.pode_abrir) return null;
  const guia = `/contas-medicas/guia/${conta.id}`;
  const rotulo =
    conta.situacao === "A_FAZER"
      ? "Pegar"
      : conta.minha && conta.etapa_da_esteira === "em_analise"
        ? "Continuar"
        : "Abrir";
  const principal = rotulo !== "Abrir";
  return (
    <Link
      href={guia}
      className={`${BOTAO} ${principal ? "bg-primary text-white hover:bg-primary/90" : "border border-border text-primary hover:bg-slate-50"}`}
    >
      {rotulo}
    </Link>
  );
}

function ContaEmDestaque({ conta, marcar }: { conta: ItemDaBusca; marcar: string }) {
  const periodo = periodoDaConta(conta);
  const comQuem = conta.minha ? "Com você" : (conta.com ?? (conta.situacao === "A_FAZER" ? "Ninguém pegou ainda" : null));
  return (
    <article aria-label="Conta encontrada" className="flex flex-wrap items-center justify-between gap-4 p-6">
      <div className="min-w-0 space-y-1">
        <p className="text-4xl font-bold tabular-nums text-slate-900">
          <Marcado texto={conta.numero_atendimento ?? ""} marcar={marcar} />
        </p>
        {conta.paciente_rotulo && (
          <p className="text-lg text-slate-700">
            <Marcado texto={conta.paciente_rotulo} marcar={marcar} />
          </p>
        )}
        <p className="text-sm text-slate-600">
          {[conta.operadora, periodo].filter(Boolean).join(", ")}
        </p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 pt-2 text-sm">
          <dt className="text-slate-500">Onde está</dt>
          <dd className="text-slate-800">
            {NOME_DA_ETAPA[conta.etapa_da_esteira]}, {rotuloDaSituacao(conta).toLowerCase()}
          </dd>
          {comQuem && (
            <>
              <dt className="text-slate-500">Com quem</dt>
              <dd className="text-slate-800">{comQuem}</dd>
            </>
          )}
          {conta.arquivada_em && (
            <>
              <dt className="text-slate-500">Competência</dt>
              <dd className="text-slate-800">{tituloDaCompetencia(conta.competencia)}</dd>
            </>
          )}
        </dl>
      </div>
      <BotaoDoDestaque conta={conta} />
    </article>
  );
}

/**
 * O que aparece no lugar da Esteira e da lista: o pedido de mais um
 * caractere, a busca em curso, o erro, nenhum resultado, a conta em destaque
 * ou a lista dos resultados.
 */
export function ResultadosDaBusca({
  texto,
  resposta,
  erro,
}: {
  texto: string;
  resposta: RespostaDaBusca | null;
  erro: boolean;
}) {
  const termo = texto.trim();
  let conteudo;
  if (termo.length < MINIMO_DA_BUSCA) {
    conteudo = <p className="p-6 text-sm text-slate-500">{DIGITE_MAIS}</p>;
  } else if (erro) {
    conteudo = (
      <p role="alert" className="flex items-center gap-2 p-6 text-sm text-red-700">
        <AlertCircle className="h-4 w-4" aria-hidden="true" /> {ERRO_DA_BUSCA}
      </p>
    );
  } else if (!resposta) {
    conteudo = (
      <p className="flex items-center gap-2 p-6 text-sm text-slate-500">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Buscando
      </p>
    );
  } else if (resposta.contas.length === 0) {
    conteudo = <p className="p-10 text-center text-sm text-slate-500">{SEM_RESULTADO}</p>;
  } else if (resposta.contas.length === 1) {
    conteudo = <ContaEmDestaque conta={resposta.contas[0]} marcar={termo} />;
  } else {
    conteudo = (
      <>
        {/* Na busca quem decide abrir é o `pode_abrir` de cada conta, que o servidor já calculou. */}
        <ListaDeContas contas={resposta.contas} abreAlheias marcar={termo} />
        {resposta.mais && <p className="border-t border-border px-5 py-3 text-xs text-slate-600">{REFINE_A_BUSCA}</p>}
      </>
    );
  }
  return (
    <section aria-label="Resultados da busca" className="rounded-2xl border border-border bg-white shadow-premium">
      {conteudo}
    </section>
  );
}
