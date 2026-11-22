"use client";

import Link from "next/link";
import { useState } from "react";

import { dataCurta } from "@/components/conduta/MedidaERetorno";
import { chamarComite } from "@/lib/conduta/comite";
import type { MarcoDaVerificacao, VerificacaoDeRetaliacao as Dados } from "@/lib/conduta/retaliacao";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

interface Props {
  casoId: string;
  dados: Dados | null;
  /** O botão REGISTRAR VERIFICAÇÃO da caixa "O QUE FAZER AGORA" foi tocado. */
  registrando: boolean;
  aoMudar: () => void;
}

function situacao(m: MarcoDaVerificacao): string {
  if (m.situacao === "aguardando") return `Em ${dataCurta(m.data)}`;
  if (m.situacao === "pendente") return `Pendente desde ${dataCurta(m.data)}`;
  const quem = m.verificada_por ? ` por ${m.verificada_por}` : "";
  return `${m.houve ? "Houve mudança desfavorável" : "Não houve mudança desfavorável"}. Registrada${quem} em ${dataCurta(m.verificada_em)}.`;
}

/**
 * O acompanhamento contra retaliação (issue #1839; especificação, 6.11 e 18):
 * as verificações de 30, 90 e 180 dias depois do encerramento. A coordenação
 * responde com um clique, "Não houve" ou "Houve", com a observação se quiser.
 * Quando houve, a tela oferece abrir um caso novo de retaliação.
 */
export function VerificacaoDeRetaliacao({ casoId, dados, registrando, aoMudar }: Props) {
  const [observacao, setObservacao] = useState("");
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [aberto, setAberto] = useState<{ id: string; protocolo: string } | null>(null);

  if (!dados) return null;
  const pendente = dados.marco_pendente;

  const agir = async (caminho: string, body: unknown): Promise<unknown> => {
    setOcupado(true);
    setAviso(null);
    try {
      const corpo = await chamarComite(`/casos/${casoId}/verificacoes-de-retaliacao${caminho}`, { method: "POST", body });
      aoMudar();
      return corpo;
    } catch (e) {
      setAviso((e as Error).message);
      return null;
    } finally {
      setOcupado(false);
    }
  };

  const responder = async (houve: boolean) => {
    if ((await agir("", { marco: pendente, houve, observacao })) !== null) setObservacao("");
  };

  const abrirCasoNovo = async (marco: number) => {
    const corpo = (await agir("/caso-novo", { marco })) as { id: string; protocolo: string } | null;
    if (corpo) setAberto(corpo);
  };

  return (
    <section aria-label="Acompanhamento" className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">Acompanhamento contra retaliação</h2>
      <p className="text-sm text-slate-600">
        Em 30, 90 e 180 dias, verifique se houve mudança desfavorável para quem relatou: desligamento, escala,
        transferência ou avaliação.
      </p>
      <ul className="space-y-2">
        {dados.marcos.map((m) => (
          <li key={m.marco} className="space-y-1">
            <p className="text-sm font-semibold text-slate-900">{`Verificação de ${m.marco} dias`}</p>
            <p className="text-sm text-slate-700">{situacao(m)}</p>
            {m.observacao && <p className="text-sm text-slate-700">{m.observacao}</p>}
            {m.caso_novo && (
              <p className="text-sm text-slate-700">
                {"Caso novo de retaliação: "}
                <Link href={`/comite-de-conduta/casos/${m.caso_novo.id}`} className="font-semibold text-[#282760] underline">
                  {m.caso_novo.protocolo}
                </Link>
              </p>
            )}
            {m.pode_abrir_caso_novo && (
              <button type="button" className={BOTAO} disabled={ocupado} onClick={() => void abrirCasoNovo(m.marco)}>
                ABRIR CASO DE RETALIAÇÃO
              </button>
            )}
          </li>
        ))}
      </ul>

      {registrando && dados.pode_registrar && pendente && (
        <div className="space-y-2 border-t border-border pt-3">
          <p className="text-sm font-semibold text-slate-900">{`Verificação de ${pendente} dias: houve mudança desfavorável?`}</p>
          <label className="block text-sm text-slate-700">
            Observação (opcional)
            <textarea
              className={`${CAMPO} mt-1`}
              rows={3}
              maxLength={2000}
              value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
            />
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void responder(false)}>
              Não houve
            </button>
            <button type="button" className={BOTAO} disabled={ocupado} onClick={() => void responder(true)}>
              Houve
            </button>
          </div>
        </div>
      )}

      {aberto && (
        <p role="status" className="text-sm text-slate-700">
          {`Caso novo de retaliação aberto: ${aberto.protocolo}. Ele entrou na triagem.`}
        </p>
      )}
      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </section>
  );
}
