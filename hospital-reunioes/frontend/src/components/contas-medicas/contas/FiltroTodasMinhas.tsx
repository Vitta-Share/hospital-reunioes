"use client";

import { useEffect, useState } from "react";

import { Legenda } from "@/components/ui/Legenda";
import { LEGENDA_DO_RECORTE, RECORTES, type Recorte } from "@/lib/contas-medicas/textos";

const CHAVE = "contas-medicas:recorte";

/**
 * A escolha entre "Todas" e "Minhas" (issue #1955), guardada no navegador.
 * Sem escolha guardada, vale "Todas". O armazenamento pode faltar (navegação
 * privada, cota cheia, bloqueio) e aí lança erro: a leitura cai em "Todas" e a
 * gravação só deixa de lembrar, sem quebrar a tela.
 */
export function useRecorte(): [Recorte, (recorte: Recorte) => void] {
  // Começa em "Todas" e só lê depois de montar: o servidor não tem o
  // armazenamento, e ler no primeiro render desencontraria a hidratação.
  const [recorte, setRecorte] = useState<Recorte>("todas");

  useEffect(() => {
    setRecorte(lerEscolha());
  }, []);

  const escolher = (novo: Recorte) => {
    setRecorte(novo);
    gravarEscolha(novo);
  };

  return [recorte, escolher];
}

function lerEscolha(): Recorte {
  try {
    return window.localStorage.getItem(CHAVE) === "minhas" ? "minhas" : "todas";
  } catch {
    return "todas";
  }
}

function gravarEscolha(recorte: Recorte): void {
  try {
    window.localStorage.setItem(CHAVE, recorte);
  } catch {
    // Sem armazenamento a escolha vale só para a página aberta.
  }
}

/** "Todas" e "Minhas" numa peça só, com a Legenda de uma frase embaixo. */
export function FiltroTodasMinhas({ valor, onMudar }: { valor: Recorte; onMudar: (recorte: Recorte) => void }) {
  return (
    <div className="flex flex-col items-end">
      <div role="group" aria-label="Todas ou Minhas" className="inline-flex shrink-0 rounded-xl bg-slate-100 p-1">
        {RECORTES.map(({ valor: opcao, rotulo }) => (
          <button
            key={opcao}
            type="button"
            aria-pressed={valor === opcao}
            onClick={() => onMudar(opcao)}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors motion-reduce:transition-none ${
              valor === opcao ? "bg-white text-primary shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {rotulo}
          </button>
        ))}
      </div>
      <Legenda>{LEGENDA_DO_RECORTE}</Legenda>
    </div>
  );
}
