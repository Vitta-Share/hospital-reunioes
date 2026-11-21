"use client";

import { cloneElement, useId, useState, type ReactElement } from "react";

interface DicaProps {
  /** A frase que aparece; curta, de uma linha ou duas. */
  texto: string;
  /** O elemento que recebe o mouse e o foco: um link ou um botão. */
  children: ReactElement<{ "aria-describedby"?: string }>;
}

/**
 * A dica que aparece ao passar o mouse ou ao chegar pelo teclado (issue
 * #1950). Some ao sair, ao perder o foco ou com Esc. O elemento embrulhado
 * aponta para ela por `aria-describedby`, para o leitor de tela ler a frase
 * junto com o nome.
 */
export function Dica({ texto, children }: DicaProps) {
  const id = useId();
  const [aberta, setAberta] = useState(false);

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setAberta(true)}
      onMouseLeave={() => setAberta(false)}
      onFocus={() => setAberta(true)}
      onBlur={() => setAberta(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") setAberta(false);
      }}
    >
      {cloneElement(children, { "aria-describedby": aberta ? id : undefined })}
      {aberta && (
        <span
          role="tooltip"
          id={id}
          className="pointer-events-none absolute left-0 top-full z-20 mt-1 w-max max-w-64 rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-normal normal-case tracking-normal text-white shadow-lg"
        >
          {texto}
        </span>
      )}
    </span>
  );
}
