/**
 * O cartão da Pergunta da Vitta (issue #2116, PRD #2112, ADR 0109, decisão 3).
 *
 * A pergunta que a Vitta manda pela ponte, em destaque: de qual Projeto é, a
 * pergunta, as quatro linhas em palavras simples (por que precisa da pessoa,
 * o que está parado, o que anda depois e o ganho), o estado e há quantos dias
 * espera. Uma peça só: a Conversa da Demanda a desenha no lugar da bolha, e a
 * lista Esperando sua resposta e o responder no cartão vêm nas próximas
 * partes, sobre ela.
 *
 * O nome é Pergunta da Vitta, nunca Pendência (ADR 0109, decisão 2).
 */

export type EstadoDaPergunta = "aberta" | "respondida" | "resolvida" | "cancelada";

export type PerguntaDaVitta = {
  id: string;
  projeto: string;
  assunto: string;
  texto: string;
  por_que_precisa: string;
  o_que_esta_parado: string;
  o_que_anda_depois: string;
  ganho: string;
  estado: EstadoDaPergunta;
  criado_em: string | null;
  destinatario?: string | null;
};

const NOME_DO_ESTADO: Record<EstadoDaPergunta, string> = {
  aberta: "Aberta",
  respondida: "Respondida",
  resolvida: "Resolvida",
  cancelada: "Cancelada",
};

const UM_DIA = 24 * 60 * 60 * 1000;

/** Os dias inteiros desde que a Pergunta nasceu, como no lembrete de 3 dias. */
function espera(criadoEm: string | null, agora: Date): string | null {
  if (!criadoEm) return null;
  const desde = new Date(criadoEm).getTime();
  if (Number.isNaN(desde)) return null;
  const dias = Math.max(0, Math.floor((agora.getTime() - desde) / UM_DIA));
  if (dias === 0) return "Esperando há menos de 1 dia";
  return dias === 1 ? "Esperando há 1 dia" : `Esperando há ${dias} dias`;
}

export function perguntaValida(item: unknown): item is PerguntaDaVitta {
  if (typeof item !== "object" || item === null) return false;
  const p = item as Record<string, unknown>;
  return typeof p.id === "string" && typeof p.texto === "string" && typeof p.estado === "string";
}

export function CartaoDaPergunta({ pergunta, agora = new Date() }: { pergunta: PerguntaDaVitta; agora?: Date }) {
  const aberta = pergunta.estado === "aberta";
  const tempo = aberta ? espera(pergunta.criado_em, agora) : null;
  const linhas: [string, string][] = [
    ["Por que precisa de você", pergunta.por_que_precisa],
    ["O que está parado", pergunta.o_que_esta_parado],
    ["O que anda quando você responder", pergunta.o_que_anda_depois],
    ["O que o hospital ganha", pergunta.ganho],
  ];
  return (
    <article
      aria-label="Pergunta da Vitta"
      className={`w-full rounded-2xl border-2 px-4 py-3 space-y-3 ${
        aberta ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-bold text-slate-900">Pergunta da Vitta</span>
        <span className="normal-case rounded-full bg-white border border-slate-200 px-2 py-0.5 text-slate-700">
          {pergunta.projeto}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 font-semibold ${
            aberta ? "bg-amber-200 text-amber-900" : "bg-slate-200 text-slate-700"
          }`}
        >
          {NOME_DO_ESTADO[pergunta.estado] ?? pergunta.estado}
        </span>
        {tempo && <span className="normal-case text-text-secondary">{tempo}</span>}
      </div>
      {pergunta.destinatario && (
        <p className="normal-case text-xs text-text-secondary">Para {pergunta.destinatario}</p>
      )}
      <p className="normal-case whitespace-pre-wrap text-sm font-semibold text-slate-900">{pergunta.texto}</p>
      <dl className="grid gap-2 sm:grid-cols-2">
        {linhas.map(([rotulo, valor]) => (
          <div key={rotulo} className="rounded-xl bg-white border border-slate-200 px-3 py-2">
            <dt className="text-xs font-semibold text-slate-700">{rotulo}</dt>
            <dd className="normal-case text-sm text-slate-800">{valor}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}
