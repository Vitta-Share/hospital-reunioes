"use client";

import { useState } from "react";

import { ACOES_DE_LEITURA, baixarDossie, type ItemDaTrilha, type TrilhaDoCaso as Trilha } from "@/lib/conduta/trilha";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 disabled:text-slate-600 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

function quando(iso: string | null): string {
  if (!iso) return "sem data";
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(iso));
}

function Item({ item }: { item: ItemDaTrilha }) {
  const rotuloDoCodigo = item.tipo === "documento" ? "Código de integridade" : "Código da linha";
  return (
    <li className="space-y-0.5 border-l-2 border-slate-200 pl-3">
      <p className="text-sm font-semibold text-slate-900 break-words">
        {item.versao ? `${item.titulo}, versão ${item.versao}` : item.titulo}
      </p>
      <p className="text-xs text-slate-600">{`${item.autor || "Sem autor registrado"}, ${quando(item.data)}, ${item.origem}`}</p>
      <p className="text-xs text-slate-500 break-all">
        {item.codigo ? `${rotuloDoCodigo}: ${item.codigo}` : `${rotuloDoCodigo}: não registrado no envio`}
      </p>
    </li>
  );
}

/** A área "Trilha do caso" (issue #1837): as gavetas do rito, a linha do
 * tempo de atos e documentos, a conferência da cadeia e o BAIXAR DOSSIÊ. */
export function TrilhaDoCaso({ casoId, protocolo, trilha }: { casoId: string; protocolo: string; trilha: Trilha | null }) {
  const [comLeituras, setComLeituras] = useState(false);
  const [baixando, setBaixando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  if (!trilha) return null;

  const leituras = trilha.linha_do_tempo.filter((i) => i.tipo === "ato" && ACOES_DE_LEITURA.has(i.acao ?? ""));
  const itens = comLeituras ? trilha.linha_do_tempo : trilha.linha_do_tempo.filter((i) => !leituras.includes(i));

  const baixar = async () => {
    setBaixando(true);
    setAviso(null);
    try {
      await baixarDossie(casoId, protocolo);
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setBaixando(false);
    }
  };

  return (
    <section aria-label="Trilha do caso" className={`${CARTAO} px-4 py-4 space-y-4`}>
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-slate-900">Trilha do caso</h2>
        <p className="text-sm text-slate-700">Tudo o que foi feito e assinado neste caso.</p>
        <p
          role={trilha.conferencia.intacta ? undefined : "alert"}
          className={`text-sm ${trilha.conferencia.intacta ? "text-slate-600" : "font-semibold text-red-700"}`}
        >
          {trilha.conferencia.texto}
        </p>
      </div>

      {trilha.pode_baixar_dossie && (
        <div className="space-y-1">
          <button type="button" className={BOTAO} disabled={baixando} onClick={() => void baixar()}>
            BAIXAR DOSSIÊ
          </button>
          <p className="text-xs text-slate-500">O download fica registrado na trilha, com quem baixou e quando.</p>
          {aviso && (
            <p role="alert" className="text-sm text-red-700">
              {aviso}
            </p>
          )}
        </div>
      )}

      {trilha.gavetas.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-900">Gavetas do rito</h3>
          <ul aria-label="Gavetas do rito" className="space-y-1">
            {trilha.gavetas.map((gaveta) => (
              <li key={gaveta.rotulo} className="text-sm text-slate-800 break-words">
                <span className="font-semibold">{`${gaveta.rotulo}: `}</span>
                <span className={gaveta.situacao === "Assinado" ? "text-emerald-700" : "text-amber-700"}>
                  {gaveta.situacao.toLowerCase()}
                </span>
                <span className="text-xs text-slate-500">{` (${gaveta.origem})`}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-900">Linha do tempo</h3>
        <ol aria-label="Linha do tempo" className="space-y-3">
          {itens.map((item, indice) => (
            <Item key={`${item.tipo}-${item.codigo ?? indice}-${indice}`} item={item} />
          ))}
        </ol>
        {leituras.length > 0 && (
          <button type="button" className={BOTAO_CLARO} onClick={() => setComLeituras(!comLeituras)}>
            {comLeituras ? "ESCONDER AS LEITURAS" : `MOSTRAR AS LEITURAS (${leituras.length})`}
          </button>
        )}
      </div>
    </section>
  );
}
