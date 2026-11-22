"use client";

/**
 * O link pessoal das Pendências (issue #1878, ADR 0098, decisão 8).
 *
 * Quem nunca entrou no aplicativo chega aqui pelo link do e-mail de segunda,
 * sem senha: o token é a credencial e só alcança as Pendências em aberto da
 * pessoa dona dele. Ela pode iniciar, anotar, concluir e repactuar, sempre com
 * uma anotação. Os botões de cada Pendência são os que o backend devolve.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";

import { Logo } from "@/components/ui/Logo";

type Comando = "iniciar" | "anotar" | "concluir" | "repactuar";

interface MinhaPendencia {
  id_acao: string;
  descricao: string;
  reuniao: string;
  prazo: string | null;
  situacao: string;
  acoes: Comando[];
}

interface MinhasPendencias {
  pessoa: string;
  pendencias: MinhaPendencia[];
}

const ROTULO: Record<Comando, string> = {
  iniciar: "Iniciar",
  anotar: "Anotar",
  concluir: "Concluir",
  repactuar: "Repactuar",
};

const FEITO: Record<Comando, string> = {
  iniciar: "Pendência iniciada.",
  anotar: "Anotação registrada.",
  concluir: "Pendência concluída.",
  repactuar: "Prazo repactuado.",
};

const SITUACAO: Record<string, string> = {
  PENDENTE: "Pendente",
  EM_PROGRESSO: "Em progresso",
  ATRASADO: "Atrasada",
  REPACTUADA: "Repactuada",
};

function dataBr(iso: string | null): string {
  if (!iso) return "Sem prazo";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

async function detalhe(res: Response, padrao: string): Promise<string> {
  const corpo = await res.json().catch(() => ({}));
  return typeof corpo.detail === "string" ? corpo.detail : padrao;
}

function FormDaAcao({
  token,
  pendencia,
  comando,
  onFeito,
  onCancelar,
}: {
  token: string;
  pendencia: MinhaPendencia;
  comando: Comando;
  onFeito: (dados: MinhasPendencias) => void;
  onCancelar: () => void;
}) {
  const [anotacao, setAnotacao] = useState("");
  const [prazo, setPrazo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const pedePrazo = comando === "repactuar";
  const pronto = anotacao.trim().length > 0 && (!pedePrazo || prazo !== "");

  async function enviar() {
    setEnviando(true);
    setErro(null);
    try {
      const res = await fetch(
        `/api/minhas-pendencias/${encodeURIComponent(token)}/pendencias/${encodeURIComponent(pendencia.id_acao)}/acoes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ comando, anotacao: anotacao.trim(), prazo: pedePrazo ? prazo : null }),
        },
      );
      if (!res.ok) {
        setErro(await detalhe(res, "Não foi possível registrar. Tente novamente."));
        return;
      }
      onFeito((await res.json()) as MinhasPendencias);
    } catch {
      setErro("Não foi possível registrar. Tente novamente.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="mt-3 space-y-3 border-t border-border pt-3">
      <label className="block normal-case text-sm font-medium text-slate-700">
        Anotação (obrigatória)
        <textarea
          value={anotacao}
          onChange={(e) => setAnotacao(e.target.value)}
          rows={3}
          maxLength={5000}
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
        />
      </label>
      {pedePrazo && (
        <label className="block normal-case text-sm font-medium text-slate-700">
          Prazo novo
          <input
            type="date"
            value={prazo}
            onChange={(e) => setPrazo(e.target.value)}
            className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal"
          />
        </label>
      )}
      {erro && (
        <p role="alert" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {erro}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => void enviar()}
          disabled={!pronto || enviando}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {enviando && <Loader2 className="w-4 h-4 animate-spin" />}
          Confirmar: {ROTULO[comando]}
        </button>
        <button
          type="button"
          onClick={onCancelar}
          className="rounded-xl border border-slate-300 px-4 py-2 text-sm text-slate-600"
        >
          Voltar
        </button>
      </div>
    </div>
  );
}

export default function MinhasPendenciasPage() {
  const params = useParams();
  const token = params.token as string;

  const [dados, setDados] = useState<MinhasPendencias | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [aberta, setAberta] = useState<{ id: string; comando: Comando } | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const res = await fetch(`/api/minhas-pendencias/${encodeURIComponent(token)}`);
      if (!res.ok) {
        setErro(await detalhe(res, "Não foi possível abrir este link."));
        return;
      }
      setDados((await res.json()) as MinhasPendencias);
    } catch {
      setErro("Não foi possível abrir este link. Tente novamente.");
    } finally {
      setCarregando(false);
    }
  }, [token]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <main className="min-h-screen bg-bg">
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-4">
        <div className="flex items-center justify-center mb-2">
          <Logo variant="default" size="sm" />
        </div>

        {carregando ? (
          <div className="flex items-center justify-center gap-2 py-16 text-slate-500">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Carregando as suas pendências...</span>
          </div>
        ) : erro && !dados ? (
          <div className="bg-white rounded-2xl border border-border shadow-premium px-6 py-10 text-center space-y-3">
            <AlertCircle className="w-10 h-10 text-amber-500 mx-auto" />
            <p className="text-slate-700 font-medium">{erro}</p>
          </div>
        ) : dados ? (
          <>
            <div className="bg-white rounded-2xl border border-border shadow-premium px-6 py-5">
              <h1 className="text-xl font-bold text-slate-900">Minhas pendências</h1>
              <p className="text-sm text-slate-600 mt-1">
                Olá, <span className="normal-case font-semibold">{dados.pessoa}</span>. Estas são as suas
                pendências em aberto. Toda atualização pede uma anotação e fica registrada no histórico.
              </p>
              <p className="text-xs text-slate-400 mt-2">Este link é só seu. Não encaminhe o e-mail.</p>
            </div>

            {aviso && (
              <p
                role="status"
                className="flex items-center gap-2 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3"
              >
                <CheckCircle2 className="w-4 h-4" />
                {aviso}
              </p>
            )}

            {dados.pendencias.length === 0 ? (
              <div className="bg-white rounded-2xl border border-border px-6 py-10 text-center">
                <p className="text-slate-600">Você não tem pendências em aberto.</p>
              </div>
            ) : (
              <ul className="space-y-3">
                {dados.pendencias.map((p) => (
                  <li key={p.id_acao} className="bg-white rounded-2xl border border-border shadow-premium px-5 py-4">
                    <p className="text-sm font-semibold text-slate-900">{p.descricao}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {p.reuniao}. Prazo: {dataBr(p.prazo)}. {SITUACAO[p.situacao] ?? p.situacao}.
                    </p>
                    {aberta?.id === p.id_acao ? (
                      <FormDaAcao
                        token={token}
                        pendencia={p}
                        comando={aberta.comando}
                        onCancelar={() => setAberta(null)}
                        onFeito={(novos) => {
                          setAviso(FEITO[aberta.comando]);
                          setAberta(null);
                          setDados(novos);
                        }}
                      />
                    ) : (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {p.acoes.map((c) => (
                          <button
                            key={c}
                            type="button"
                            onClick={() => {
                              setAviso(null);
                              setAberta({ id: p.id_acao, comando: c });
                            }}
                            className="rounded-xl border border-primary/30 px-3 py-1.5 text-sm font-medium text-primary hover:bg-primary/5"
                          >
                            {ROTULO[c]}
                          </button>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : null}
      </div>
    </main>
  );
}
