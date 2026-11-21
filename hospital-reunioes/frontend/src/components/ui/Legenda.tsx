"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

/**
 * A Legenda: a frase curta que explica a tela ou o comando (issue #1950).
 *
 * Um interruptor "Legendas" liga e desliga todas as Legendas debaixo do mesmo
 * `LegendasProvider`, e a escolha fica num cookie, com o nome que o provedor
 * recebe. Quem monta o provedor lê esse cookie no servidor e passa a escolha
 * em `ligadasIniciais`: assim o HTML do servidor e o primeiro paint já vêm
 * com as Legendas como a pessoa deixou, sem a tela pular na hidratação. Sem
 * provedor, a Legenda aparece.
 *
 * O navegador pode recusar o cookie (bloqueio de cookies) e aí a gravação só
 * deixa de lembrar, sem quebrar a tela.
 */

interface EstadoDasLegendas {
  ligadas: boolean;
  alternar: () => void;
}

const LegendasContext = createContext<EstadoDasLegendas>({ ligadas: true, alternar: () => {} });

export function LegendasProvider({
  chave,
  ligadasIniciais = true,
  children,
}: {
  chave: string;
  ligadasIniciais?: boolean;
  children: ReactNode;
}) {
  const [ligadas, setLigadas] = useState(ligadasIniciais);

  const alternar = () => {
    const novo = !ligadas;
    setLigadas(novo);
    gravarPreferencia(chave, novo);
  };

  return <LegendasContext.Provider value={{ ligadas, alternar }}>{children}</LegendasContext.Provider>;
}

export function Legenda({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { ligadas } = useContext(LegendasContext);
  if (!ligadas) return null;
  return <p className={`text-slate-500 text-sm mt-0.5 ${className}`.trim()}>{children}</p>;
}

/** O interruptor "Legendas", que liga e desliga as Legendas do mesmo provedor. */
export function InterruptorDeLegendas() {
  const { ligadas, alternar } = useContext(LegendasContext);
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligadas}
      onClick={alternar}
      className="inline-flex items-center gap-2 text-xs font-medium text-slate-600"
    >
      <span
        aria-hidden="true"
        className={`relative inline-flex h-4 w-7 shrink-0 rounded-full transition-colors ${
          ligadas ? "bg-primary" : "bg-slate-300"
        }`}
      >
        <span
          className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${ligadas ? "left-3.5" : "left-0.5"}`}
        />
      </span>
      Legendas
    </button>
  );
}

/** Um ano: a escolha vale até a pessoa mudar de novo. */
const UM_ANO_EM_SEGUNDOS = 60 * 60 * 24 * 365;

function gravarPreferencia(chave: string, ligadas: boolean): void {
  try {
    document.cookie = `${chave}=${ligadas ? "1" : "0"}; path=/; max-age=${UM_ANO_EM_SEGUNDOS}; samesite=lax`;
  } catch {
    // Sem armazenamento a escolha vale só para a página aberta.
  }
}
