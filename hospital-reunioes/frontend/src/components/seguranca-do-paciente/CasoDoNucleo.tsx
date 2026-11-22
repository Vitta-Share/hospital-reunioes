"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import { CHEGOU_AO_PACIENTE, TURNOS } from "@/lib/seguranca-do-paciente/notificacao";
import type { NotificacaoExterna, PrazoDoCaso } from "@/lib/seguranca-do-paciente/prazos";
import { ESTADOS, formatarData, ORIGENS, QuemNotificou, type Caso } from "./NotificacoesDoNucleo";
import { PrazosDoCaso } from "./PrazosDoCaso";
import { SeloDaOuvidoria } from "./SeloDaOuvidoria";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

interface CasoAberto extends Caso {
  justificativa_tecnica?: string | null;
  /** Os prazos congelados na confirmação da triagem (issue #1993). */
  prazos?: PrazoDoCaso[];
  notificacao_externa?: NotificacaoExterna | null;
}

function Bloco({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{titulo}</h3>
      <div className="text-sm text-slate-800 leading-relaxed">{children}</div>
    </section>
  );
}

/**
 * Um caso do Núcleo aberto (issue #1997). É a tela que o e-mail de ciência
 * da Ouvidoria abre, com login, e abrir o caso que veio dela já marca o
 * Recebido na Ouvidoria: quem marca é o servidor, ao entregar o caso.
 */
export function CasoDoNucleo({ id }: { id: string }) {
  const [caso, setCaso] = useState<CasoAberto | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarNsp<CasoAberto>(`/api/nsp/notificacoes/${encodeURIComponent(id)}`)
      .then((corpo) => vivo && setCaso(corpo))
      .catch((e: Error) => vivo && setErro(e.message));
    return () => {
      vivo = false;
    };
  }, [id]);

  if (erro) {
    return (
      <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
        <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
        <p className="text-sm text-red-700">{erro}</p>
      </div>
    );
  }
  if (caso === null) {
    return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;
  }

  const chegou = CHEGOU_AO_PACIENTE.find((c) => c.valor === caso.chegou_ao_paciente)?.rotulo;
  const turno = TURNOS.find((t) => t.valor === caso.turno)?.rotulo;
  return (
    <article className={`${CARTAO} px-4 py-4 md:px-6 md:py-5 space-y-4`}>
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-bold text-slate-900 tabular-nums">{caso.protocolo}</h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
            {ESTADOS[caso.estado] ?? caso.estado}
          </span>
          {caso.origem === "ouvidoria" ? (
            <SeloDaOuvidoria estado={caso.ouvidoria?.estado ?? null} />
          ) : (
            <span className="text-xs text-slate-500">{ORIGENS[caso.origem] ?? caso.origem}</span>
          )}
          {caso.grave_ou_morte && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
              Grave ou houve morte
            </span>
          )}
        </div>
        <p className="text-sm text-slate-600">
          <span>{caso.setor ?? "Setor não informado"}</span>
          {`, ${formatarData(caso.data_ocorrencia)}`}
          {turno ? `, ${turno.toLowerCase()}` : ""}
          {chegou ? `. ${chegou}.` : "."}
        </p>
        <QuemNotificou caso={caso} />
      </header>

      <PrazosDoCaso prazos={caso.prazos ?? []} notificacaoExterna={caso.notificacao_externa ?? null} />

      <Bloco titulo="O que aconteceu">
        <p className="whitespace-pre-wrap break-words">{caso.relato}</p>
      </Bloco>

      {caso.justificativa_tecnica && (
        <Bloco titulo="O que a Ouvidoria apurou">
          <p className="whitespace-pre-wrap break-words">{caso.justificativa_tecnica}</p>
        </Bloco>
      )}
    </article>
  );
}
