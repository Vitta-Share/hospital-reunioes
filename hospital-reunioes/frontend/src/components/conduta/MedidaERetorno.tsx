"use client";

import { useState } from "react";

import { chamarComite } from "@/lib/conduta/comite";
import { abrirComunicacaoDaMedida, type MedidaERetorno as Dados } from "@/lib/conduta/retorno";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

/** "2026-11-18" ou um instante ISO vira "18/11/2026", sem passar pelo fuso. */
export function dataCurta(valor: string | null | undefined): string {
  const [ano, mes, dia] = (valor ?? "").slice(0, 10).split("-");
  return ano && mes && dia ? `${dia}/${mes}/${ano}` : "";
}

interface Props {
  casoId: string;
  dados: Dados | null;
  aoMudar: () => void;
}

/**
 * O caminho do caso depois da votação (issue #1835; especificação, 6.8, 6.9 e
 * 6.10): a decisão da Direção sobre a medida, o retorno (a resposta a quem
 * relatou e a comunicação ao acusado, que só saem depois de aprovados pela
 * coordenação) e a correção de processo, com responsável e prazo.
 */
export function MedidaERetorno({ casoId, dados, aoMudar }: Props) {
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [revisando, setRevisando] = useState(false);
  const [denunciante, setDenunciante] = useState("");
  const [acusado, setAcusado] = useState("");
  const [correcao, setCorrecao] = useState<string | null>(null);
  const [responsavel, setResponsavel] = useState("");
  const [prazo, setPrazo] = useState("");
  const [comunicacao, setComunicacao] = useState<string | null>(null);

  if (!dados) return null;
  const { retorno, correcoes } = dados;
  const ultima = retorno.versoes[0] ?? null;

  const agir = async (caminho: string, body: unknown = {}, metodo = "POST"): Promise<unknown> => {
    setOcupado(true);
    setAviso(null);
    try {
      const corpo = await chamarComite(`/casos/${casoId}/${caminho}`, { method: metodo, body: metodo === "GET" ? undefined : body });
      if (metodo !== "GET") aoMudar();
      return corpo;
    } catch (e) {
      setAviso((e as Error).message);
      return null;
    } finally {
      setOcupado(false);
    }
  };

  const salvarVersao = async () => {
    if ((await agir("retorno/versoes", { denunciante, acusado })) !== null) setRevisando(false);
  };

  const gravarCorrecao = async () => {
    if ((await agir("correcoes", { texto: correcao, responsavel, prazo_em: prazo })) !== null) {
      setCorrecao(null);
      setResponsavel("");
      setPrazo("");
    }
  };

  const abrirComunicacao = async () => {
    const corpo = (await agir("retorno/comunicacao-ao-acusado", undefined, "GET")) as { texto: string } | null;
    if (corpo) setComunicacao(corpo.texto);
  };

  const abrirCopia = async () => {
    try {
      window.open(await abrirComunicacaoDaMedida(casoId), "_blank", "noopener");
    } catch (e) {
      setAviso((e as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      {dados.com_medida ? (
        dados.enviado_a_direcao_em && (
          <section aria-label="Decisão da Direção" className={`${CARTAO} px-4 py-4 space-y-2`}>
            <h2 className="text-base font-semibold text-slate-900">Decisão da Direção</h2>
            <p className="text-xs text-slate-500">{`Recomendação enviada em ${dataCurta(dados.enviado_a_direcao_em)}.`}</p>
            {dados.decisao ? (
              <>
                <p className="text-sm font-semibold text-slate-900">{dados.decisao.decisao}</p>
                <p className="text-xs text-slate-500">{`Decidida pelo Presidente em ${dataCurta(dados.decisao.decidida_em)}.`}</p>
                {dados.decisao.justificativa && <p className="text-sm text-slate-700">{dados.decisao.justificativa}</p>}
              </>
            ) : (
              <p className="text-sm text-slate-700">A Recomendação está com a Direção, à espera da decisão sobre a medida.</p>
            )}
            {dados.comunicacoes.length > 0 && (
              <button type="button" className={BOTAO_CLARO} onClick={() => void abrirCopia()}>
                ABRIR A CÓPIA DA COMUNICAÇÃO DA MEDIDA
              </button>
            )}
          </section>
        )
      ) : (
        <p className="text-sm text-slate-600">Caso improcedente ou inconclusivo: não vai à Direção.</p>
      )}

      {correcoes && (
        <section aria-label="Correção de processo" className={`${CARTAO} px-4 py-4 space-y-3`}>
          <h2 className="text-base font-semibold text-slate-900">Correção de processo</h2>
          {correcoes.escolhidas.length > 0 && (
            <ul className="space-y-2">
              {correcoes.escolhidas.map((c) => (
                <li key={`${c.texto}-${c.escolhida_em}`} className="space-y-0.5">
                  <p className="text-sm text-slate-900">{c.texto}</p>
                  <p className="text-xs text-slate-600">{`Responsável: ${c.responsavel}. Prazo: ${dataCurta(c.prazo_em)}.`}</p>
                </li>
              ))}
            </ul>
          )}
          {correcoes.pode_escolher && (
            <>
              {correcoes.sugeridas.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase">Sugestão do agente</p>
                  {correcoes.sugeridas.map((s) => (
                    <button
                      key={s}
                      type="button"
                      aria-label={`ESCOLHER: ${s}`}
                      className="block w-full rounded-xl border border-border px-3 py-2 text-left text-sm text-slate-800 hover:border-[#282760]"
                      onClick={() => setCorrecao(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-2">
                <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("correcoes/sugestao")}>
                  SUGERIR CORREÇÕES
                </button>
                {correcao === null && (
                  <button type="button" className={BOTAO_CLARO} onClick={() => setCorrecao("")}>
                    ESCREVER CORREÇÃO
                  </button>
                )}
              </div>
              {correcao !== null && (
                <form
                  aria-label="Escolher a correção de processo"
                  className="space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void gravarCorrecao();
                  }}
                >
                  <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                    <span>Correção</span>
                    <textarea className={CAMPO} rows={2} value={correcao} onChange={(e) => setCorrecao(e.target.value)} />
                  </label>
                  <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                    <span>Responsável</span>
                    <input className={CAMPO} value={responsavel} maxLength={200} onChange={(e) => setResponsavel(e.target.value)} />
                  </label>
                  <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                    <span>Prazo</span>
                    <input type="date" className={CAMPO} value={prazo} onChange={(e) => setPrazo(e.target.value)} />
                  </label>
                  <button type="submit" className={BOTAO} disabled={ocupado || !correcao.trim() || !responsavel.trim() || !prazo}>
                    GRAVAR CORREÇÃO
                  </button>
                </form>
              )}
            </>
          )}
        </section>
      )}

      {(retorno.versoes.length > 0 || retorno.em_aberto) && (
        <section aria-label="Retorno" className={`${CARTAO} px-4 py-4 space-y-3`}>
          <h2 className="text-base font-semibold text-slate-900">Retorno</h2>
          {retorno.aprovado ? (
            <p className="text-sm text-emerald-800">
              {`Aprovado por ${retorno.aprovado.aprovado_por} em ${dataCurta(retorno.aprovado.aprovado_em)}. A resposta está na página de acompanhamento de quem relatou.`}
            </p>
          ) : (
            <p className="text-sm text-slate-600">Nada sai antes da aprovação da coordenação.</p>
          )}
          {ultima && !revisando && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">
                {`Versão ${ultima.versao}, ${ultima.origem === "agente" ? "redigida pelo agente" : `revisada por ${ultima.autor}`}.`}
              </p>
              <p className="text-xs font-semibold text-slate-500 uppercase">Resposta a quem relatou</p>
              <p className="text-sm text-slate-800 whitespace-pre-line">{ultima.denunciante}</p>
              <p className="text-xs font-semibold text-slate-500 uppercase">Comunicação ao acusado</p>
              <p className="text-sm text-slate-800 whitespace-pre-line">{ultima.acusado}</p>
            </div>
          )}
          {revisando && (
            <form
              aria-label="Revisar o retorno"
              className="space-y-2"
              onSubmit={(e) => {
                e.preventDefault();
                void salvarVersao();
              }}
            >
              <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                <span>Resposta a quem relatou</span>
                <textarea className={CAMPO} rows={4} value={denunciante} onChange={(e) => setDenunciante(e.target.value)} />
              </label>
              <p className="text-xs text-slate-500">Não cite a medida nem nome de ninguém.</p>
              <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                <span>Comunicação ao acusado</span>
                <textarea className={CAMPO} rows={5} value={acusado} onChange={(e) => setAcusado(e.target.value)} />
              </label>
              <p className="text-xs text-slate-500">Não cite quem relatou.</p>
              <div className="flex flex-col sm:flex-row gap-2">
                <button type="submit" className={BOTAO} disabled={ocupado}>
                  SALVAR VERSÃO
                </button>
                <button type="button" className={BOTAO_CLARO} onClick={() => setRevisando(false)}>
                  CANCELAR
                </button>
              </div>
            </form>
          )}
          {retorno.pode_redigir && !revisando && (
            <div className="flex flex-col sm:flex-row gap-2">
              <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("retorno")}>
                GERAR RETORNO
              </button>
              {ultima && (
                <button
                  type="button"
                  className={BOTAO_CLARO}
                  onClick={() => {
                    setDenunciante(ultima.denunciante);
                    setAcusado(ultima.acusado);
                    setRevisando(true);
                  }}
                >
                  REVISAR O RETORNO
                </button>
              )}
              <button type="button" className={BOTAO} disabled={ocupado || !retorno.pode_aprovar} onClick={() => void agir("retorno/aprovacao")}>
                APROVAR RETORNO
              </button>
            </div>
          )}
          {retorno.pode_redigir && retorno.bloqueio_da_aprovacao && (
            <p className="text-xs text-slate-600">{retorno.bloqueio_da_aprovacao}</p>
          )}
          {retorno.aprovado && (
            <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void abrirComunicacao()}>
              ABRIR COMUNICAÇÃO AO ACUSADO
            </button>
          )}
          {comunicacao && (
            <div aria-label="Comunicação ao acusado aprovada" className="rounded-xl border border-border bg-slate-50 px-3 py-2">
              <p className="text-sm text-slate-800 whitespace-pre-line">{comunicacao}</p>
            </div>
          )}
        </section>
      )}

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </div>
  );
}
