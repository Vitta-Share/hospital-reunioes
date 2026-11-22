/**
 * O Me explique do cartão da Pergunta da Vitta (issue #2122, PRD #2112, ADR
 * 0109, decisão 8).
 *
 * O botão abre, dentro do cartão, a conversa particular de quem está logado
 * com o Assistente de Tecnologia: o servidor guarda uma por Pergunta e por
 * pessoa. Abrir lê a conversa guardada; só a nova chama o Assistente, que
 * começa explicando. A pessoa pergunta por texto.
 *
 * O rascunho que o Assistente propõe só vai para o campo de resposta do
 * cartão com o clique em "Usar este rascunho", e quem responde é o botão
 * Responder do cartão: daqui não sai resposta nem mensagem na Conversa.
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { BASE_TECNOLOGIA, FALHA_DE_CONEXAO, motivoDaRecusa } from "./demandas";

export type FalaDoMeExplique = { papel: "pessoa" | "assistente"; texto: string; rascunho: string | null };

/** O mesmo teto da rota. */
const LIMITE_DA_PERGUNTA = 4000;

export function urlDoMeExplique(perguntaId: string): string {
  return `${BASE_TECNOLOGIA}/perguntas/${encodeURIComponent(perguntaId)}/me-explique`;
}

function falasValidas(corpo: unknown): FalaDoMeExplique[] | null {
  const mensagens = (corpo as { mensagens?: unknown } | null)?.mensagens;
  if (!Array.isArray(mensagens)) return null;
  return mensagens.filter(
    (m): m is FalaDoMeExplique => typeof m?.texto === "string" && (m.papel === "pessoa" || m.papel === "assistente"),
  );
}

export function MeExplique({
  perguntaId,
  token,
  onUsarRascunho,
}: {
  perguntaId: string;
  token: string;
  /** O clique em "Usar este rascunho": quem desenha o cartão põe o texto no campo de resposta. */
  onUsarRascunho: (rascunho: string) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [falas, setFalas] = useState<FalaDoMeExplique[] | null>(null);
  const [texto, setTexto] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function pedir(metodo: "GET" | "POST", corpo?: { texto?: string }): Promise<FalaDoMeExplique[] | null> {
    const resposta = await fetch(urlDoMeExplique(perguntaId), {
      method: metodo,
      headers: { Authorization: `Bearer ${token}`, ...(corpo ? { "Content-Type": "application/json" } : {}) },
      ...(corpo ? { body: JSON.stringify(corpo) } : {}),
    });
    if (!resposta.ok) {
      setErro(await motivoDaRecusa(resposta));
      return null;
    }
    return falasValidas(await resposta.json());
  }

  async function rodar(passo: () => Promise<void>) {
    setCarregando(true);
    setErro(null);
    try {
      await passo();
    } catch (e) {
      console.error("[admin/tecnologia] falha no Me explique", e);
      setErro(FALHA_DE_CONEXAO);
    } finally {
      setCarregando(false);
    }
  }

  function abrir() {
    setAberto(!aberto);
    if (aberto || falas !== null || carregando) return;
    void rodar(async () => {
      const guardadas = await pedir("GET");
      if (guardadas === null) return;
      // A conversa nova começa com a explicação do Assistente.
      setFalas(guardadas.length > 0 ? guardadas : await pedir("POST", {}));
    });
  }

  function perguntar() {
    const pergunta = texto.trim();
    if (!pergunta || carregando) return;
    void rodar(async () => {
      const novas = await pedir("POST", { texto: pergunta });
      if (novas !== null) {
        setFalas(novas);
        setTexto("");
      }
    });
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={abrir}
        aria-expanded={aberto}
        className="px-3 py-1.5 rounded-lg border border-primary text-primary bg-white text-sm font-semibold"
      >
        Me explique
      </button>
      {aberto && (
        <section
          role="region"
          aria-label="Me explique"
          className="rounded-xl bg-white border border-slate-200 px-3 py-3 space-y-3"
        >
          <p className="normal-case text-xs text-text-secondary">
            Conversa só sua com o Assistente de Tecnologia. Ninguém mais vê, e nada daqui é enviado.
          </p>
          {(falas ?? []).map((fala, i) => (
            <div
              key={i}
              className={`normal-case rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
                fala.papel === "pessoa" ? "ml-8 bg-primary/10 text-slate-900" : "mr-8 bg-slate-50 text-slate-800"
              }`}
            >
              <p>{fala.texto}</p>
              {fala.papel === "assistente" && fala.rascunho && (
                <div className="mt-2 rounded-lg border border-slate-200 bg-white px-3 py-2 space-y-2">
                  <p className="text-xs font-semibold text-slate-700">Rascunho de resposta</p>
                  <p>{fala.rascunho}</p>
                  <button
                    type="button"
                    onClick={() => onUsarRascunho(fala.rascunho ?? "")}
                    className="px-3 py-1 rounded-lg bg-primary text-white text-xs font-semibold"
                  >
                    Usar este rascunho
                  </button>
                </div>
              )}
            </div>
          ))}
          {carregando && (
            <p className="flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              O Assistente está escrevendo.
            </p>
          )}
          {erro && (
            <p role="alert" className="normal-case px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {erro}
            </p>
          )}
          <div className="flex gap-2">
            <textarea
              aria-label="Pergunte ao Assistente"
              rows={1}
              maxLength={LIMITE_DA_PERGUNTA}
              placeholder="Pergunte o que quiser sobre este pedido."
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-xl outline-none focus:border-primary focus:ring-1 focus:ring-primary bg-white resize-y"
            />
            <button
              type="button"
              onClick={perguntar}
              disabled={!texto.trim() || carregando}
              className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Perguntar
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
