"use client";

import { useState } from "react";

import { chamarComite } from "@/lib/conduta/comite";
import { dataEHora } from "@/lib/conduta/depoimentos";
import { abrirRelatorioAssinado, type TextoDaApuracao, type TipoDoTexto } from "@/lib/conduta/relatorio";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 disabled:text-slate-600 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

const TITULOS: Record<TipoDoTexto, string> = { relatorio: "Relatório de apuração", cronologia: "Cronologia dos fatos" };
const BOTOES: Record<TipoDoTexto, string> = { relatorio: "GERAR RELATÓRIO", cronologia: "MONTAR CRONOLOGIA" };
const SITUACOES = { gerado: "Ainda não enviado à assinatura", enviado: "Aguardando a assinatura dos apuradores", assinado: "Assinado pelos apuradores" };

/** Um texto da apuração (relatório ou cronologia): o botão do agente, o texto, a edição e as versões. */
function Texto({
  casoId,
  tipo,
  documento,
  podeRedigir,
  ocupado,
  agir,
}: {
  casoId: string;
  tipo: TipoDoTexto;
  documento: TextoDaApuracao | null;
  podeRedigir: boolean;
  ocupado: boolean;
  agir: (caminho: string, body?: unknown) => Promise<boolean>;
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState("");

  return (
    <section aria-label={TITULOS[tipo]} className={`${CARTAO} px-4 py-4 space-y-3`}>
      <h2 className="text-base font-semibold text-slate-900">{TITULOS[tipo]}</h2>
      {documento ? (
        <>
          <p className="text-xs text-slate-500">{`Versão ${documento.versao}`}</p>
          {editando ? (
            <form
              aria-label={`Editar ${TITULOS[tipo].toLowerCase()}`}
              className="space-y-2"
              onSubmit={async (e) => {
                e.preventDefault();
                if (await agir(`${tipo}/versoes`, { texto })) setEditando(false);
              }}
            >
              <textarea
                className={CAMPO}
                rows={12}
                value={texto}
                maxLength={documento.limite}
                aria-label="Texto"
                onChange={(e) => setTexto(e.target.value)}
              />
              <p className="text-xs text-slate-500">{`${texto.length} de ${documento.limite} caracteres, uma página`}</p>
              <div className="flex flex-col sm:flex-row gap-2">
                <button type="submit" className={BOTAO} disabled={!texto.trim() || ocupado}>
                  SALVAR NOVA VERSÃO
                </button>
                <button type="button" className={BOTAO_CLARO} onClick={() => setEditando(false)}>
                  Cancelar
                </button>
              </div>
            </form>
          ) : (
            <p className="text-sm text-slate-800 whitespace-pre-line break-words">{documento.texto}</p>
          )}
          {podeRedigir && !editando && (
            <button
              type="button"
              className={BOTAO_CLARO}
              disabled={ocupado}
              onClick={() => {
                setTexto(documento.texto);
                setEditando(true);
              }}
            >
              EDITAR
            </button>
          )}
          <details className="text-sm text-slate-700">
            <summary className="cursor-pointer font-semibold text-[#282760]">{`Versões (${documento.versoes.length})`}</summary>
            <ol className="mt-2 space-y-2">
              {documento.versoes.map((v) => (
                <li key={v.versao} className="border-l-2 border-slate-200 pl-3">
                  <p className="text-xs text-slate-500">
                    {`Versão ${v.versao}, ${v.origem === "agente" ? "pelo agente" : "editada"}, por ${v.autor || "Não informado"}${
                      v.criado_em ? `, em ${dataEHora(v.criado_em)}` : ""
                    }`}
                  </p>
                  <p className="whitespace-pre-line break-words">{v.texto}</p>
                </li>
              ))}
            </ol>
          </details>
        </>
      ) : (
        <p className="text-sm text-slate-700">
          {tipo === "relatorio"
            ? "O agente redige o rascunho de uma página: fatos, provas, versão do acusado e a regra do Código. Nenhum nome vai ao agente."
            : "O agente monta a lista dos fatos em ordem de data. Nenhum nome vai ao agente."}
        </p>
      )}
      {podeRedigir && (
        <button type="button" className={documento ? BOTAO_CLARO : BOTAO} disabled={ocupado} onClick={() => void agir(tipo)}>
          {documento ? `${BOTOES[tipo]} DE NOVO` : BOTOES[tipo]}
        </button>
      )}
      {tipo === "relatorio" && documento && documento.assinatura !== undefined && (
        <Assinatura casoId={casoId} documento={documento} ocupado={ocupado} agir={agir} />
      )}
    </section>
  );
}

/** No rito Completo: o envio aos apuradores pela ClickSign e a cópia que volta. */
function Assinatura({
  casoId,
  documento,
  ocupado,
  agir,
}: {
  casoId: string;
  documento: TextoDaApuracao;
  ocupado: boolean;
  agir: (caminho: string, body?: unknown) => Promise<boolean>;
}) {
  const [aviso, setAviso] = useState<string | null>(null);
  const assinatura = documento.assinatura ?? null;
  return (
    <div className="space-y-2 border-t border-slate-100 pt-3">
      <p className="text-sm text-slate-800">
        {assinatura ? SITUACOES[assinatura.situacao] : "A última versão ainda não foi à assinatura dos apuradores."}
      </p>
      {assinatura?.erro && <p className="text-sm text-red-700">{assinatura.erro}</p>}
      {(!assinatura || assinatura.situacao === "gerado") && (
        <button type="button" className={BOTAO} disabled={ocupado} onClick={() => void agir("relatorio/assinatura")}>
          ENVIAR PARA ASSINATURA
        </button>
      )}
      {assinatura?.situacao === "enviado" && (
        <button type="button" className={BOTAO_CLARO} disabled={ocupado} onClick={() => void agir("relatorio/reconsulta")}>
          Reconsultar status
        </button>
      )}
      {assinatura?.tem_copia && (
        <button
          type="button"
          className={BOTAO_CLARO}
          onClick={async () => {
            setAviso(null);
            try {
              window.open(await abrirRelatorioAssinado(casoId), "_blank", "noopener");
            } catch (e) {
              setAviso((e as Error).message);
            }
          }}
        >
          ABRIR RELATÓRIO ASSINADO
        </button>
      )}
      {aviso && <p className="text-sm text-red-700">{aviso}</p>}
    </div>
  );
}

/**
 * O fim da Apuração (issue #1832; especificação, 6.3 e 6.4): o relatório de
 * uma página e a cronologia dos fatos, redigidos pelo agente num clique e
 * revisados por quem apurou. "ENVIAR PARA VOTO" fica na caixa "O QUE FAZER
 * AGORA", com o motivo quando está bloqueado.
 */
export function RelatorioDaApuracao({
  casoId,
  relatorio,
  cronologia,
  podeRedigir,
  aoMudar,
}: {
  casoId: string;
  relatorio: TextoDaApuracao | null;
  cronologia: TextoDaApuracao | null;
  podeRedigir: boolean;
  aoMudar: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  if (!relatorio && !cronologia && !podeRedigir) return null;

  const agir = async (caminho: string, body?: unknown): Promise<boolean> => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarComite(`/casos/${casoId}/${caminho}`, { method: "POST", body: body ?? {} });
      aoMudar();
      return true;
    } catch (e) {
      setAviso((e as Error).message);
      return false;
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-3">
      {ocupado && (
        <p role="status" className="text-sm text-slate-600">
          Aguarde, o pedido está em andamento.
        </p>
      )}
      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
      <Texto casoId={casoId} tipo="relatorio" documento={relatorio} podeRedigir={podeRedigir} ocupado={ocupado} agir={agir} />
      <Texto casoId={casoId} tipo="cronologia" documento={cronologia} podeRedigir={podeRedigir} ocupado={ocupado} agir={agir} />
    </div>
  );
}
