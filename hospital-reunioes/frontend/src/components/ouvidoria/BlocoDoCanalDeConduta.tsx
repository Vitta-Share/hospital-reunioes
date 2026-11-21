"use client";

/**
 * A sinalização ao Canal de Conduta no Dossiê (issue #1849, ADR 0097 decisão 14).
 *
 * Manifestação de paciente sobre conduta grave de um profissional continua na
 * Ouvidoria. O botão abre um caso no Canal, com o relato integral e sem o nome
 * nem o contato de quem manifestou, e pede uma confirmação antes. Depois de
 * sinalizado, o bloco diz isso e o botão some: nada do caso do Canal volta
 * para o ouvidor.
 */

import { useState } from "react";
import { AlertCircle, Loader2, Scale } from "lucide-react";

const FALHA = "Não foi possível sinalizar o caso ao Canal de Conduta agora. Tente novamente.";

export interface CamposDoCanalDeConduta {
  /** Quando o ouvidor sinalizou o caso ao Canal (migration 202). */
  conduta_sinalizada_em?: string | null;
}

interface BlocoDoCanalDeCondutaProps {
  caso: CamposDoCanalDeConduta & { id: string };
  token: string | null;
  /** A sinalização deu certo e o Dossiê na tela ficou velho. */
  onSinalizado: () => void;
}

export function BlocoDoCanalDeConduta({ caso, token, onSinalizado }: BlocoDoCanalDeCondutaProps) {
  const [confirmando, setConfirmando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function sinalizar() {
    if (!token) return;
    setEnviando(true);
    setErro(null);
    try {
      const res = await fetch(`/api/ouvidoria/manifestacoes/${caso.id}/canal-de-conduta`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setConfirmando(false);
        onSinalizado();
        return;
      }
      const corpo = await res.json().catch(() => ({}));
      setErro(typeof corpo.detail === "string" ? corpo.detail : FALHA);
    } catch {
      setErro(FALHA);
    } finally {
      setEnviando(false);
    }
  }

  if (caso.conduta_sinalizada_em) {
    return (
      <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-slate-50 border border-slate-200 text-slate-800 text-sm">
        <Scale className="w-4 h-4 shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p data-testid="sinalizado-ao-canal" className="font-semibold">
            Sinalizado ao Canal de Conduta
          </p>
          <p className="text-xs mt-0.5 text-slate-600">
            O Comitê de Conduta recebeu o relato, sem o nome nem o contato de quem manifestou. A
            manifestação segue aberta na Ouvidoria.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {!confirmando ? (
          <button
            type="button"
            onClick={() => {
              setErro(null);
              setConfirmando(true);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 transition-colors"
          >
            <Scale className="w-3.5 h-3.5" />
            Sinalizar ao Canal de Conduta
          </button>
        ) : (
          <div className="w-full px-4 py-3 rounded-xl bg-slate-50 border border-slate-200 text-sm text-slate-700 space-y-2">
            <p>
              Abre um caso no Canal de Conduta com o relato integral, sem o nome nem o contato de quem
              manifestou. O Comitê apura a conduta do profissional, e a manifestação continua aberta
              aqui. Você não vê o caso do Canal depois.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void sinalizar()}
                disabled={enviando}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide bg-[#282760] text-white hover:opacity-90 disabled:opacity-60 transition-colors"
              >
                {enviando && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />}
                Confirmar sinalização
              </button>
              <button
                type="button"
                onClick={() => setConfirmando(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wide text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>

      {erro && (
        <div
          role="alert"
          className="flex items-start gap-2 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm"
        >
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{erro}</span>
        </div>
      )}
    </div>
  );
}

export default BlocoDoCanalDeConduta;
