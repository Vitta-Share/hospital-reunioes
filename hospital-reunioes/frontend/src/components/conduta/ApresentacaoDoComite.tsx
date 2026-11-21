"use client";

import { useEffect, useState } from "react";

import { ModalPortal } from "@/components/ui/ModalPortal";
import { CARTOES_DO_PRIMEIRO_ACESSO, CHAVE_DA_APRESENTACAO } from "@/lib/conduta/guia";
import { createClient } from "@/lib/supabase/client";

/**
 * Os cinco cartões do primeiro acesso ao Comitê de Conduta (issue #1842,
 * regra T9). Quem decide se a pessoa já os viu é o layout, pelo cadastro de
 * login dela; aqui, assim que os cartões aparecem, a marca é gravada, para
 * que não voltem em outra tela nem em outro aparelho. Se a gravação falhar,
 * eles voltam no próximo acesso, e o guia continua no mesmo lugar.
 *
 * O navegador também lembra, enquanto a aba vive: voltar e avançar restauram
 * do cache do roteador o layout montado antes da marca, ainda com os cartões
 * dentro, e sem esta lembrança eles abririam de novo (revisão do PR #2107).
 * A lembrança é por pessoa, porque sair e entrar com outro login não recarrega
 * a aba.
 */
const jaApresentadaNestaAba = new Set<string>();

export function ApresentacaoDoComite({ pessoa }: { pessoa: string }) {
  const [aberta, setAberta] = useState(() => !jaApresentadaNestaAba.has(pessoa));
  const [indice, setIndice] = useState(0);

  useEffect(() => {
    if (jaApresentadaNestaAba.has(pessoa)) return;
    jaApresentadaNestaAba.add(pessoa);
    createClient()
      .auth.updateUser({ data: { [CHAVE_DA_APRESENTACAO]: new Date().toISOString() } })
      .catch(() => undefined);
  }, [pessoa]);

  if (!aberta) return null;

  const total = CARTOES_DO_PRIMEIRO_ACESSO.length;
  const cartao = CARTOES_DO_PRIMEIRO_ACESSO[indice];
  const ultimo = indice === total - 1;

  return (
    <ModalPortal>
      <div className="modal-backdrop z-[300] flex items-center justify-center px-4">
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="apresentacao-do-comite"
          className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-5 sm:p-6 min-w-0"
        >
          <h2 id="apresentacao-do-comite" className="text-lg font-bold text-slate-900 normal-case tracking-normal">
            Bem-vindo ao Comitê de Conduta
          </h2>
          <p className="text-xs font-semibold text-slate-500 mt-1">
            {indice + 1} de {total}
          </p>
          <div className="mt-3 rounded-2xl border border-border bg-[#EAEAF0]/40 px-4 py-3">
            <h3 className="text-base font-semibold text-[#282760] normal-case tracking-normal">{cartao.titulo}</h3>
            <p className="text-sm text-slate-700 mt-1">{cartao.texto}</p>
          </div>
          <div className="mt-4 flex flex-col-reverse sm:flex-row sm:justify-between gap-2">
            {indice > 0 ? (
              <button
                type="button"
                onClick={() => setIndice(indice - 1)}
                className="w-full sm:w-auto min-h-[44px] px-4 rounded-xl border border-slate-200 text-slate-700 text-sm font-semibold"
              >
                Voltar
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setAberta(false)}
                className="w-full sm:w-auto min-h-[44px] px-4 rounded-xl border border-slate-200 text-slate-700 text-sm font-semibold"
              >
                Pular
              </button>
            )}
            <button
              type="button"
              onClick={() => (ultimo ? setAberta(false) : setIndice(indice + 1))}
              className="w-full sm:w-auto min-h-[44px] px-4 rounded-xl bg-[#282760] text-white text-sm font-semibold"
            >
              {ultimo ? "Começar" : "Próximo"}
            </button>
          </div>
        </div>
      </div>
    </ModalPortal>
  );
}
