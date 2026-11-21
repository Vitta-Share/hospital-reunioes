"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/**
 * A Legenda: a frase curta que explica a tela ou o comando (issue #1950).
 *
 * Um interruptor "Legendas" liga e desliga todas as Legendas debaixo do mesmo
 * `LegendasProvider`, e a escolha fica no navegador, na chave que o provedor
 * recebe. Sem provedor, a Legenda aparece.
 *
 * O armazenamento pode faltar (navegação privada, bloqueio do navegador) e aí
 * lança erro: a leitura cai em Legendas ligadas e a gravação só deixa de
 * lembrar, sem quebrar a tela.
 */

interface EstadoDasLegendas {
  ligadas: boolean;
  alternar: () => void;
}

const LegendasContext = createContext<EstadoDasLegendas>({ ligadas: true, alternar: () => {} });

export function LegendasProvider({ chave, children }: { chave: string; children: ReactNode }) {
  // Começa ligada e só lê depois de montar: o servidor não tem o
  // armazenamento, e ler no primeiro render desencontraria a hidratação.
  const [ligadas, setLigadas] = useState(true);

  useEffect(() => {
    setLigadas(lerPreferencia(chave));
  }, [chave]);

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

function lerPreferencia(chave: string): boolean {
  try {
    return window.localStorage.getItem(chave) !== "0";
  } catch {
    return true;
  }
}

function gravarPreferencia(chave: string, ligadas: boolean): void {
  try {
    window.localStorage.setItem(chave, ligadas ? "1" : "0");
  } catch {
    // Sem armazenamento a escolha vale só para a página aberta.
  }
}
