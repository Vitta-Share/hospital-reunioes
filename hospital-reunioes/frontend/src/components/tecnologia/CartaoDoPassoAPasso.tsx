/**
 * O cartão do Passo a passo da Vitta (issue #2176, ADR 0110, decisões 4 a 8).
 *
 * O Pedido da Vitta de fazer alguma coisa: os passos escritos para quem os
 * faz, cada um com um check, e o "Como saber que acabou" como o último. O
 * botão Concluir só libera com todos marcados. A anotação é opcional e fica
 * só no app. Concluído, o app comenta e fecha o card no GitHub; se o GitHub
 * recusa, o cartão mostra "Não chegou ao GitHub" com o motivo e o Reenviar.
 *
 * Marca e conclui quem o servidor diz (`pode_responder`): o Destinatário, ou
 * um Desenvolvedor no lugar dele. Cada check mostra quem marcou.
 *
 * O Pedido de implantação (issue #2207, ADR 0111) usa este cartão com o nome
 * dele: o card fechou quando o Pedido nasceu, e o "Não chegou ao GitHub" com
 * o Reenviar pode aparecer já no cartão aberto. O Pedido que espera outro
 * (issue #2208) mostra "Espera" com o assunto do outro, e o Concluir fica
 * bloqueado com o motivo até o servidor mandar o cartão sem a espera. O
 * cartão que conclui avisa os outros da tela (`PEDIDO_CONCLUIDO`): o que
 * espera por ele solta a espera na hora, sem recarregar.
 *
 * O Pedido de implantação aberto tem o "Achei um problema" (issue #2210, ADR
 * 0111, decisão 9): o cartão pede o bug ao Assistente com o Pedido, e o texto
 * inicial o servidor monta; a conversa que nasceu abre pela tela
 * (`ABRIR_DEMANDA`). Com o card do bug criado, o cartão mostra "Espera a
 * Demanda N" e o Concluir fica bloqueado até ela ser entregue.
 */

import { useEffect, useState } from "react";
import { ListChecks, Loader2 } from "lucide-react";

import { BASE_TECNOLOGIA, FALHA_DE_CONEXAO, motivoDaRecusa } from "./demandas";
import { MeExplique } from "./MeExplique";
import { espera, perguntaValida, type PerguntaDaVitta } from "./CartaoDaPergunta";

/** O que a rota do Concluir devolve: o cartão concluído e, se houve anotação, a mensagem dela na Conversa. */
export type PassoAPassoConcluido = {
  pergunta: PerguntaDaVitta;
  mensagem: { id: string; autor: string | null; texto: string; criado_em: string | null; minha: boolean } | null;
};

/** O evento da janela com o id do Pedido que acabou de ser concluído nesta tela. */
export const PEDIDO_CONCLUIDO = "tecnologia:pedido-concluido";

/** O evento da janela com o id da Demanda de bug que o Achei um problema fez nascer. */
export const ABRIR_DEMANDA = "tecnologia:abrir-demanda";

/** O mesmo teto da rota: a anotação entra na Conversa com o começo na frente. */
const LIMITE_DA_ANOTACAO = 4000;

function urlDo(pedidoId: string, acao: "checks" | "concluir" | "reenviar"): string {
  return `${BASE_TECNOLOGIA}/perguntas/${encodeURIComponent(pedidoId)}/${acao}`;
}

const NOME_DO_ESTADO: Record<string, string> = {
  aberta: "Aberto",
  concluida: "Concluído",
  cancelada: "Cancelado",
};

function quando(instante: string | null | undefined): string {
  if (!instante) return "";
  const data = new Date(instante);
  if (Number.isNaN(data.getTime())) return "";
  return data.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function CartaoDoPassoAPasso({
  pedido,
  agora = new Date(),
  token = null,
  onConcluido,
}: {
  pedido: PerguntaDaVitta;
  agora?: Date;
  /** Sem token, o cartão só mostra. */
  token?: string | null;
  /** O Passo a passo concluído: quem desenha o cartão troca o Pedido e põe a anotação na Conversa. */
  onConcluido?: (concluido: PassoAPassoConcluido) => void;
}) {
  const [atual, setAtual] = useState<PerguntaDaVitta>(pedido);
  const [anotacao, setAnotacao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => setAtual(pedido), [pedido]);

  // O esperado concluído em outro cartão da tela solta a espera deste, sem
  // mexer nos checks já marcados aqui.
  useEffect(() => {
    function soltar(evento: Event) {
      const id = (evento as CustomEvent<string>).detail;
      setAtual((a) => (a.espera?.pedido_id === id ? { ...a, espera: null } : a));
    }
    window.addEventListener(PEDIDO_CONCLUIDO, soltar);
    return () => window.removeEventListener(PEDIDO_CONCLUIDO, soltar);
  }, []);

  const aberta = atual.estado === "aberta";
  const faz = aberta && Boolean(atual.pode_responder) && Boolean(token);
  const passos = atual.passos ?? [];
  const todosMarcados = passos.length > 0 && passos.every((p) => p.marcado);
  const esperado = aberta ? atual.espera : null;
  const bug = aberta ? atual.espera_demanda : null;
  const acheiUmProblema = aberta && atual.tipo === "implantacao" && Boolean(token);

  async function pedir(url: string, corpo?: unknown): Promise<unknown> {
    if (!token || enviando) return null;
    setEnviando(true);
    setErro(null);
    try {
      const resposta = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: corpo === undefined ? undefined : JSON.stringify(corpo),
      });
      if (!resposta.ok) {
        setErro(await motivoDaRecusa(resposta));
        return null;
      }
      return await resposta.json();
    } catch (e) {
      console.error("[admin/tecnologia] falha no Passo a passo da Vitta", e);
      setErro(FALHA_DE_CONEXAO);
      return null;
    } finally {
      setEnviando(false);
    }
  }

  async function marcar(indice: number, marcado: boolean) {
    const cartao = await pedir(urlDo(atual.id, "checks"), { passo: indice, marcado });
    if (perguntaValida(cartao)) setAtual(cartao);
  }

  async function concluir() {
    const corpo = await pedir(urlDo(atual.id, "concluir"), { anotacao: anotacao.trim() || null });
    const concluido = corpo as PassoAPassoConcluido | null;
    if (concluido && perguntaValida(concluido.pergunta)) {
      setAtual(concluido.pergunta);
      setAnotacao("");
      if (concluido.pergunta.estado === "concluida") {
        window.dispatchEvent(new CustomEvent(PEDIDO_CONCLUIDO, { detail: concluido.pergunta.id }));
      }
      onConcluido?.(concluido);
    }
  }

  async function acheiOProblema() {
    const corpo = await pedir(`${BASE_TECNOLOGIA}/chat`, { escolha: "bug", pedido_id: atual.id });
    const demandaId = (corpo as { demanda_id?: unknown } | null)?.demanda_id;
    if (typeof demandaId === "string") window.dispatchEvent(new CustomEvent(ABRIR_DEMANDA, { detail: demandaId }));
  }

  async function reenviar() {
    const cartao = await pedir(urlDo(atual.id, "reenviar"));
    if (perguntaValida(cartao)) setAtual(cartao);
  }

  const tempo = aberta ? espera(atual.criado_em, agora) : null;
  const linhas: [string, string][] = [
    ["Por que precisa de você", atual.por_que_precisa],
    ["O que está parado", atual.o_que_esta_parado],
    ["O que anda quando você concluir", atual.o_que_anda_depois],
    ["O que o hospital ganha", atual.ganho],
  ];
  const conclusao = atual.conclusao;
  const fechamento = atual.fechamento;
  const nome = atual.tipo === "implantacao" ? "Pedido de implantação" : "Passo a passo da Vitta";
  const nomeDoIcone = atual.tipo === "implantacao" ? "Pedido de implantação" : "Passo a passo";

  return (
    <article
      aria-label={nome}
      className={`w-full rounded-2xl border-2 px-4 py-3 space-y-3 ${
        aberta ? "border-sky-300 bg-sky-50" : "border-slate-200 bg-slate-50"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <ListChecks role="img" aria-label={nomeDoIcone} className="w-4 h-4 text-sky-700" />
        <span className="font-bold text-slate-900">{nome}</span>
        <span className="normal-case rounded-full bg-white border border-slate-200 px-2 py-0.5 text-slate-700">
          {atual.projeto}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 font-semibold ${
            aberta ? "bg-sky-200 text-sky-900" : "bg-slate-200 text-slate-700"
          }`}
        >
          {NOME_DO_ESTADO[atual.estado] ?? atual.estado}
        </span>
        {tempo && <span className="normal-case text-text-secondary">{tempo}</span>}
      </div>
      {atual.destinatario && <p className="normal-case text-xs text-text-secondary">Para {atual.destinatario}</p>}
      {esperado && (
        <p className="normal-case text-xs font-semibold text-amber-800">{`Espera: ${esperado.assunto}`}</p>
      )}
      {bug && <p className="normal-case text-xs font-semibold text-amber-800">{`Espera a Demanda ${bug.numero ?? ""}`}</p>}
      <p className="normal-case whitespace-pre-wrap text-sm font-semibold text-slate-900">{atual.texto}</p>
      <dl className="grid gap-2 sm:grid-cols-2">
        {linhas.map(([rotulo, valor]) => (
          <div key={rotulo} className="rounded-xl bg-white border border-slate-200 px-3 py-2">
            <dt className="text-xs font-semibold text-slate-700">{rotulo}</dt>
            <dd className="normal-case text-sm text-slate-800">{valor}</dd>
          </div>
        ))}
      </dl>
      <ol aria-label="Passos" className="space-y-2">
        {passos.map((passo, indice) => (
          <li key={indice} className="flex items-start gap-2 rounded-xl bg-white border border-slate-200 px-3 py-2">
            <input
              type="checkbox"
              aria-label={passo.texto}
              checked={passo.marcado}
              disabled={!faz || enviando}
              onChange={(e) => marcar(indice, e.target.checked)}
              className="mt-1 h-4 w-4 accent-primary"
            />
            <div className="min-w-0">
              <p className="normal-case whitespace-pre-wrap break-words text-sm text-slate-800">{passo.texto}</p>
              {passo.marcado && passo.por && (
                <p className="normal-case text-xs text-text-secondary">
                  {passo.em_nome_de
                    ? `Marcado por ${passo.por} em nome de ${passo.em_nome_de}, ${quando(passo.em)}`
                    : `Marcado por ${passo.por}, ${quando(passo.em)}`}
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>
      {faz && token && (
        <div className="space-y-2">
          <MeExplique perguntaId={atual.id} token={token} onUsarRascunho={setAnotacao} />
          <textarea
            aria-label="Sua anotação (opcional)"
            rows={2}
            maxLength={LIMITE_DA_ANOTACAO}
            placeholder="Quer deixar algo registrado para a Vitta? Escreva aqui. Fica só no aplicativo."
            value={anotacao}
            onChange={(e) => setAnotacao(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl outline-none focus:border-primary focus:ring-1 focus:ring-primary bg-white resize-y"
          />
          <button
            type="button"
            onClick={concluir}
            disabled={!todosMarcados || Boolean(esperado) || Boolean(bug) || enviando}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {enviando && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Concluir
          </button>
          {esperado ? (
            <p className="normal-case text-xs text-text-secondary">{`Este Pedido espera "${esperado.assunto}" ser concluído.`}</p>
          ) : bug ? (
            <p className="normal-case text-xs text-text-secondary">{`Este Pedido espera a Demanda ${bug.numero ?? ""} ser entregue.`}</p>
          ) : (
            !todosMarcados && (
              <p className="normal-case text-xs text-text-secondary">Marque todos os passos para concluir.</p>
            )
          )}
        </div>
      )}
      {acheiUmProblema && (
        <button
          type="button"
          onClick={acheiOProblema}
          disabled={enviando}
          className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-sm font-semibold text-slate-800 hover:border-primary disabled:opacity-40"
        >
          Achei um problema
        </button>
      )}
      {conclusao && (
        <div role="group" aria-label="Concluído" className="rounded-xl bg-white border border-slate-200 px-3 py-2 space-y-1">
          <p className="normal-case text-sm text-slate-800">
            {conclusao.como === "github"
              ? `Concluído pelo GitHub, ${quando(conclusao.concluida_em)}`
              : conclusao.em_nome_de
                ? `Concluído por ${conclusao.por ?? ""} em nome de ${conclusao.em_nome_de}, ${quando(conclusao.concluida_em)}`
                : `Concluído por ${conclusao.por ?? ""}, ${quando(conclusao.concluida_em)}`}
          </p>
          {conclusao.anotacao && (
            <p className="normal-case whitespace-pre-wrap text-sm text-slate-700">{`Anotação: ${conclusao.anotacao}`}</p>
          )}
        </div>
      )}
      {fechamento?.estado === "falhou" && (
        <div role="alert" className="normal-case space-y-2 px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          <p className="font-semibold">Não chegou ao GitHub</p>
          {fechamento.motivo && <p>{fechamento.motivo}</p>}
          {atual.pode_reenviar && token && (
            <button
              type="button"
              onClick={reenviar}
              disabled={enviando}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-700 text-white text-sm font-semibold disabled:opacity-40"
            >
              {enviando && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Reenviar
            </button>
          )}
        </div>
      )}
      {fechamento?.estado === "fechado" && (
        <p className="normal-case text-xs text-text-secondary">O card foi fechado no GitHub.</p>
      )}
      {erro && (
        <p role="alert" className="normal-case px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          {erro}
        </p>
      )}
    </article>
  );
}
