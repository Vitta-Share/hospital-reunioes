"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Inbox, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import { CHEGOU_AO_PACIENTE, TURNOS } from "@/lib/seguranca-do-paciente/notificacao";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

interface Caso {
  id: string;
  protocolo: string;
  estado: string;
  origem: string;
  relato: string;
  leito_ou_atendimento: string | null;
  setor: string | null;
  data_ocorrencia: string;
  turno: string | null;
  chegou_ao_paciente: string | null;
  grave_ou_morte: boolean | null;
  criado_em: string;
  /** Só para a Presidência e o Acesso pleno: o servidor decide. */
  anonimo?: boolean;
  notificante?: { nome: string | null; contato: string | null } | null;
}

const ESTADOS: Record<string, string> = {
  recebida: "Recebida",
  em_triagem: "Em triagem",
  classificada: "Classificada",
  encaminhada: "Encaminhada",
  fora_de_escopo: "Fora de escopo",
  em_analise_agregada: "Em análise agregada",
};

const ORIGENS: Record<string, string> = {
  qr: "Pelo QR",
  endereco: "Pelo endereço",
  modulo: "Pelo módulo",
  ouvidoria: "Da Ouvidoria",
  busca_ativa: "Busca ativa",
  ronda: "Ronda",
  reuniao_rapida: "Reunião rápida",
  auditoria: "Auditoria",
  outra: "Outra",
};

function formatarData(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" });
}

function QuemNotificou({ caso }: { caso: Caso }) {
  if (caso.notificante === undefined) return null;
  if (caso.anonimo || !caso.notificante) {
    return <p className="text-sm text-slate-500">Notificado sem identificação</p>;
  }
  const { nome, contato } = caso.notificante;
  return (
    <p className="text-sm text-slate-500">
      {`Notificado por ${nome ?? "pessoa sem nome"}${contato ? ` (${contato})` : ""}`}
    </p>
  );
}

/**
 * Notificações (issue #1987): todos os casos do Núcleo, do mais novo ao mais
 * velho, para quem tem o recurso de casos. Quem notificou aparece só quando o
 * servidor manda, para a Presidência e o Acesso pleno.
 */
export function NotificacoesDoNucleo() {
  const [casos, setCasos] = useState<Caso[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarNsp<{ notificacoes: Caso[] }>("/api/nsp/notificacoes")
      .then((corpo) => vivo && setCasos(corpo.notificacoes))
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
  if (casos === null) {
    return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;
  }
  if (casos.length === 0) {
    return (
      <div className={`${CARTAO} flex flex-col items-center text-center gap-2 px-4 py-10`}>
        <Inbox className="w-8 h-8 text-slate-300" aria-hidden />
        <p className="text-sm font-semibold text-slate-900">Nenhuma notificação ainda.</p>
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {casos.map((caso) => {
        const idDoTitulo = `caso-${caso.id}`;
        const chegou = CHEGOU_AO_PACIENTE.find((c) => c.valor === caso.chegou_ao_paciente)?.rotulo;
        const turno = TURNOS.find((t) => t.valor === caso.turno)?.rotulo;
        return (
          <li key={caso.id}>
            <article aria-labelledby={idDoTitulo} className={`${CARTAO} px-4 py-4 space-y-2`}>
              <div className="flex flex-wrap items-center gap-2">
                <h2 id={idDoTitulo} className="text-base font-bold text-slate-900 tabular-nums">
                  {caso.protocolo}
                </h2>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                  {ESTADOS[caso.estado] ?? caso.estado}
                </span>
                <span className="text-xs text-slate-500">{ORIGENS[caso.origem] ?? caso.origem}</span>
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
              <p className="text-sm text-slate-800 whitespace-pre-line line-clamp-4">{caso.relato}</p>
              <QuemNotificou caso={caso} />
            </article>
          </li>
        );
      })}
    </ul>
  );
}
