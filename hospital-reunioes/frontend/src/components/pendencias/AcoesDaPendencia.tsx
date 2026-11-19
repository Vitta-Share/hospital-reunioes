"use client";

import { useCallback, useEffect, useState } from "react";
import { History, Loader2 } from "lucide-react";

import type { ComandoPendencia, EventoPendencia, HistoricoPendencia, Pendencia } from "@/types";

/**
 * As ações e o histórico da Pendência (issue #1862, ADR 0098, decisão 5).
 *
 * Toda ação pede uma anotação; repactuar e reabrir pedem também o prazo novo.
 * Os botões são os que o backend devolve em `acoes_permitidas`: quem age sai do
 * vínculo com a Pendência, e a regra mora no servidor.
 */

const ROTULO_DO_BOTAO: Record<ComandoPendencia, string> = {
  iniciar: "Iniciar",
  anotar: "Anotar",
  concluir: "Concluir",
  repactuar: "Repactuar",
  cancelar: "Cancelar pendência",
  reabrir: "Reabrir",
};

const ROTULO_DO_EVENTO: Record<EventoPendencia["comando"], string> = {
  iniciar: "Iniciou",
  anotar: "Anotou",
  concluir: "Concluiu",
  repactuar: "Repactuou",
  cancelar: "Cancelou",
  reabrir: "Reabriu",
  migracao: "Ajuste da migração",
};

const PEDE_PRAZO: ComandoPendencia[] = ["repactuar", "reabrir"];

function dataBr(iso?: string | null): string {
  if (!iso) return "";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

function quando(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface Props {
  idAcao: string;
  token: string | null;
  /** A ação que o arrasto no kanban sugeriu; abre o formulário se for permitida. */
  acaoInicial?: ComandoPendencia | null;
  onAtualizada: (pendencia: Pendencia) => void;
}

export function AcoesDaPendencia({ idAcao, token, acaoInicial, onAtualizada }: Props) {
  const [historico, setHistorico] = useState<HistoricoPendencia | null>(null);
  const [acao, setAcao] = useState<ComandoPendencia | null>(null);
  const [anotacao, setAnotacao] = useState("");
  const [prazo, setPrazo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    const res = await fetch(`/api/pendencias/${idAcao}/historico`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return setHistorico({ eventos: [], acoes_permitidas: [] });
    const dados = await res.json();
    setHistorico({ eventos: dados?.eventos ?? [], acoes_permitidas: dados?.acoes_permitidas ?? [] });
  }, [idAcao, token]);

  useEffect(() => {
    carregar().catch(() => setHistorico({ eventos: [], acoes_permitidas: [] }));
  }, [carregar]);

  useEffect(() => {
    if (acaoInicial && historico?.acoes_permitidas.includes(acaoInicial)) setAcao(acaoInicial);
  }, [acaoInicial, historico]);

  function abrir(comando: ComandoPendencia) {
    setAcao(comando);
    setAnotacao("");
    setPrazo("");
    setErro(null);
  }

  const pedePrazo = acao !== null && PEDE_PRAZO.includes(acao);
  const pronto = anotacao.trim().length > 0 && (!pedePrazo || prazo !== "");

  async function confirmar() {
    if (!acao || !pronto) return;
    setEnviando(true);
    setErro(null);
    try {
      const corpo: Record<string, string> = { comando: acao, anotacao: anotacao.trim() };
      if (pedePrazo) corpo.prazo = prazo;
      const res = await fetch(`/api/pendencias/${idAcao}/acoes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(corpo),
      });
      const dados = await res.json().catch(() => ({}));
      if (!res.ok) {
        setErro(typeof dados.detail === "string" ? dados.detail : "Não foi possível registrar a ação. Tente de novo.");
        return;
      }
      onAtualizada(dados as Pendencia);
      setAcao(null);
      await carregar();
    } catch {
      setErro("Sem conexão. Tente de novo.");
    } finally {
      setEnviando(false);
    }
  }

  if (!historico) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Loader2 className="w-4 h-4 animate-spin" /> Carregando o histórico...
      </div>
    );
  }

  return (
    <section className="space-y-4">
      {historico.acoes_permitidas.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {historico.acoes_permitidas.map((comando) => (
            <button
              key={comando}
              type="button"
              onClick={() => abrir(comando)}
              className={`px-3 py-1.5 rounded-lg text-sm font-semibold border transition-colors ${
                acao === comando
                  ? "bg-primary text-white border-primary"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {ROTULO_DO_BOTAO[comando]}
            </button>
          ))}
        </div>
      )}

      {acao && (
        <div className="p-4 rounded-xl border border-primary/30 bg-primary/5 space-y-3">
          <label className="block">
            <span className="text-xs font-semibold text-slate-600">Anotação (obrigatória)</span>
            <textarea
              value={anotacao}
              onChange={(e) => setAnotacao(e.target.value)}
              placeholder="Conte o que foi feito ou por que esta ação."
              className="mt-1 w-full min-h-[80px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </label>
          {pedePrazo && (
            <label className="block">
              <span className="text-xs font-semibold text-slate-600">Prazo novo</span>
              <input
                type="date"
                value={prazo}
                onChange={(e) => setPrazo(e.target.value)}
                className="mt-1 block rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary"
              />
            </label>
          )}
          {erro && <p className="text-sm text-red-600">{erro}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirmar}
              disabled={!pronto || enviando}
              className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {enviando ? "Registrando..." : "Confirmar"}
            </button>
            <button
              type="button"
              onClick={() => setAcao(null)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100"
            >
              Voltar
            </button>
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <History className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Histórico</span>
        </div>
        {historico.eventos.length === 0 ? (
          <p className="text-sm text-slate-400">Nenhuma ação registrada ainda.</p>
        ) : (
          <ol aria-label="Histórico da pendência" className="space-y-3">
            {historico.eventos.map((evento) => (
              <li key={evento.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-800">
                    {ROTULO_DO_EVENTO[evento.comando] ?? evento.comando}, por {evento.autor_nome}
                  </span>
                  <span className="text-[11px] text-slate-400">{quando(evento.criado_em)}</span>
                </div>
                {evento.prazo_depois && evento.prazo_depois !== evento.prazo_antes && (
                  <p className="text-xs text-slate-500 mt-1">Prazo novo: {dataBr(evento.prazo_depois)}</p>
                )}
                {evento.conta_atraso && <p className="text-xs text-red-600 mt-1">Depois do vencimento</p>}
                <p className="text-sm text-slate-600 mt-1 whitespace-pre-wrap break-words">{evento.anotacao}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
