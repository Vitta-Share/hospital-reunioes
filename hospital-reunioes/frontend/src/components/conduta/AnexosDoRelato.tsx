"use client";

/**
 * Os anexos do relato na tela do caso (issue #1844). O backend entrega o
 * arquivo já sem os dados de origem e grava a abertura na trilha. Não há nome
 * de arquivo: o canal não guarda o nome original.
 */

import { useState } from "react";

import { ROTULOS_DO_ANEXO, abrirAnexo, type AnexoDoRelato } from "@/lib/conduta/anexos";
import { dataEHora } from "@/lib/conduta/depoimentos";

const BOTAO_PEQUENO =
  "inline-flex min-h-[44px] items-center justify-center rounded-xl border border-border bg-white px-3 py-2 text-sm font-semibold text-[#282760] hover:border-[#282760]/40";

export function AnexosDoRelato({ casoId, anexos }: { casoId: string; anexos: AnexoDoRelato[] }) {
  const [aviso, setAviso] = useState<string | null>(null);

  if (anexos.length === 0) return null;

  const abrir = async (anexoId: string) => {
    setAviso(null);
    try {
      window.open(await abrirAnexo(casoId, anexoId), "_blank", "noopener");
    } catch (e) {
      setAviso((e as Error).message);
    }
  };

  return (
    <div className="space-y-2 pt-2">
      <h3 className="text-sm font-semibold text-slate-900">Anexos do relato</h3>
      <ul aria-label="Anexos do relato" className="space-y-2">
        {anexos.map((anexo, indice) => (
          <li key={anexo.id} className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-700">
            <span>
              {`${ROTULOS_DO_ANEXO[anexo.tipo]} ${indice + 1}, enviado em ${dataEHora(anexo.enviado_em)}`}
              {anexo.origem === "complemento" ? " (complemento)" : ""}
            </span>
            <button type="button" className={BOTAO_PEQUENO} onClick={() => void abrir(anexo.id)}>
              {`Abrir ${ROTULOS_DO_ANEXO[anexo.tipo].toLowerCase()} ${indice + 1}`}
            </button>
          </li>
        ))}
      </ul>
      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </div>
  );
}
