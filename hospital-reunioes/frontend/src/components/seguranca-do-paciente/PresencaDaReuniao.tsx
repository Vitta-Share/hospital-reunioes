"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import { createClient } from "@/lib/supabase/client";

export type SituacaoDePresenca = "presente" | "ausente" | "ausente_justificado" | "convidado";

export interface PessoaDaPresenca {
  participante_id: string;
  nome: string | null;
  papel: string | null;
  conta_para_quorum: boolean;
  situacao: SituacaoDePresenca | null;
}

export interface Quorum {
  total: number;
  presentes: number;
  minimo: number;
  presidencia_ou_suplente: boolean;
  instalada: boolean;
}

export interface Apuracao {
  id_reuniao: string;
  data: string;
  status_ata: string;
  pessoas: PessoaDaPresenca[];
  quorum: Quorum;
  pode_registrar: boolean;
}

interface PessoaDoCadastro {
  id: string;
  nome: string;
}

const SITUACOES: [SituacaoDePresenca, string][] = [
  ["presente", "Presente"],
  ["ausente", "Ausente"],
  ["ausente_justificado", "Ausente justificado"],
  ["convidado", "Convidado"],
];
const ROTULO = Object.fromEntries(SITUACOES) as Record<SituacaoDePresenca, string>;

const PAPEL: Record<string, string> = { presidencia: "Presidência", suplente: "Suplente", membro: "Membro" };

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

function resumo(q: Quorum): string {
  const conta = `${q.presentes} presentes de ${q.total}, mínimo de ${q.minimo}.`;
  return q.instalada ? `Reunião instalada: ${conta}` : `Sem quórum: ${conta}`;
}

/**
 * A presença e o quórum de uma reunião do Núcleo (issue #1774).
 *
 * A Presidência marca, para cada pessoa, presente, ausente, ausente justificado
 * ou convidado, e acrescenta convidados de fora do Núcleo. O quórum vem do
 * servidor, que sabe quem contava para quórum no dia da reunião. Sem quórum,
 * a tela pede a nova data e registra a reunião como não instalada.
 */
export function PresencaDaReuniao({ idReuniao, onMudou }: { idReuniao: string; onMudou?: () => void }) {
  const rota = `/api/nsp/reunioes/${idReuniao}/presenca`;
  const [apuracao, setApuracao] = useState<Apuracao | null>(null);
  const [pessoas, setPessoas] = useState<PessoaDaPresenca[]>([]);
  const [cadastro, setCadastro] = useState<PessoaDoCadastro[]>([]);
  const [convidado, setConvidado] = useState("");
  const [novaData, setNovaData] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const aplicar = useCallback((corpo: Apuracao) => {
    setApuracao(corpo);
    setPessoas(corpo.pessoas);
  }, []);

  useEffect(() => {
    (async () => {
      const tk = await token();
      const res = await fetch(rota, { headers: { Authorization: `Bearer ${tk}` } });
      if (!res.ok) {
        setErro("Não consegui carregar a presença da reunião.");
        return;
      }
      const corpo: Apuracao = await res.json();
      aplicar(corpo);
      if (corpo.pode_registrar) {
        const lista = await fetch("/api/nsp/membros/pessoas", { headers: { Authorization: `Bearer ${tk}` } });
        if (lista.ok) setCadastro((await lista.json()).pessoas ?? []);
      }
    })();
  }, [rota, aplicar]);

  function marcar(id: string, valor: string) {
    setPessoas((atual) =>
      atual.map((p) => (p.participante_id === id ? { ...p, situacao: (valor || null) as SituacaoDePresenca | null } : p)),
    );
  }

  function acrescentar() {
    const pessoa = cadastro.find((p) => p.id === convidado);
    if (!pessoa) return;
    setPessoas((atual) => [
      ...atual,
      { participante_id: pessoa.id, nome: pessoa.nome, papel: null, conta_para_quorum: false, situacao: "convidado" },
    ]);
    setConvidado("");
  }

  async function salvar() {
    setSalvando(true);
    setErro(null);
    const tk = await token();
    const presencas = pessoas
      .filter((p) => p.situacao)
      .map((p) => ({ participante_id: p.participante_id, situacao: p.situacao }));
    const res = await fetch(rota, {
      method: "PUT",
      headers: { Authorization: `Bearer ${tk}`, "Content-Type": "application/json" },
      body: JSON.stringify({ presencas }),
    });
    setSalvando(false);
    if (!res.ok) {
      setErro("Não consegui salvar a presença.");
      return;
    }
    aplicar(await res.json());
  }

  async function reagendar(e: FormEvent) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    const tk = await token();
    const res = await fetch(`/api/nsp/reunioes/${idReuniao}/nao-instalada`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tk}`, "Content-Type": "application/json" },
      body: JSON.stringify({ data: novaData, hora_inicio: null }),
    });
    setSalvando(false);
    if (!res.ok) {
      setErro("Não consegui reagendar. A nova data tem que ser depois da reunião.");
      return;
    }
    onMudou?.();
  }

  if (!apuracao) {
    return erro ? <p className="text-sm text-red-700">{erro}</p> : null;
  }

  const { quorum, pode_registrar: podeRegistrar } = apuracao;
  const listados = new Set(pessoas.map((p) => p.participante_id));
  const registrada = apuracao.pessoas.some((p) => p.situacao);

  return (
    <div className="space-y-3 border-t border-border pt-3">
      <ul className="space-y-2">
        {pessoas.map((p) => {
          const nome = p.nome ?? p.participante_id;
          return (
            <li key={p.participante_id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="min-w-0">
                <span className="block text-sm text-slate-900">{nome}</span>
                <span className="block text-xs text-slate-500">
                  {p.papel ? PAPEL[p.papel] ?? p.papel : "De fora do Núcleo"}
                  {p.conta_para_quorum ? "" : ", não conta para quórum"}
                </span>
              </span>
              {podeRegistrar ? (
                <select
                  aria-label={`Presença de ${nome}`}
                  value={p.situacao ?? ""}
                  onChange={(e) => marcar(p.participante_id, e.target.value)}
                  className="rounded-lg border border-border px-2 py-1.5 text-sm bg-white"
                >
                  <option value="">Sem registro</option>
                  {SITUACOES.map(([valor, rotulo]) => (
                    <option key={valor} value={valor}>
                      {rotulo}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-sm text-slate-700">{p.situacao ? ROTULO[p.situacao] : "Sem registro"}</span>
              )}
            </li>
          );
        })}
      </ul>

      {podeRegistrar && (
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Acrescentar convidado"
            value={convidado}
            onChange={(e) => setConvidado(e.target.value)}
            className="rounded-lg border border-border px-2 py-1.5 text-sm bg-white"
          >
            <option value="">Escolha a pessoa</option>
            {cadastro
              .filter((c) => !listados.has(c.id))
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
          </select>
          <button
            type="button"
            onClick={acrescentar}
            disabled={!convidado}
            className="rounded-xl border border-border text-sm px-3 py-1.5 disabled:opacity-60"
          >
            Acrescentar
          </button>
          <button
            type="button"
            onClick={salvar}
            disabled={salvando}
            className="rounded-xl bg-[#282760] text-white text-sm font-semibold px-4 py-2 disabled:opacity-60"
          >
            Salvar presença
          </button>
        </div>
      )}

      <p className={`text-sm font-semibold ${quorum.instalada ? "text-emerald-700" : "text-orange-700"}`}>
        {resumo(quorum)}
      </p>
      {!quorum.presidencia_ou_suplente && (
        <p className="text-sm text-orange-700">Falta a Presidência ou o suplente presente.</p>
      )}

      {podeRegistrar && registrada && !quorum.instalada && (
        <form onSubmit={reagendar} aria-label="Reagendar a reunião" className="flex flex-wrap items-end gap-2">
          <label className="block text-sm text-slate-700">
            Nova data
            <input
              required
              type="date"
              value={novaData}
              onChange={(e) => setNovaData(e.target.value)}
              className="mt-1 block rounded-lg border border-border px-3 py-2 text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={salvando}
            className="rounded-xl bg-orange-600 text-white text-sm font-semibold px-4 py-2.5 disabled:opacity-60"
          >
            Registrar como não instalada e reagendar
          </button>
        </form>
      )}

      {erro && <p className="text-sm text-red-700">{erro}</p>}
    </div>
  );
}
