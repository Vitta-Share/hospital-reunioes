import { formatarDataHora, type NotificacaoExterna, type PrazoDoCaso } from "@/lib/seguranca-do-paciente/prazos";

interface Props {
  prazos: PrazoDoCaso[];
  notificacaoExterna: NotificacaoExterna | null;
}

/**
 * Os prazos do caso, congelados na confirmação da triagem (issue #1993). Cada
 * um com data e hora absolutas, nunca "em 3 dias". O prazo legal vem da norma
 * e não muda; o interno vem da tabela do dia da confirmação.
 */
export function PrazosDoCaso({ prazos, notificacaoExterna }: Props) {
  if (prazos.length === 0 && !notificacaoExterna) return null;
  return (
    <section className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Prazos</h3>
      {notificacaoExterna && (
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">
          {`Notificar no ${notificacaoExterna.rotulo} até ${formatarDataHora(notificacaoExterna.prazo_legal)}.`}
        </p>
      )}
      <ul className="divide-y divide-border rounded-xl border border-border">
        {prazos.map((prazo) => (
          <li key={prazo.marco} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
            <span className="min-w-0 flex-1 text-slate-800">{prazo.rotulo}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                prazo.tipo === "legal" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700"
              }`}
            >
              {prazo.tipo === "legal" ? "Legal" : "Interno"}
            </span>
            <span className="font-semibold tabular-nums text-slate-900">{formatarDataHora(prazo.vence_em)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
