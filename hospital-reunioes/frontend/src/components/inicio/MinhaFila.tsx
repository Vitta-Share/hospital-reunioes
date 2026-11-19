"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

import { createClient } from "@/lib/supabase/client";

export type GrupoDoInicio = "passou_do_prazo" | "ate_48_horas" | "proximos_7_dias";

/** Um item da Minha Fila, no formato comum de toda fonte (ADR 0104). */
export interface ItemDoInicio {
  tipo: string;
  id: string;
  titulo: string;
  origem: string;
  prazo: string | null;
  chegou_em: string | null;
  area: string;
  acao: string;
  destino: string;
  acao_de_um_clique: { rotulo: string; endpoint: string } | null;
  grupo: GrupoDoInicio | null;
  dias_de_atraso: number | null;
}

export interface InicioDaPessoa {
  hoje: string;
  frase: { titulo: string; apoio: string };
  contadores: Record<GrupoDoInicio, number>;
  itens: ItemDoInicio[];
  avisos: { fonte: string; mensagem: string }[];
  trilho: unknown[];
  filas_do_papel: unknown[];
}

const GRUPOS: { chave: GrupoDoInicio; titulo: string }[] = [
  { chave: "passou_do_prazo", titulo: "Passou do prazo" },
  { chave: "ate_48_horas", titulo: "Vence em até 48 horas" },
  { chave: "proximos_7_dias", titulo: "Próximos 7 dias" },
];

const DIAS_DA_SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

// Vermelho só em texto (ADR 0104, decisão 8): nada de fundo nem borda.
const VERMELHO = "text-red-700";

/** "2026-11-20" vira ["sex", "20/11"], sem passar por fuso. */
function diaDaSemanaEData(iso: string): [string, string] {
  const [ano, mes, dia] = iso.slice(0, 10).split("-").map(Number);
  const data = new Date(ano, mes - 1, dia);
  return [DIAS_DA_SEMANA[data.getDay()], `${String(dia).padStart(2, "0")}/${String(mes).padStart(2, "0")}`];
}

function dataPorExtenso(iso: string): string {
  const [ano, mes, dia] = iso.slice(0, 10).split("-").map(Number);
  return new Date(ano, mes - 1, dia).toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function Quando({ item, hoje }: { item: ItemDoInicio; hoje: string }) {
  if (item.grupo === "passou_do_prazo" && item.dias_de_atraso) {
    return (
      <div className={`leading-tight ${VERMELHO}`}>
        <span className="block text-3xl tabular-nums">{item.dias_de_atraso}</span>
        <span className="block text-xs mt-0.5">
          {item.dias_de_atraso === 1 ? "dia de atraso" : "dias de atraso"}
        </span>
      </div>
    );
  }
  const data = item.prazo ?? item.chegou_em;
  if (!data) return <div />;
  const [semana, diaEMes] = diaDaSemanaEData(data);
  return (
    <div className="leading-tight text-text">
      <span className="block text-xl">{data.slice(0, 10) === hoje ? "Hoje" : semana}</span>
      <span className="block text-xs mt-0.5 text-text-secondary">{diaEMes}</span>
    </div>
  );
}

function Linha({ item, hoje }: { item: ItemDoInicio; hoje: string }) {
  return (
    <li className="grid grid-cols-[88px_minmax(0,1fr)] sm:grid-cols-[104px_minmax(0,1fr)_auto] gap-4 items-center py-3.5 px-2 border-b border-border">
      <Quando item={item} hoje={hoje} />
      <div className="min-w-0">
        <p className="text-base text-text leading-snug">{item.titulo}</p>
        <p className="text-xs text-text-secondary mt-1">{item.origem}</p>
      </div>
      <div className="col-start-2 sm:col-start-auto flex sm:flex-col items-center sm:items-end justify-between gap-2">
        <span className="etiqueta text-[11px] text-text-secondary bg-slate-100 rounded-full px-2.5 py-0.5 whitespace-nowrap">
          {item.area}
        </span>
        <Link
          href={item.destino}
          className={`uppercase tracking-wide text-xs whitespace-nowrap rounded-lg px-3.5 py-2 border border-primary ${
            item.grupo === "passou_do_prazo" ? "bg-primary text-white" : "bg-white text-primary"
          }`}
        >
          {item.acao}
        </Link>
      </div>
    </li>
  );
}

/**
 * O Início de quem está olhando (issue #1934, ADR 0104): a frase do topo, os
 * três contadores e a Minha Fila em três grupos, do prazo mais vencido para o
 * mais distante. Grupo, atraso e frase vêm prontos do servidor.
 */
export function MinhaFila() {
  const [inicio, setInicio] = useState<InicioDaPessoa | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const {
          data: { session },
        } = await createClient().auth.getSession();
        const res = await fetch("/api/inicio", {
          headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
        });
        if (!res.ok) throw new Error(String(res.status));
        const corpo = (await res.json()) as InicioDaPessoa;
        if (vivo) setInicio(corpo);
      } catch {
        if (vivo) setFalhou(true);
      }
    })();
    return () => {
      vivo = false;
    };
  }, []);

  if (falhou) {
    return (
      <p role="alert" className="p-6 text-sm text-text-secondary">
        Não foi possível abrir o seu Início agora. Tente de novo em instantes.
      </p>
    );
  }
  if (!inicio) {
    return (
      <p className="p-6 flex items-center gap-2 text-sm text-text-secondary">
        <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
        Carregando o seu Início
      </p>
    );
  }

  const vencidos = inicio.contadores.passou_do_prazo;
  const grupos = GRUPOS.map((g) => ({ ...g, itens: inicio.itens.filter((i) => i.grupo === g.chave) })).filter(
    (g) => g.itens.length > 0
  );
  const contadores: [number, string][] = [
    [vencidos, vencidos === 1 ? "prazo vencido" : "prazos vencidos"],
    [inicio.contadores.ate_48_horas, inicio.contadores.ate_48_horas === 1 ? "vence em até 48 horas" : "vencem em até 48 horas"],
    [inicio.contadores.proximos_7_dias, "nos próximos 7 dias"],
  ];

  return (
    <div className="bg-white rounded-2xl border border-border overflow-hidden">
      <section
        data-testid="abertura"
        className={`px-6 sm:px-8 pt-7 pb-6 ${vencidos > 0 ? "bg-primary-dark text-white" : "bg-white text-text"}`}
      >
        <div className="flex flex-wrap justify-between gap-4 text-xs opacity-80">
          <h1 className="text-xs">Início</h1>
          <span>{dataPorExtenso(inicio.hoje)}</span>
        </div>
        <p className="mt-4 text-3xl sm:text-4xl leading-tight max-w-[22ch]">{inicio.frase.titulo}</p>
        <p className="mt-2.5 text-base max-w-[52ch] opacity-85">{inicio.frase.apoio}</p>
        <ul aria-label="Resumo dos prazos" className="mt-5 flex flex-wrap gap-2">
          {contadores.map(([numero, rotulo]) => (
            <li
              key={rotulo}
              className="inline-flex items-baseline gap-2 rounded-lg border border-current px-3.5 py-2 text-xs"
            >
              <b className="font-normal text-xl tabular-nums">{numero}</b>
              <span className="etiqueta">{rotulo}</span>
            </li>
          ))}
        </ul>
      </section>

      <div className="px-4 sm:px-8 py-7 space-y-8">
        {inicio.avisos.map((aviso) => (
          <p key={aviso.fonte} role="status" className="text-sm text-text-secondary">
            {aviso.mensagem}
          </p>
        ))}

        {grupos.length === 0 ? (
          <p className="text-base text-text">Nada vencido e nada para os próximos 7 dias.</p>
        ) : (
          grupos.map((grupo) => (
            <section key={grupo.chave} aria-label={grupo.titulo}>
              <h2
                className={`flex items-baseline gap-2.5 pb-2 border-b border-border text-xs ${
                  grupo.chave === "passou_do_prazo" ? VERMELHO : "text-text-secondary"
                }`}
              >
                {grupo.titulo}
                <span className="tabular-nums">{grupo.itens.length}</span>
              </h2>
              <ul>
                {grupo.itens.map((item) => (
                  <Linha key={`${item.tipo}:${item.id}`} item={item} hoje={inicio.hoje} />
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
