"use client";

import { useState } from "react";

import { dataCurta } from "@/components/conduta/MedidaERetorno";
import { chamarComite } from "@/lib/conduta/comite";
import { LIMITE_DA_PERGUNTA, type MensagensDoCaso as Dados } from "@/lib/conduta/mensagens";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

interface Props {
  casoId: string;
  dados: Dados | null;
  aoMudar: () => void;
}

/**
 * Mensagens (issue #1845; especificação, 5.3 e 6.1): a conversa com quem
 * relatou pela página de acompanhamento. A coordenação pergunta, partindo das
 * perguntas que o agente sugeriu na triagem, e lê o complemento. Pedido sem
 * resposta em 15 dias libera arquivar por falta de elementos; o caso
 * arquivado reabre quando a informação chega depois.
 */
export function MensagensDoCaso({ casoId, dados, aoMudar }: Props) {
  const [pergunta, setPergunta] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  if (!dados) return null;

  const agir = async (caminho: string, body?: unknown): Promise<boolean> => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarComite(`/casos/${casoId}/${caminho}`, { method: "POST", body });
      aoMudar();
      return true;
    } catch (e) {
      setAviso((e as Error).message);
      return false;
    } finally {
      setOcupado(false);
    }
  };

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await agir("mensagens", { texto: pergunta })) setPergunta("");
  };

  return (
    <section aria-label="Mensagens" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Mensagens</h2>
      <p className="text-sm text-slate-600">
        A conversa com quem relatou, pela página de acompanhamento. Quem relatou lê as perguntas quando volta à página,
        sem aviso por nenhum meio.
      </p>

      {dados.itens.length === 0 ? (
        <p className="text-sm text-slate-600">Nenhuma mensagem trocada ainda.</p>
      ) : (
        <ul className="space-y-2">
          {dados.itens.map((m) => (
            <li key={m.id} className={`rounded-xl px-3 py-2 space-y-1 ${m.de === "comite" ? "bg-slate-50" : "bg-amber-50"}`}>
              <p className="text-xs font-semibold text-slate-600">
                {m.de === "comite" ? "Pergunta do Comitê" : "Complemento de quem relatou"}
              </p>
              <p className="text-sm text-slate-800 whitespace-pre-line break-words">{m.texto}</p>
              <p className="text-xs text-slate-500">{dataCurta(m.enviada_em)}</p>
            </li>
          ))}
        </ul>
      )}

      {dados.aguardando_resposta && dados.arquivar_a_partir_de && !dados.pode_arquivar && (
        <p className="text-sm text-slate-600">
          {`Aguardando a resposta de quem relatou. Arquivar por falta de elementos fica disponível em ${dataCurta(dados.arquivar_a_partir_de)}.`}
        </p>
      )}
      {dados.pode_arquivar && (
        <div className="space-y-1">
          <p className="text-sm text-slate-700">O pedido de complemento está sem resposta há 15 dias.</p>
          <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("arquivamento")}>
            ARQUIVAR POR FALTA DE ELEMENTOS
          </button>
        </div>
      )}
      {dados.arquivado && (
        <p className="text-sm text-slate-700">
          {dados.pode_reabrir
            ? "Quem relatou mandou informação depois do arquivamento. Você pode reabrir o caso."
            : "O caso foi arquivado por falta de elementos. Se quem relatou mandar a informação, ele pode ser reaberto."}
        </p>
      )}
      {dados.pode_reabrir && (
        <button type="button" className={BOTAO} disabled={ocupado} onClick={() => void agir("reabertura")}>
          REABRIR CASO
        </button>
      )}

      {dados.pode_perguntar && (
        <form onSubmit={enviar} className="space-y-2 border-t border-border pt-3" aria-label="Enviar pergunta">
          {dados.perguntas_sugeridas.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-600">Sugestão do agente</p>
              <div className="flex flex-wrap gap-2">
                {dados.perguntas_sugeridas.map((sugerida) => (
                  <button
                    key={sugerida}
                    type="button"
                    className="rounded-full border border-border bg-white px-3 py-1 text-xs text-slate-700 hover:border-[#282760]"
                    onClick={() => setPergunta(sugerida)}
                  >
                    {sugerida}
                  </button>
                ))}
              </div>
            </div>
          )}
          <label className="block text-sm text-slate-700">
            Pergunta a quem relatou
            <textarea
              className={`${CAMPO} mt-1`}
              rows={3}
              maxLength={LIMITE_DA_PERGUNTA}
              value={pergunta}
              onChange={(e) => setPergunta(e.target.value)}
            />
          </label>
          <p className="text-xs text-slate-500">Quem relatou lê exatamente o que você escrever. Deixe nomes de fora.</p>
          <button type="submit" className={BOTAO} disabled={ocupado || !pergunta.trim()}>
            ENVIAR PERGUNTA
          </button>
        </form>
      )}

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </section>
  );
}
