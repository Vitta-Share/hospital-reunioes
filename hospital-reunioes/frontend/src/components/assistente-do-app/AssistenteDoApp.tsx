"use client";

import { useRef, useState } from "react";
import { Bot, Send, X } from "lucide-react";

import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";
import { FALHA_DA_CONVERSA, perguntarAoAssistente, type FalaDoAssistente } from "@/lib/assistente-do-app/conversa";

import { RoteiroDoBug } from "./RoteiroDoBug";

/**
 * O robô do Assistente do app (issue #2267, ADR 0113, decisão 8): no canto
 * inferior direito de toda área logada, para todo usuário. Abre um painel com
 * as sugestões "Relatar um bug" e "Tirar uma dúvida" e o campo livre. A
 * dúvida vive só aqui, no estado da tela: não vira Demanda e some ao
 * recarregar a página. O bug segue o Roteiro do bug (`RoteiroDoBug`, issue
 * #2275), que vira Demanda. Cancelar o relato, terminar o envio ou fechar o
 * painel devolvem as sugestões e o campo livre.
 *
 * No celular, sobe acima da barra inferior (`BottomNav`).
 */
export function AssistenteDoApp() {
  const { participante } = useCurrentParticipante();
  const [aberto, setAberto] = useState(false);
  const [falas, setFalas] = useState<FalaDoAssistente[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [relatando, setRelatando] = useState(false);
  const campo = useRef<HTMLTextAreaElement>(null);

  function fecharOPainel() {
    setAberto(false);
    setRelatando(false);
  }

  async function enviar() {
    const pergunta = texto.trim();
    if (!pergunta || enviando) return;
    const conversa: FalaDoAssistente[] = [...falas, { role: "user", content: pergunta }];
    setFalas(conversa);
    setTexto("");
    setErro(null);
    setEnviando(true);
    try {
      const resposta = await perguntarAoAssistente(conversa, participante);
      setFalas([...conversa, { role: "assistant", content: resposta }]);
    } catch (e) {
      // A pergunta volta para o campo, e a conversa fica como estava.
      setFalas(falas);
      setTexto(pergunta);
      setErro(e instanceof Error ? e.message : FALHA_DA_CONVERSA);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div data-assistente-do-app className="fixed right-4 bottom-[96px] md:right-6 md:bottom-6 z-40">
      {aberto && (
        <div
          role="dialog"
          aria-label="Assistente do app"
          className="absolute bottom-full right-0 mb-3 w-[360px] max-w-[calc(100vw-2rem)] bg-white border border-slate-200 rounded-2xl shadow-premium-strong overflow-hidden flex flex-col"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
              <Bot className="w-4 h-4 text-primary" strokeWidth={1.75} />
              Assistente do app
            </h3>
            <button
              type="button"
              onClick={fecharOPainel}
              aria-label="Fechar"
              className="w-6 h-6 rounded-md hover:bg-slate-100 flex items-center justify-center text-slate-400"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="max-h-[360px] overflow-y-auto px-4 py-3 flex flex-col gap-2">
            {falas.map((fala, i) => (
              <p
                key={i}
                className={`text-sm whitespace-pre-wrap rounded-xl px-3 py-2 max-w-[85%] ${
                  fala.role === "user"
                    ? "self-end bg-primary text-white"
                    : "self-start bg-slate-100 text-slate-800"
                }`}
              >
                {fala.content}
              </p>
            ))}
            {relatando && <RoteiroDoBug aoSair={() => setRelatando(false)} />}
            {!relatando && (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setRelatando(true)}
                  className="px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-sm font-medium hover:bg-primary/10 transition-colors"
                >
                  Relatar um bug
                </button>
                <button
                  type="button"
                  onClick={() => campo.current?.focus()}
                  className="px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-sm font-medium hover:bg-primary/10 transition-colors"
                >
                  Tirar uma dúvida
                </button>
              </div>
            )}
            {enviando && <p className="self-start text-xs text-slate-400">Pensando…</p>}
            {erro && <p className="text-xs text-red-600">{erro}</p>}
          </div>

          {!relatando && (
            <form
              className="flex items-end gap-2 px-3 py-3 border-t border-slate-100"
              onSubmit={(e) => {
                e.preventDefault();
                void enviar();
              }}
            >
              <textarea
                ref={campo}
                aria-label="Sua pergunta"
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void enviar();
                  }
                }}
                rows={2}
                maxLength={8000}
                placeholder="Escreva a sua dúvida"
                className="flex-1 resize-none text-sm rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:border-primary"
              />
              <button
                type="submit"
                aria-label="Enviar"
                disabled={enviando || !texto.trim()}
                className="w-9 h-9 rounded-lg bg-primary text-white flex items-center justify-center disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => (aberto ? fecharOPainel() : setAberto(true))}
        aria-label="Assistente do app"
        aria-expanded={aberto}
        className="w-12 h-12 rounded-full bg-primary text-white shadow-premium-strong flex items-center justify-center hover:bg-primary/90 transition-colors"
      >
        <Bot className="w-6 h-6" strokeWidth={1.75} />
      </button>
    </div>
  );
}
