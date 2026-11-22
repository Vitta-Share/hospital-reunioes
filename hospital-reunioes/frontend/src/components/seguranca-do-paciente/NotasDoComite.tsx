"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

interface NotaDoComite {
  id: string;
  texto: string;
  enviada_em: string | null;
}

/** "2026-11-21T13:00:00+00:00" vira "21/11/2026", no fuso do hospital. */
function dataBr(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo" }).format(new Date(iso));
}

/**
 * A lista "Notas do Comitê de Conduta" (issue #1850): as notas que o Comitê
 * mandou ao Núcleo sobre risco ao paciente, da mais nova à mais antiga. Cada
 * uma traz só o texto e a data do envio: sem protocolo, sem relato e sem quem
 * relatou.
 */
export function NotasDoComite() {
  const [notas, setNotas] = useState<NotaDoComite[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let vivo = true;
    chamarNsp<{ notas: NotaDoComite[] }>("/api/nsp/notas-do-comite")
      .then((corpo) => vivo && setNotas(corpo.notas))
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
  if (notas === null) return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;
  if (notas.length === 0) {
    return (
      <p className={`${CARTAO} px-4 py-6 text-sm text-slate-600 text-center`}>
        O Comitê de Conduta ainda não mandou nenhuma nota.
      </p>
    );
  }

  return (
    <ul aria-label="Notas do Comitê de Conduta" className="space-y-3">
      {notas.map((nota) => (
        <li key={nota.id} className={`${CARTAO} px-4 py-4 space-y-1`}>
          {nota.enviada_em && <p className="text-xs text-slate-500">{`Enviada em ${dataBr(nota.enviada_em)}`}</p>}
          <p className="text-sm text-slate-800 whitespace-pre-line break-words">{nota.texto}</p>
        </li>
      ))}
    </ul>
  );
}
