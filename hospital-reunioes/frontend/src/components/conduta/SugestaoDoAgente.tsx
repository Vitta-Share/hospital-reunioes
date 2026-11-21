"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";

import { chamarComite } from "@/lib/conduta/comite";
import type { ItemDaSugestao, SugestaoDoAgente as Sugestao } from "@/lib/conduta/sugestao";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

function Item({
  item,
  podeResponder,
  ocupado,
  aoResponder,
}: {
  item: ItemDaSugestao;
  podeResponder: boolean;
  ocupado: boolean;
  aoResponder: (item: string, resposta: "confirmo" | "discordo", motivo?: string) => void;
}) {
  const [discordando, setDiscordando] = useState(false);
  const [motivo, setMotivo] = useState("");

  return (
    <li aria-label={item.titulo} className="border-t border-border pt-3 space-y-1 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-900">{item.titulo}</h3>
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">{item.rotulo}</span>
      </div>
      <p className="text-sm text-slate-800 whitespace-pre-line break-words">{item.valor}</p>
      <p className="text-sm text-slate-600 break-words">{`Por quê: ${item.justificativa}`}</p>
      {item.trecho && <p className="text-sm italic text-slate-500 break-words">{`Trecho do relato: "${item.trecho}"`}</p>}

      {item.resposta === "confirmo" && <p className="text-xs font-semibold text-emerald-700">A coordenação confirmou.</p>}
      {item.resposta === "discordo" && (
        <p className="text-xs font-semibold text-red-700">{`A coordenação discordou: ${item.motivo ?? ""}`}</p>
      )}

      {podeResponder && !item.resposta && !discordando && (
        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          <button type="button" className={BOTAO} disabled={ocupado} onClick={() => aoResponder(item.item, "confirmo")}>
            CONFIRMO
          </button>
          <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => setDiscordando(true)}>
            DISCORDO
          </button>
        </div>
      )}
      {podeResponder && !item.resposta && discordando && (
        <form
          aria-label={`Discordar: ${item.titulo}`}
          className="space-y-2 pt-1"
          onSubmit={(e) => {
            e.preventDefault();
            aoResponder(item.item, "discordo", motivo);
          }}
        >
          <label className="text-sm font-semibold text-slate-700 space-y-1 block">
            <span>Motivo da discordância, em uma linha</span>
            <input className={CAMPO} value={motivo} maxLength={500} onChange={(e) => setMotivo(e.target.value)} />
          </label>
          <button type="submit" className={BOTAO} disabled={!motivo.trim() || ocupado}>
            GRAVAR DISCORDÂNCIA
          </button>
        </form>
      )}
    </li>
  );
}

/**
 * A sugestão do agente de triagem (issue #1827; especificação, seção 6.1):
 * cada item marcado como Sugestão, com a justificativa à vista, e o
 * possível impedimento por nome, que o aplicativo confere sem IA. A
 * coordenação confirma ou discorda item a item; discordar pede o motivo.
 */
export function SugestaoDoAgente({
  casoId,
  sugestao,
  aoResponder,
}: {
  casoId: string;
  sugestao: Sugestao;
  aoResponder: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  const responder = async (item: string, resposta: "confirmo" | "discordo", motivo = "") => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarComite(`/casos/${casoId}/sugestao`, { method: "POST", body: { item, resposta, motivo } });
      aoResponder();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <section aria-label="Sugestão do agente" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-slate-900">Sugestão do agente de triagem</h2>
        <p className="text-xs text-slate-500">O agente sugere. Quem decide é a coordenação.</p>
      </div>

      {sugestao.possivel_impedimento.length > 0 && (
        <div role="alert" className="flex gap-2 items-start rounded-xl bg-amber-50 px-3 py-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-700 mt-0.5" aria-hidden />
          <div className="text-sm text-amber-900 space-y-0.5">
            <p className="font-semibold">Possível impedimento</p>
            {sugestao.possivel_impedimento.map((i) => (
              <p key={i.membro}>{`${i.membro}: ${i.motivo}`}</p>
            ))}
          </div>
        </div>
      )}

      {sugestao.situacao === "aguardando" && <p className="text-sm text-slate-600">O agente ainda não leu este relato.</p>}
      {sugestao.situacao === "manual" && <p className="text-sm text-slate-700">{sugestao.motivo}</p>}

      {sugestao.itens.length > 0 && (
        <ul className="space-y-3">
          {sugestao.itens.map((item) => (
            <Item
              key={item.item}
              item={item}
              podeResponder={sugestao.pode_responder}
              ocupado={ocupado}
              aoResponder={(i, r, m) => void responder(i, r, m)}
            />
          ))}
        </ul>
      )}

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </section>
  );
}
