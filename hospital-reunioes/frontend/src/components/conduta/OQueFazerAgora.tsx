"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { Lock } from "lucide-react";

import type { Caixa } from "@/lib/conduta/comite";

const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 disabled:text-slate-600 w-full sm:w-auto";

/**
 * A caixa "O QUE FAZER AGORA" (issue #1824; especificação, seções 5.3, 18 e
 * regras C9 e C10): uma frase, um botão principal e o "Como fazer" em três
 * linhas, que abrem ao toque. Botão bloqueado mostra o motivo numa linha.
 *
 * O botão age (`aoAgir`) ou leva a outra tela (`href`).
 */
export function OQueFazerAgora({
  caixa,
  aoAgir,
  href,
  ocupado = false,
}: {
  caixa: Caixa;
  aoAgir?: (acao: string) => void;
  href?: string;
  ocupado?: boolean;
}) {
  const [aberto, setAberto] = useState(false);
  const idDoComo = useId();
  const bloqueado = Boolean(caixa.bloqueio);

  return (
    <section
      aria-label="O que fazer agora"
      className="rounded-2xl border-2 border-[#282760] bg-[#EAEAF0] px-4 py-4 space-y-3 mb-5"
    >
      <h2 className="text-xs font-bold tracking-wide text-[#282760]">O QUE FAZER AGORA</h2>
      <p className="text-base font-semibold text-slate-900">{caixa.frase}</p>
      {caixa.botao &&
        (href && !bloqueado ? (
          <Link href={href} className={BOTAO}>
            {caixa.botao}
          </Link>
        ) : (
          <button
            type="button"
            className={BOTAO}
            disabled={bloqueado || ocupado || !aoAgir}
            onClick={() => caixa.acao && aoAgir?.(caixa.acao)}
          >
            {caixa.botao}
          </button>
        ))}
      {caixa.bloqueio && (
        <p className="flex gap-2 items-start text-sm text-slate-700">
          <Lock className="w-4 h-4 shrink-0 mt-0.5 text-slate-500" aria-hidden />
          <span>{caixa.bloqueio}</span>
        </p>
      )}
      <div>
        <button
          type="button"
          aria-expanded={aberto}
          aria-controls={idDoComo}
          onClick={() => setAberto((v) => !v)}
          className="text-sm font-semibold text-[#282760] underline"
        >
          Como fazer
        </button>
        {aberto && (
          <ol id={idDoComo} className="mt-2 space-y-1 list-decimal pl-5 text-sm text-slate-700">
            {caixa.como_fazer.map((linha) => (
              <li key={linha}>{linha}</li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
