"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2, Lock } from "lucide-react";

import { chamarNsp } from "@/lib/seguranca-do-paciente/membros";
import {
  descreverPrazo,
  formatarDataHora,
  type CelulaInterna,
  type TabelaDePrazos as Tabela,
} from "@/lib/seguranca-do-paciente/prazos";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO =
  "rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30";
const ROTA = "/api/nsp/configuracao/prazos";

function nomeDaCelula(celula: { faixa: string; rotulo: string }): string {
  return `Faixa ${celula.faixa}, ${celula.rotulo}`;
}

/** Uma célula interna editável: o número, a unidade e o botão de salvar. */
function CelulaEditavel({
  celula,
  unidades,
  aoSalvar,
}: {
  celula: CelulaInterna;
  unidades: Tabela["unidades"];
  aoSalvar: (celula: CelulaInterna, valor: number | null, unidade: string | null) => Promise<void>;
}) {
  const [valor, setValor] = useState(celula.valor === null ? "" : String(celula.valor));
  const [unidade, setUnidade] = useState(celula.unidade ?? "");
  const [salvando, setSalvando] = useState(false);
  const nome = nomeDaCelula(celula);

  async function salvar() {
    setSalvando(true);
    try {
      const semPrazo = unidade === "" || valor === "";
      await aoSalvar(celula, semPrazo ? null : Number(valor), semPrazo ? null : unidade);
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="number"
        min={1}
        aria-label={nome}
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        className={`${CAMPO} w-20 tabular-nums`}
      />
      <select
        aria-label={`Unidade, ${nome}`}
        value={unidade}
        onChange={(e) => setUnidade(e.target.value)}
        className={CAMPO}
      >
        <option value="">sem prazo próprio</option>
        {unidades.map((u) => (
          <option key={u.valor} value={u.valor}>
            {u.rotulo}
          </option>
        ))}
      </select>
      <button
        type="button"
        aria-label={`Salvar ${nome}`}
        onClick={salvar}
        disabled={salvando}
        className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
      >
        {salvando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
        Salvar
      </button>
    </div>
  );
}

/**
 * A tabela de prazos do Núcleo na Configuração (issue #1993, ADR 0107
 * decisão 2). Os prazos internos do art. 26 se editam pela Presidência e pelo
 * Acesso pleno; os legais vêm da norma e aparecem só para leitura. A mudança
 * vale para os casos confirmados depois dela, e cada uma fica no histórico.
 */
export function TabelaDePrazos() {
  const [tabela, setTabela] = useState<Tabela | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvo, setSalvo] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      setTabela(await chamarNsp<Tabela>(ROTA));
    } catch (e) {
      setErro((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (tabela === null) {
    return erro ? (
      <div role="alert" className={`${CARTAO} flex gap-2 items-start px-4 py-4`}>
        <AlertCircle className="w-5 h-5 shrink-0 text-red-500" aria-hidden />
        <p className="text-sm text-red-700">{erro}</p>
      </div>
    ) : (
      <Loader2 className="w-5 h-5 animate-spin text-slate-400" aria-label="Carregando" />
    );
  }

  async function salvar(celula: CelulaInterna, valor: number | null, unidade: string | null) {
    setErro(null);
    setSalvo(null);
    try {
      await chamarNsp(`${ROTA}/${encodeURIComponent(celula.faixa)}/${encodeURIComponent(celula.marco)}`, {
        method: "PUT",
        body: { valor, unidade },
      });
      setSalvo("Prazo salvo. Vale para os casos confirmados daqui para a frente.");
      await carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  }

  const marcos = Array.from(new Set(tabela.internos.map((c) => c.marco)));

  return (
    <section aria-labelledby="prazos-titulo" className={`${CARTAO} px-4 py-4 space-y-4`}>
      <div className="space-y-1">
        <h2 id="prazos-titulo" className="text-base font-semibold text-slate-900">
          Tabela de prazos
        </h2>
        <p className="text-sm text-slate-600">
          Os prazos do art. 26 do Regimento, por faixa. Ao confirmar a triagem, o caso guarda os prazos do dia: mudar a
          tabela vale para os casos confirmados depois.
        </p>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-900">Prazos internos</h3>
        {marcos.map((marco) => {
          const celulas = tabela.internos.filter((c) => c.marco === marco);
          return (
            <div key={marco} className="space-y-2 rounded-xl border border-border px-3 py-3">
              <p className="text-sm font-semibold text-slate-800">{celulas[0].rotulo}</p>
              <ul className="space-y-2">
                {celulas.map((celula) => (
                  <li key={celula.faixa} className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="w-16 font-semibold text-slate-600">{`Faixa ${celula.faixa}`}</span>
                    {celula.editavel ? (
                      <CelulaEditavel
                        key={`${celula.valor}-${celula.unidade}`}
                        celula={celula}
                        unidades={tabela.unidades}
                        aoSalvar={salvar}
                      />
                    ) : (
                      <span className="text-slate-800">{descreverPrazo(celula)}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {erro && (
        <p role="alert" className="text-sm text-red-700">
          {erro}
        </p>
      )}
      {salvo && (
        <p role="status" className="text-sm text-emerald-700">
          {salvo}
        </p>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-900">Prazos legais</h3>
        {tabela.legais.map((linha) => (
          <section key={linha.marco} className="space-y-2 rounded-xl border border-border bg-slate-50 px-3 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-slate-800">{linha.rotulo}</p>
              <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                <Lock className="w-3.5 h-3.5" aria-hidden />
                Fixado pela norma, não se altera pela tela
              </span>
            </div>
            <ul className="space-y-1">
              {Object.entries(linha.celulas).map(([faixa, texto]) => (
                <li key={faixa} className="flex gap-3 text-sm">
                  <span className="w-16 shrink-0 font-semibold text-slate-600">{`Faixa ${faixa}`}</span>
                  <span className="text-slate-800">{texto}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-900">Histórico</h3>
        {tabela.historico.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma mudança na tabela até agora.</p>
        ) : (
          <ul className="space-y-1">
            {tabela.historico.map((r) => (
              <li key={`${r.quando}-${r.faixa}-${r.marco}`} className="text-sm text-slate-700">
                {`${formatarDataHora(r.quando)}, ${r.quem ?? "sem autor registrado"}: ${nomeDaCelula(r)}, de ${descreverPrazo(
                  r.de
                ).toLowerCase()} para ${descreverPrazo(r.para).toLowerCase()}.`}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
