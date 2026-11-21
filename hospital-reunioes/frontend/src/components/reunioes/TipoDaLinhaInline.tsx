"use client";

import { useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { createClient } from "@/lib/supabase/client";
import { getErrorMessage } from "@/lib/errors";

/** Ação, Rotina e Processo (issue #1872): o tipo de cada linha do quadro da Ata. */
export const TIPOS_DA_LINHA = [
  { valor: "ACAO", rotulo: "Ação" },
  { valor: "ROTINA", rotulo: "Rotina" },
  { valor: "PROCESSO", rotulo: "Processo" },
] as const;

export const FREQUENCIAS_DA_ROTINA = [
  { valor: "SEMANAL", rotulo: "Semanal" },
  { valor: "QUINZENAL", rotulo: "Quinzenal" },
  { valor: "MENSAL", rotulo: "Mensal" },
] as const;

/** Linha sem tipo (ou com tipo desconhecido) vale como Ação, como no backend. */
export function tipoDaLinha(tipo?: string | null): string {
  const valor = (tipo || "").toUpperCase();
  return TIPOS_DA_LINHA.some((t) => t.valor === valor) ? valor : "ACAO";
}

export function rotuloDoTipo(tipo?: string | null, frequencia?: string | null): string {
  const t = tipoDaLinha(tipo);
  const rotulo = TIPOS_DA_LINHA.find((x) => x.valor === t)?.rotulo ?? "Ação";
  if (t !== "ROTINA") return rotulo;
  const freq = FREQUENCIAS_DA_ROTINA.find((f) => f.valor === (frequencia || "").toUpperCase());
  return freq ? `${rotulo}, ${freq.rotulo.toLowerCase()}` : `${rotulo}, sem frequência`;
}

interface TipoDaLinhaInlineProps {
  reuniaoId: string;
  atribuicaoIndex: number;
  valorAtual: { tipo?: string | null; frequencia?: string | null };
  onAtualizado: (novo: { tipo: string; frequencia: string | null }) => void;
}

/** Os seletores de tipo e frequência de uma linha na validação da Ata. */
export function TipoDaLinhaInline({ reuniaoId, atribuicaoIndex, valorAtual, onAtualizado }: TipoDaLinhaInlineProps) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const tipo = tipoDaLinha(valorAtual.tipo);
  const linha = atribuicaoIndex + 1;

  async function persistir(payload: { tipo?: string; frequencia?: string | null }) {
    setLoading(true);
    try {
      const {
        data: { session },
      } = await createClient().auth.getSession();
      const res = await fetch(`/api/reunioes/${reuniaoId}/quadro-atribuicoes/${atribuicaoIndex}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : "Erro ao atualizar o tipo da linha");
      }
      const data = await res.json();
      onAtualizado({ tipo: tipoDaLinha(data?.tipo), frequencia: data?.frequencia ?? null });
    } catch (err) {
      toast(getErrorMessage(err) || "Erro ao atualizar o tipo da linha", "error");
    } finally {
      setLoading(false);
    }
  }

  const classe =
    "block w-full text-xs rounded-lg border border-slate-200 bg-white px-2 py-1 text-slate-700 disabled:opacity-60";

  return (
    <div className="space-y-1 min-w-[120px]" onClick={(e) => e.stopPropagation()}>
      <select
        aria-label={`Tipo da linha ${linha}`}
        className={classe}
        value={tipo}
        disabled={loading}
        onChange={(e) => void persistir({ tipo: e.target.value })}
      >
        {TIPOS_DA_LINHA.map((t) => (
          <option key={t.valor} value={t.valor}>
            {t.rotulo}
          </option>
        ))}
      </select>
      {tipo === "ROTINA" && (
        <select
          aria-label={`Frequência da linha ${linha}`}
          className={`${classe} ${valorAtual.frequencia ? "" : "border-amber-300 text-amber-800"}`}
          value={(valorAtual.frequencia || "").toUpperCase()}
          disabled={loading}
          onChange={(e) => void persistir({ frequencia: e.target.value || null })}
        >
          <option value="">Escolha a frequência</option>
          {FREQUENCIAS_DA_ROTINA.map((f) => (
            <option key={f.valor} value={f.valor}>
              {f.rotulo}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
