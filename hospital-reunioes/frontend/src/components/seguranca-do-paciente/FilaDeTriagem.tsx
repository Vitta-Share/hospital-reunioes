"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCheck, Inbox, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import { rotuloDaFaixa, type ItemDaFila, type RespostaDaFila } from "@/lib/seguranca-do-paciente/triagem";
import { formatarData } from "./NotificacoesDoNucleo";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

const COR_DA_FAIXA: Record<string, string> = {
  A: "bg-red-100 text-red-800",
  B: "bg-orange-100 text-orange-800",
  C: "bg-amber-100 text-amber-800",
  D: "bg-sky-100 text-sky-800",
  E: "bg-slate-100 text-slate-700",
};

export function SeloDaFaixa({ faixa }: { faixa: string | null }) {
  if (!faixa) {
    return (
      <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-800">
        Classificar manualmente
      </span>
    );
  }
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-semibold ${COR_DA_FAIXA[faixa] ?? "bg-slate-100 text-slate-700"}`}
    >
      {rotuloDaFaixa(faixa)}
    </span>
  );
}

function diasDesde(iso: string): number {
  const ms = Date.now() - new Date(iso).getTime();
  return Number.isNaN(ms) ? 0 : Math.max(0, Math.floor(ms / 86_400_000));
}

/**
 * A fila de triagem (issue #1992): as notificações sem triagem confirmada, da
 * mais antiga para a mais nova, na ordem do servidor. Sem relato e sem quem
 * notificou: o protocolo, a faixa e o assunto sugeridos, o setor e a data.
 *
 * Com a aprovação em lote ligada (issue #2002), os casos D e E que cabem no
 * lote ganham uma caixa de marcar, e "Confirmar em lote" confirma os marcados
 * de uma vez. Quem confere cada caso de verdade é o servidor.
 */
export function FilaDeTriagem() {
  const [fila, setFila] = useState<ItemDaFila[] | null>(null);
  const [loteLigado, setLoteLigado] = useState(false);
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [erroDoLote, setErroDoLote] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const carregar = useCallback(
    () =>
      chamarNsp<RespostaDaFila>("/api/nsp/triagem").then((corpo) => {
        setFila(corpo.fila);
        setLoteLigado(Boolean(corpo.lote_ligado));
        setMarcados(new Set());
      }),
    []
  );

  useEffect(() => {
    let vivo = true;
    chamarNsp<RespostaDaFila>("/api/nsp/triagem")
      .then((corpo) => {
        if (!vivo) return;
        setFila(corpo.fila);
        setLoteLigado(Boolean(corpo.lote_ligado));
      })
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, []);

  function alternar(id: string) {
    setMarcados((atual) => {
      const novo = new Set(atual);
      if (novo.has(id)) novo.delete(id);
      else novo.add(id);
      return novo;
    });
  }

  async function confirmarEmLote() {
    if (!fila) return;
    const ids = fila.filter((item) => marcados.has(item.id)).map((item) => item.id);
    setEnviando(true);
    setErroDoLote(null);
    setAviso(null);
    try {
      const corpo = await chamarNsp<{ confirmados: { id: string }[] }>("/api/nsp/triagem/lote", {
        method: "POST",
        body: { ids },
      });
      const total = corpo.confirmados.length;
      setAviso(total === 1 ? "1 caso confirmado." : `${total} casos confirmados.`);
      await carregar().catch((e: Error) => setErro(e.message));
    } catch (e) {
      setErroDoLote((e as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  if (erro) {
    return (
      <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
        <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
        <p className="text-sm text-red-700">{erro}</p>
      </div>
    );
  }
  if (fila === null) {
    return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;
  }
  if (fila.length === 0) {
    return (
      <div className={`${CARTAO} flex flex-col items-center text-center gap-2 px-4 py-10`}>
        <Inbox className="w-8 h-8 text-slate-300" aria-hidden />
        <p className="text-sm font-semibold text-slate-900">Nenhuma notificação esperando a triagem.</p>
        {aviso && <p className="text-sm text-emerald-700">{aviso}</p>}
      </div>
    );
  }

  const comLote = loteLigado && fila.some((item) => item.cabe_no_lote);

  return (
    <div className="space-y-3">
      {comLote && (
        <div className={`${CARTAO} flex flex-wrap items-center justify-between gap-3 px-4 py-3`}>
          <p className="text-sm text-slate-700">
            Marque os casos das faixas D e E para confirmar a sugestão de todos de uma vez.
          </p>
          <button
            type="button"
            onClick={confirmarEmLote}
            disabled={marcados.size === 0 || enviando}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-50"
          >
            {enviando ? (
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
            ) : (
              <CheckCheck className="w-4 h-4" aria-hidden />
            )}
            {marcados.size > 0 ? `Confirmar em lote (${marcados.size})` : "Confirmar em lote"}
          </button>
        </div>
      )}
      {erroDoLote && (
        <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-3`}>
          <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
          <p className="text-sm text-red-700">{erroDoLote}</p>
        </div>
      )}
      {aviso && (
        <p role="status" className="text-sm text-emerald-700">
          {aviso}
        </p>
      )}
      <ul className="space-y-3">
        {fila.map((item) => {
          const dias = diasDesde(item.criado_em);
          const marcavel = loteLigado && item.cabe_no_lote;
          return (
            <li key={item.id} className="flex items-stretch gap-2">
              {marcavel && (
                <label className="flex min-w-[44px] items-center justify-center">
                  <input
                    type="checkbox"
                    aria-label={`Marcar ${item.protocolo} para confirmar em lote`}
                    checked={marcados.has(item.id)}
                    onChange={() => alternar(item.id)}
                    className="h-5 w-5 accent-primary"
                  />
                </label>
              )}
              <Link
                href={`/seguranca-do-paciente/notificacoes/${item.id}/triagem`}
                className={`${CARTAO} block flex-1 px-4 py-4 space-y-1.5 hover:border-primary/40`}
              >
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-base font-bold text-slate-900 tabular-nums">{item.protocolo}</span>
                  <SeloDaFaixa faixa={item.faixa} />
                  {item.grave_ou_morte && (
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                      Grave ou houve morte
                    </span>
                  )}
                </span>
                {item.assunto && <span className="block text-sm text-slate-800">{item.assunto}</span>}
                <span className="block text-sm text-slate-500">
                  {`${item.setor ?? "Setor não informado"}`}
                  {item.data_ocorrencia ? `, ${formatarData(item.data_ocorrencia)}` : ""}
                  {`. Recebida há ${dias === 1 ? "1 dia" : `${dias} dias`}.`}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
