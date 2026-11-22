"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertCircle, Inbox, Loader2 } from "lucide-react";

import { OQueFazerAgora } from "@/components/conduta/OQueFazerAgora";
import { ContagemDaRotaEspecialNaLista } from "@/components/conduta/RotaEspecial";
import {
  RITOS,
  SITUACOES,
  chamarComite,
  rotuloDaEtapa,
  rotuloDoRito,
  textoDoPrazo,
  type CasoDaLista,
} from "@/lib/conduta/comite";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAIXA_DOS_CASOS = {
  frase: "Filtre por situação e rito e abra o caso pelo protocolo.",
  botao: "VER O QUE DEPENDE DE MIM",
  como_fazer: [
    "Escolha a situação e o rito",
    "Abra o caso pelo protocolo",
    "Prazo vencido fica marcado na lista",
  ],
  acao: "minha_vez",
  bloqueio: null,
};
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";

/**
 * Casos (issue #1824; especificação, seção 5.2): todos os casos a que a
 * pessoa tem acesso, com filtro por situação e rito. Sem nome e sem trecho de
 * relato: a lista mostra protocolo, rito, etapa e prazo.
 */
export function CasosDoComite() {
  const [situacao, setSituacao] = useState("");
  const [rito, setRito] = useState("");
  const [casos, setCasos] = useState<CasoDaLista[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    const consulta = new URLSearchParams();
    if (situacao) consulta.set("situacao", situacao);
    if (rito) consulta.set("rito", rito);
    const sufixo = consulta.toString() ? `?${consulta}` : "";
    setCasos(null);
    chamarComite<{ casos: CasoDaLista[] }>(`/casos${sufixo}`)
      .then((corpo) => vivo && setCasos(corpo.casos))
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, [situacao, rito]);

  return (
    <div className="space-y-4">
      <OQueFazerAgora caixa={CAIXA_DOS_CASOS} href="/comite-de-conduta" />
      <ContagemDaRotaEspecialNaLista />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label className="text-sm font-semibold text-slate-700 space-y-1">
          <span>Situação</span>
          <select className={CAMPO} value={situacao} onChange={(e) => setSituacao(e.target.value)}>
            <option value="">Todas</option>
            {SITUACOES.map((s) => (
              <option key={s.valor} value={s.valor}>
                {s.rotulo}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700 space-y-1">
          <span>Rito</span>
          <select className={CAMPO} value={rito} onChange={(e) => setRito(e.target.value)}>
            <option value="">Todos</option>
            {RITOS.map((r) => (
              <option key={r.valor} value={r.valor}>
                {r.rotulo}
              </option>
            ))}
            <option value="sem_rito">Sem rito ainda</option>
          </select>
        </label>
      </div>

      {erro ? (
        <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
          <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
          <p className="text-sm text-red-700">{erro}</p>
        </div>
      ) : casos === null ? (
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />
      ) : casos.length === 0 ? (
        <div className={`${CARTAO} flex flex-col items-center text-center gap-2 px-4 py-10`}>
          <Inbox className="w-8 h-8 text-slate-300" aria-hidden />
          <p className="text-sm font-semibold text-slate-900">Nenhum caso com esse filtro.</p>
        </div>
      ) : (
        <ul aria-label="Casos" className="space-y-3">
          {casos.map((caso) => (
            <li key={caso.id}>
              <Link
                href={`/comite-de-conduta/casos/${caso.id}`}
                className={`${CARTAO} flex flex-col gap-1 px-4 py-3 hover:border-[#282760]`}
              >
                <span className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-base font-bold text-slate-900 tabular-nums">{caso.protocolo}</span>
                  <span className={`text-sm font-semibold ${caso.prazo_vencido ? "text-red-700" : "text-slate-700"}`}>
                    {textoDoPrazo(caso.faltam_dias, caso.situacao === "encerrado")}
                  </span>
                </span>
                <span className="text-sm text-slate-600">
                  {`${rotuloDoRito(caso.rito)}, ${rotuloDaEtapa(caso.etapa).toLowerCase()}`}
                </span>
                {caso.prazo_vencido && (
                  <span className="text-xs font-semibold text-red-700">Prazo vencido registrado</span>
                )}
                {caso.origem === "ouvidoria" && (
                  <span className="text-xs font-semibold text-slate-600">Origem: Ouvidoria</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
