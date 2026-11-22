"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";

import { dataCurta } from "@/components/conduta/MedidaERetorno";
import {
  DECISOES,
  abrirAtaDaRecomendacao,
  anexarComunicacaoDaMedida,
  chamarDirecao,
  type Decisao,
  type ListaDaDirecao,
  type Recomendacao,
} from "@/lib/conduta/direcao";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO = "w-full rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900";
const BOTAO =
  "inline-flex items-center justify-center rounded-xl bg-[#282760] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#1f1e4d] disabled:bg-slate-300 w-full sm:w-auto";
const BOTAO_CLARO =
  "inline-flex items-center justify-center rounded-xl border border-[#282760] bg-white px-4 py-2.5 text-sm font-semibold text-[#282760] disabled:opacity-50 w-full sm:w-auto";

function Falha({ texto }: { texto: string }) {
  return (
    <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
      <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
      <p className="text-sm text-red-700">{texto}</p>
    </div>
  );
}

/** Os casos que o Comitê enviou à Direção, só com os metadados (issue #1835). */
export function ListaDeRecomendacoes() {
  const [lista, setLista] = useState<ListaDaDirecao | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    chamarDirecao<ListaDaDirecao>("/recomendacoes")
      .then(setLista)
      .catch((e: Error) => setErro(e.message));
  }, []);

  if (erro) return <Falha texto={erro} />;
  if (lista === null) return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;
  if (lista.recomendacoes.length === 0) {
    return <p className="text-sm text-slate-600">Nenhuma Recomendação do Comitê foi enviada à Direção.</p>;
  }
  return (
    <ul className="space-y-2">
      {lista.recomendacoes.map((r) => (
        <li key={r.id}>
          <Link
            href={`/comite-de-conduta/recomendacoes/${r.id}`}
            className={`${CARTAO} flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 px-4 py-3 hover:border-[#282760]`}
          >
            <span className="text-sm font-semibold text-slate-900 tabular-nums">{r.protocolo}</span>
            <span className="text-xs text-slate-500">{`Enviada em ${dataCurta(r.enviado_a_direcao_em)}`}</span>
            <span className="text-xs font-semibold text-slate-700">{r.decisao ?? "Aguardando a decisão"}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/**
 * A Recomendação do Comitê de um caso (issue #1835; especificação, 6.8): a
 * página de conclusão e a ata assinada. O Presidente só lê; a diretoria
 * executiva registra a decisão dele sobre a medida e anexa a cópia da
 * comunicação. Cada leitura entra na trilha do caso.
 */
export function RecomendacaoDoComite({ casoId }: { casoId: string }) {
  const [pagina, setPagina] = useState<Recomendacao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [decisao, setDecisao] = useState<Decisao | "">("");
  const [justificativa, setJustificativa] = useState("");
  const [data, setData] = useState("");

  const carregar = useCallback(() => {
    chamarDirecao<Recomendacao>(`/recomendacoes/${casoId}`)
      .then((corpo) => {
        setPagina(corpo);
        setErro(null);
      })
      .catch((e: Error) => setErro(e.message));
  }, [casoId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  if (erro) return <Falha texto={erro} />;
  if (pagina === null) return <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />;

  const pedeJustificativa = DECISOES.find((d) => d.valor === decisao)?.justificativa ?? false;
  const pronta = decisao !== "" && data !== "" && (!pedeJustificativa || justificativa.trim() !== "");

  const registrar = async () => {
    setOcupado(true);
    setAviso(null);
    try {
      await chamarDirecao(`/recomendacoes/${casoId}/decisao`, {
        method: "POST",
        body: { decisao, justificativa: pedeJustificativa ? justificativa : "", decidida_em: data },
      });
      carregar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  const abrirAta = async () => {
    try {
      window.open(await abrirAtaDaRecomendacao(casoId), "_blank", "noopener");
    } catch (e) {
      setAviso((e as Error).message);
    }
  };

  const anexar = async (arquivo: File | undefined) => {
    if (!arquivo) return;
    setOcupado(true);
    setAviso(null);
    try {
      await anexarComunicacaoDaMedida(casoId, arquivo);
      carregar();
    } catch (e) {
      setAviso((e as Error).message);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <div className="space-y-5 min-w-0">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-900 tabular-nums">{pagina.protocolo}</h1>
        <p className="text-sm text-slate-600">
          {`Rito ${pagina.rito}${pagina.categoria ? `, ${pagina.categoria}` : ""}. Enviada à Direção em ${dataCurta(pagina.enviado_a_direcao_em)}.`}
        </p>
      </header>

      <section aria-label="Página de conclusão" className={`${CARTAO} px-4 py-4 space-y-3`}>
        <h2 className="text-base font-semibold text-slate-900">Conclusão do Comitê</h2>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <dt className="text-xs font-semibold text-slate-500 uppercase">Resultado</dt>
            <dd className="text-sm text-slate-900">{pagina.resultado}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold text-slate-500 uppercase">Medida recomendada</dt>
            <dd className="text-sm text-slate-900">{pagina.medida_recomendada ?? "Sem medida"}</dd>
          </div>
        </dl>
        {pagina.relatorio && <p className="text-sm text-slate-800 whitespace-pre-line">{pagina.relatorio}</p>}
        {pagina.tem_ata_assinada && (
          <button type="button" className={BOTAO_CLARO} onClick={() => void abrirAta()}>
            ABRIR A ATA ASSINADA
          </button>
        )}
      </section>

      <section aria-label="Decisão sobre a medida" className={`${CARTAO} px-4 py-4 space-y-3`}>
        <h2 className="text-base font-semibold text-slate-900">Decisão sobre a medida</h2>
        {pagina.decisao ? (
          <div className="space-y-1">
            <p className="text-sm font-semibold text-slate-900">{pagina.decisao.decisao}</p>
            <p className="text-xs text-slate-500">{`Decidida pelo Presidente em ${dataCurta(pagina.decisao.decidida_em)}.`}</p>
            {pagina.decisao.justificativa && <p className="text-sm text-slate-700">{pagina.decisao.justificativa}</p>}
          </div>
        ) : pagina.pode_registrar ? (
          <form
            aria-label="Registrar a decisão do Presidente"
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void registrar();
            }}
          >
            <fieldset className="space-y-1">
              <legend className="text-sm font-semibold text-slate-700">Decisão do Presidente</legend>
              {DECISOES.map((d) => (
                <label key={d.valor} className="flex items-center gap-2 text-sm text-slate-800">
                  <input type="radio" name="decisao" value={d.valor} checked={decisao === d.valor} onChange={() => setDecisao(d.valor)} />
                  {d.rotulo}
                </label>
              ))}
            </fieldset>
            <label className="text-sm font-semibold text-slate-700 space-y-1 block">
              <span>Data da decisão do Presidente</span>
              <input type="date" className={CAMPO} value={data} onChange={(e) => setData(e.target.value)} />
            </label>
            {pedeJustificativa && (
              <label className="text-sm font-semibold text-slate-700 space-y-1 block">
                <span>Justificativa</span>
                <textarea className={CAMPO} rows={3} maxLength={2000} value={justificativa} onChange={(e) => setJustificativa(e.target.value)} />
              </label>
            )}
            <button type="submit" className={BOTAO} disabled={!pronta || ocupado}>
              REGISTRAR DECISÃO
            </button>
          </form>
        ) : (
          <p className="text-sm text-slate-600">A decisão do Presidente ainda não foi registrada pela diretoria executiva.</p>
        )}
        {pagina.comunicacoes.length > 0 && (
          <p className="text-xs text-slate-500">{`Cópia da comunicação da medida anexada em ${dataCurta(pagina.comunicacoes[0].enviado_em)}.`}</p>
        )}
        {pagina.pode_anexar_comunicacao && (
          <label className={`${BOTAO_CLARO} cursor-pointer`}>
            ANEXAR A CÓPIA DA COMUNICAÇÃO DA MEDIDA
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              className="sr-only"
              disabled={ocupado}
              onChange={(e) => void anexar(e.target.files?.[0])}
            />
          </label>
        )}
      </section>

      {aviso && (
        <p role="alert" className="text-sm text-red-700">
          {aviso}
        </p>
      )}
    </div>
  );
}
