"use client";

import { useState } from "react";

import { chamarComite } from "@/lib/conduta/comite";
import { baixarEtiqueta, dataBr, type GuardaDoCaso } from "@/lib/conduta/guarda";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

/** Hoje em São Paulo, no formato do campo de data. */
function hoje(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
}

/**
 * A etapa "ARQUIVAR PAPEL" e a guarda do caso (issue #1838): os originais em
 * papel esperados, a etiqueta do envelope, o registro do lacre e o "Congelar
 * caso" da coordenação. O servidor diz quem pode o quê.
 */
export function ArquivarPapel({
  casoId,
  protocolo,
  guarda,
  aoMudar,
}: {
  casoId: string;
  protocolo: string;
  guarda: GuardaDoCaso | null;
  aoMudar: () => void;
}) {
  const [data, setData] = useState(hoje);
  const [local, setLocal] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  if (!guarda || (!guarda.encerrado && !guarda.pode_congelar && !guarda.congelado_em)) return null;

  const localDoCampo = local ?? guarda.local_padrao ?? "";

  const agir = async (acao: () => Promise<unknown>) => {
    setOcupado(true);
    setAviso(null);
    try {
      await acao();
      aoMudar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-label="Arquivar papel" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Arquivar papel e guarda</h2>

      {guarda.eliminado_em ? (
        <p className="text-sm text-slate-800">
          {`O conteúdo deste caso foi eliminado em ${dataBr(guarda.eliminado_em)}, ao fim da guarda. Elimine o envelope com os originais em papel.`}
        </p>
      ) : (
        guarda.guardar_ate && <p className="text-sm text-slate-800">{`Guardar até ${dataBr(guarda.guardar_ate)}.`}</p>
      )}

      {guarda.congelado_em && (
        <p role="status" className="text-sm font-semibold text-[#282760]">
          Caso congelado. Nada dele é eliminado enquanto estiver congelado.
        </p>
      )}

      {guarda.encerrado && !guarda.eliminado_em && (
        <>
          {guarda.originais.length > 0 ? (
            <ul aria-label="Originais esperados" className="space-y-1">
              {guarda.originais.map((original) => (
                <li key={original.rotulo} className="flex flex-wrap justify-between gap-2 text-sm text-slate-800">
                  <span>{original.rotulo}</span>
                  <span className={original.situacao === "Assinado" ? "text-emerald-700" : "text-slate-500"}>
                    {original.situacao}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Este rito não tem original em papel.</p>
          )}

          {guarda.pode_imprimir && (
            <button
              type="button"
              className={BOTAO_CLARO}
              disabled={ocupado}
              onClick={() => void agir(() => baixarEtiqueta(casoId, protocolo))}
            >
              IMPRIMIR ETIQUETA
            </button>
          )}

          {guarda.lacre ? (
            <p className="text-sm text-slate-800">
              {`Lacrado por ${guarda.lacre.por} em ${dataBr(guarda.lacre.em)}. Local de guarda: ${guarda.lacre.local}.`}
            </p>
          ) : (
            guarda.pode_lacrar && (
              <form
                aria-label="Registrar o lacre"
                className="space-y-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  void agir(() =>
                    chamarComite(`/casos/${casoId}/lacre`, { method: "POST", body: { data, local: localDoCampo } })
                  );
                }}
              >
                <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                  <span>Data do lacre</span>
                  <input type="date" className={CAMPO} value={data} max={hoje()} onChange={(e) => setData(e.target.value)} />
                </label>
                <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                  <span>Local de guarda</span>
                  <input className={CAMPO} value={localDoCampo} maxLength={300} onChange={(e) => setLocal(e.target.value)} />
                </label>
                <button type="submit" className={BOTAO} disabled={ocupado || !data || !localDoCampo.trim()}>
                  REGISTRAR LACRE
                </button>
              </form>
            )
          )}
        </>
      )}

      {guarda.pode_congelar && (
        <div className="space-y-1">
          <p className="text-xs text-slate-600">Para caso com processo judicial ou administrativo.</p>
          <button
            type="button"
            className={BOTAO_CLARO}
            disabled={ocupado}
            onClick={() =>
              void agir(() =>
                chamarComite(`/casos/${casoId}/${guarda.congelado_em ? "descongelamento" : "congelamento"}`, {
                  method: "POST",
                  body: {},
                })
              )
            }
          >
            {guarda.congelado_em ? "DESCONGELAR" : "CONGELAR CASO"}
          </button>
        </div>
      )}

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </section>
  );
}
