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
 *
 * A resposta no cartão (issue #2119, ADR 0109, decisões 4 e 5): as opções
 * prontas, na mesma peça do Planejamento da Demanda, e o campo livre. Só
 * aparecem a quem o servidor diz que responde (`pode_responder`): o
 * Destinatário, ou o Desenvolvedor no lugar dele. A Pergunta respondida
 * mostra a resposta e quem respondeu.
 *
 * O estado final (issue #2121, ADR 0109, decisão 6): a resolvida mostra o que
 * foi decidido e o que destravou; a cancelada, o motivo.
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { BASE_TECNOLOGIA, FALHA_DE_CONEXAO, motivoDaRecusa } from "./demandas";
import { OpcoesEmCartao } from "./OpcoesEmCartao";

export type EstadoDaPergunta = "aberta" | "respondida" | "resolvida" | "cancelada";

export type RespostaDaPergunta = {
  opcao: string | null;
  opcao_texto: string | null;
  texto: string | null;
  respondida_em: string | null;
  respondida_por: string | null;
  em_nome_de: string | null;
};

/** O estado final (issue #2121): a Vitta leu a resposta e resolveu, ou a Pergunta deixou de ser necessária. */
export type ResolucaoDaPergunta = { decidido: string | null; destravou: string | null; resolvida_em: string | null };
export type CancelamentoDaPergunta = { motivo: string | null; cancelada_em: string | null };

/** O que a rota da resposta devolve: o cartão respondido e a mensagem da Conversa. */
export type PerguntaRespondida = {
  pergunta: PerguntaDaVitta;
  mensagem: { id: string; autor: string | null; texto: string; criado_em: string | null; minha: boolean };
};

/** O mesmo teto da rota: a resposta entra na Conversa com o começo na frente. */
const LIMITE_DA_RESPOSTA = 4000;

export function urlDaResposta(perguntaId: string): string {
  return `${BASE_TECNOLOGIA}/perguntas/${encodeURIComponent(perguntaId)}/resposta`;
}

export type PerguntaDaVitta = {
  id: string;
  projeto: string;
  assunto: string;
  texto: string;
  por_que_precisa: string;
  o_que_esta_parado: string;
  o_que_anda_depois: string;
  ganho: string;
  opcoes?: { letra: string; texto: string }[];
  recomendada?: string | null;
  porque?: string | null;
  estado: EstadoDaPergunta;
  criado_em: string | null;
  destinatario?: string | null;
  resposta?: RespostaDaPergunta | null;
  resolucao?: ResolucaoDaPergunta | null;
  cancelamento?: CancelamentoDaPergunta | null;
  pode_responder?: boolean;
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

function respondidaValida(item: unknown): item is PerguntaRespondida {
  if (typeof item !== "object" || item === null) return false;
  const r = item as Record<string, unknown>;
  const mensagem = r.mensagem as Record<string, unknown> | null;
  return perguntaValida(r.pergunta) && typeof mensagem?.id === "string" && typeof mensagem?.texto === "string";
}

/** A resposta gravada: a opção ou o texto, e quem respondeu (os dois nomes no registro do Desenvolvedor). */
function RespostaGravada({ resposta }: { resposta: RespostaDaPergunta }) {
  const quem = resposta.em_nome_de
    ? `Registrada por ${resposta.respondida_por ?? ""} em nome de ${resposta.em_nome_de}`
    : `Respondida por ${resposta.respondida_por ?? ""}`;
  return (
    <div role="group" aria-label="Resposta" className="rounded-xl bg-white border border-slate-200 px-3 py-2 space-y-1">
      <p className="text-xs font-semibold text-slate-700">Resposta</p>
      {resposta.opcao && (
        <p className="normal-case text-sm font-semibold text-slate-900">{`${resposta.opcao}) ${resposta.opcao_texto ?? ""}`}</p>
      )}
      {resposta.texto && <p className="normal-case whitespace-pre-wrap text-sm text-slate-800">{resposta.texto}</p>}
      <p className="normal-case text-xs text-text-secondary">{quem}</p>
    </div>
  );
}

/** O estado final, com a decisão e o que destravou, ou com o motivo (ADR 0109, decisão 6). */
function EstadoFinal({ nome, linhas }: { nome: string; linhas: [string, string | null][] }) {
  return (
    <dl role="group" aria-label={nome} className="rounded-xl bg-white border border-slate-200 px-3 py-2 space-y-1">
      {linhas.map(([rotulo, valor]) => (
        <div key={rotulo}>
          <dt className="text-xs font-semibold text-slate-700">{rotulo}</dt>
          <dd className="normal-case whitespace-pre-wrap text-sm text-slate-800">{valor ?? ""}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CartaoDaPergunta({
  pergunta,
  agora = new Date(),
  token = null,
  onRespondida,
}: {
  pergunta: PerguntaDaVitta;
  agora?: Date;
  /** Sem token, o cartão não responde: só mostra. */
  token?: string | null;
  /** A resposta gravada: quem desenha o cartão troca a Pergunta e põe a mensagem na Conversa. */
  onRespondida?: (respondida: PerguntaRespondida) => void;
}) {
  const [livre, setLivre] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const aberta = pergunta.estado === "aberta";
  const responde = aberta && Boolean(pergunta.pode_responder) && Boolean(token);
  const opcoes = pergunta.opcoes ?? [];

  async function responder(corpo: { opcao: string } | { texto: string }) {
    if (!token || enviando) return;
    setEnviando(true);
    setErro(null);
    try {
      const resposta = await fetch(urlDaResposta(pergunta.id), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      if (!resposta.ok) {
        setErro(await motivoDaRecusa(resposta));
        return;
      }
      const respondida: unknown = await resposta.json();
      if (respondidaValida(respondida)) {
        setLivre("");
        onRespondida?.(respondida);
      }
    } catch (e) {
      console.error("[admin/tecnologia] falha ao responder a Pergunta da Vitta", e);
      setErro(FALHA_DE_CONEXAO);
    } finally {
      setEnviando(false);
    }
  }

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
      {opcoes.length > 0 && (aberta || !pergunta.resposta) && (
        <OpcoesEmCartao
          opcoes={opcoes}
          recomendada={pergunta.recomendada}
          desabilitado={enviando}
          onEscolher={responde ? (letra) => responder({ opcao: letra }) : undefined}
        />
      )}
      {opcoes.length > 0 && pergunta.porque && pergunta.recomendada && (aberta || !pergunta.resposta) && (
        <p className="normal-case text-sm leading-relaxed text-slate-700">{`Por que recomendo a ${pergunta.recomendada}: ${pergunta.porque}`}</p>
      )}
      {responde && (
        <div className="space-y-2">
          <textarea
            aria-label="Sua resposta"
            rows={2}
            maxLength={LIMITE_DA_RESPOSTA}
            placeholder={opcoes.length > 0 ? "Nenhuma opção serve? Escreva aqui." : "Escreva a sua resposta."}
            value={livre}
            onChange={(e) => setLivre(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl outline-none focus:border-primary focus:ring-1 focus:ring-primary bg-white resize-y"
          />
          <button
            type="button"
            onClick={() => responder({ texto: livre.trim() })}
            disabled={!livre.trim() || enviando}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {enviando && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Responder
          </button>
        </div>
      )}
      {erro && (
        <p role="alert" className="normal-case px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          {erro}
        </p>
      )}
      {pergunta.resposta && <RespostaGravada resposta={pergunta.resposta} />}
      {pergunta.estado === "resolvida" && pergunta.resolucao && (
        <EstadoFinal
          nome="Resolvida"
          linhas={[
            ["O que foi decidido", pergunta.resolucao.decidido],
            ["O que destravou", pergunta.resolucao.destravou],
          ]}
        />
      )}
      {pergunta.estado === "cancelada" && pergunta.cancelamento && (
        <EstadoFinal nome="Cancelada" linhas={[["Motivo", pergunta.cancelamento.motivo]]} />
      )}
    </article>
  );
}
