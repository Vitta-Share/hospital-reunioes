"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { OQueFazerAgora } from "@/components/conduta/OQueFazerAgora";
import { chamarComite, rotuloDaEtapa, textoDoPrazo, type Caixa, type ItemDaMinhaVez } from "@/lib/conduta/comite";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

function caixaDaMinhaVez(vazia: boolean): Caixa {
  return {
    frase: "Comece pelo caso do topo: é o que vence antes.",
    botao: "ABRIR O MAIS URGENTE",
    como_fazer: [
      "A lista segue o prazo que vence antes",
      "Cada linha diz o que falta você fazer",
      "Feito o passo, o caso sai da sua lista",
    ],
    acao: "abrir",
    bloqueio: vazia ? "Não há caso esperando por você." : null,
  };
}

/**
 * MINHA VEZ (issue #1824; especificação, seção 5.1): só o que depende da
 * pessoa, do mais urgente ao menos urgente. Cada linha tem protocolo, etapa,
 * ação pendente e prazo, sem nome e sem trecho de relato. A ordem vem do
 * servidor.
 */
export function MinhaVez() {
  const [itens, setItens] = useState<ItemDaMinhaVez[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarComite<{ itens: ItemDaMinhaVez[] }>("/minha-vez")
      .then((corpo) => vivo && setItens(corpo.itens))
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  if (erro) {
    return (
      <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
        <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
        <p className="text-sm text-red-700">{erro}</p>
      </div>
    );
  }
  if (itens === null) return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;
  if (itens.length === 0) {
    return (
      <>
        <OQueFazerAgora caixa={caixaDaMinhaVez(true)} />
        <div className={`${CARTAO} flex flex-col items-center text-center gap-2 px-4 py-10`}>
          <CheckCircle2 className="w-8 h-8 text-slate-300" aria-hidden />
          <p className="text-sm font-semibold text-slate-900">Nada depende de você agora.</p>
        </div>
      </>
    );
  }

  return (
    <>
    <OQueFazerAgora caixa={caixaDaMinhaVez(false)} href={`/comite-de-conduta/casos/${itens[0].id}`} />
    <ol aria-label="O que depende de você" className="space-y-3">
      {itens.map((item) => (
        <li key={item.id}>
          <Link
            href={`/comite-de-conduta/casos/${item.id}`}
            className={`${CARTAO} flex flex-col gap-1 px-4 py-3 hover:border-[#282760]`}
          >
            <span className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-base font-bold text-slate-900 tabular-nums">{item.protocolo}</span>
              <span className={`text-sm font-semibold ${item.prazo_vencido ? "text-red-700" : "text-slate-700"}`}>
                {textoDoPrazo(item.faltam_dias)}
              </span>
            </span>
            <span className="text-sm text-slate-600">{rotuloDaEtapa(item.etapa)}</span>
            <span className="text-sm font-semibold text-[#282760]">{item.acao}</span>
          </Link>
        </li>
      ))}
    </ol>
    </>
  );
}
