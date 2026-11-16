"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { CalendarDays, Lock, Plus } from "lucide-react";

import { createClient } from "@/lib/supabase/client";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const ROTA = "/api/nsp/reunioes";

export interface ReuniaoDoNucleo {
  id_reuniao: string;
  data: string;
  hora_inicio: string | null;
  tipo: string;
  titulo: string | null;
  status_ata: string | null;
}

interface Calendario {
  reunioes: ReuniaoDoNucleo[];
  tipos: string[];
  pode_abrir: boolean;
  pode_criar: boolean;
}

const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

/** "2026-11-20" vira "novembro de 2026", sem passar pelo fuso. */
function mesDe(iso: string): string {
  const [ano, mes] = iso.split("-");
  return `${MESES[Number(mes) - 1]} de ${ano}`;
}

/** "2026-11-20" vira "20/11". */
function diaDe(iso: string): string {
  const [, mes, dia] = iso.split("-");
  return `${dia}/${mes}`;
}

function porMes(reunioes: ReuniaoDoNucleo[]): [string, ReuniaoDoNucleo[]][] {
  const grupos = new Map<string, ReuniaoDoNucleo[]>();
  for (const r of reunioes) {
    const mes = mesDe(r.data);
    grupos.set(mes, [...(grupos.get(mes) ?? []), r]);
  }
  return [...grupos.entries()];
}

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

/**
 * O item Reuniões de Segurança do Paciente (issue #1772): o calendário das
 * reuniões do Núcleo, mês a mês, e a criação à mão pela Presidência.
 *
 * Quem decide é o servidor: a lista vem só para quem tem o calendário do
 * módulo, e a reunião só abre para quem tem as reuniões. O membro sem Termo vê
 * a data e o tipo, sem link para a ata.
 */
export function ReunioesDoNucleo() {
  const [calendario, setCalendario] = useState<Calendario | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [data, setData] = useState("");
  const [hora, setHora] = useState("");
  const [tipo, setTipo] = useState("");

  const carregar = useCallback(async () => {
    const tk = await token();
    if (!tk) {
      setErro("Sessão expirada. Entre de novo.");
      return;
    }
    const res = await fetch(ROTA, { headers: { Authorization: `Bearer ${tk}` } });
    if (!res.ok) {
      setErro("Não consegui carregar as reuniões do Núcleo.");
      return;
    }
    const corpo: Calendario = await res.json();
    setCalendario(corpo);
    setTipo((atual) => atual || corpo.tipos[0] || "");
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function criar(e: FormEvent) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    const tk = await token();
    const res = await fetch(ROTA, {
      method: "POST",
      headers: { Authorization: `Bearer ${tk}`, "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, data, tipo, hora_inicio: hora || null }),
    });
    setSalvando(false);
    if (!res.ok) {
      setErro("Não consegui criar a reunião. Confira o título, a data e o tipo.");
      return;
    }
    setCriando(false);
    setTitulo("");
    setData("");
    setHora("");
    await carregar();
  }

  if (!calendario) {
    return erro ? <p className="text-sm text-red-700">{erro}</p> : null;
  }

  return (
    <div className="space-y-5">
      {calendario.pode_criar && !criando && (
        <button
          type="button"
          onClick={() => setCriando(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-[#282760] text-white text-sm font-semibold px-4 py-2.5"
        >
          <Plus className="w-4 h-4" aria-hidden />
          Nova reunião
        </button>
      )}

      {criando && (
        <form onSubmit={criar} aria-label="Nova reunião do Núcleo" className={`${CARTAO} space-y-3 px-4 py-4`}>
          <label className="block text-sm text-slate-700">
            Título
            <input
              required
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm"
            />
          </label>
          <div className="flex flex-wrap gap-3">
            <label className="block text-sm text-slate-700">
              Data
              <input
                required
                type="date"
                value={data}
                onChange={(e) => setData(e.target.value)}
                className="mt-1 block rounded-lg border border-border px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm text-slate-700">
              Hora
              <input
                type="time"
                value={hora}
                onChange={(e) => setHora(e.target.value)}
                className="mt-1 block rounded-lg border border-border px-3 py-2 text-sm"
              />
            </label>
          </div>
          <label className="block text-sm text-slate-700">
            Tipo
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border px-3 py-2 text-sm bg-white"
            >
              {calendario.tipos.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={salvando}
              className="rounded-xl bg-[#282760] text-white text-sm font-semibold px-4 py-2.5 disabled:opacity-60"
            >
              Criar reunião
            </button>
            <button
              type="button"
              onClick={() => setCriando(false)}
              className="rounded-xl border border-border text-sm px-4 py-2.5"
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      {erro && <p className="text-sm text-red-700">{erro}</p>}

      {!calendario.pode_abrir && calendario.reunioes.length > 0 && (
        <p className="flex items-center gap-2 text-sm text-slate-600">
          <Lock className="w-4 h-4 shrink-0 text-slate-400" aria-hidden />
          A ata abre depois que você assina o Termo de Adesão.
        </p>
      )}

      {calendario.reunioes.length === 0 ? (
        <div className={`${CARTAO} flex flex-col items-center text-center gap-2 px-4 py-10`}>
          <CalendarDays className="w-8 h-8 text-slate-300" aria-hidden />
          <p className="text-sm font-semibold text-slate-900">Nenhuma reunião do Núcleo marcada.</p>
        </div>
      ) : (
        porMes(calendario.reunioes).map(([mes, reunioes]) => (
          <section key={mes} aria-label={mes}>
            <h2 className="text-sm font-semibold text-slate-500 mb-2 first-letter:uppercase">{mes}</h2>
            <ul className="space-y-2">
              {reunioes.map((r) => {
                const miolo = (
                  <>
                    <span className="shrink-0 w-12 text-sm font-bold text-[#282760]">{diaDe(r.data)}</span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-slate-900 truncate">{r.titulo}</span>
                      <span className="block text-xs text-slate-500">
                        {r.tipo}
                        {r.hora_inicio ? `, ${r.hora_inicio.slice(0, 5)}` : ""}
                      </span>
                    </span>
                  </>
                );
                return (
                  <li key={r.id_reuniao}>
                    {calendario.pode_abrir ? (
                      <Link href={`/reunioes/${r.id_reuniao}`} className={`${CARTAO} flex gap-3 items-center px-4 py-3`}>
                        {miolo}
                      </Link>
                    ) : (
                      <div className={`${CARTAO} flex gap-3 items-center px-4 py-3`}>{miolo}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
