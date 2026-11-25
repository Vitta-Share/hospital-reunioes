"use client";

// PROTÓTIPO, descartável (integração Fireflies, ADR 0113 proposta).
// Três versões de como o Código da gravação aparece na Reunião agendada,
// trocadas por `?variant=` (A, B, C). O botão "Simular" faz de conta que o
// Fireflies terminou: nada vai ao backend, tudo fica na memória da tela.

import { useEffect, useState } from "react";
import { Check, Copy, Mail, Mic, Smartphone, Monitor, Sparkles, FileText, CalendarDays, Loader2 } from "lucide-react";
import { codigoDaGravacao } from "./codigoDaGravacao";
import { PrototypeSwitcher, useVersao, type Versao } from "@/components/prototype/PrototypeSwitcher";

export const VERSOES_DO_CODIGO: Versao[] = [
  { chave: "A", nome: "Cartão com passo a passo" },
  { chave: "B", nome: "Faixa no topo" },
  { chave: "C", nome: "Linha do tempo da gravação" },
];

type Etapa = "aguardando" | "chegou" | "pronta";

function useSimulacao() {
  const [etapa, setEtapa] = useState<Etapa>("aguardando");
  useEffect(() => {
    if (etapa !== "chegou") return;
    const t = setTimeout(() => setEtapa("pronta"), 2500);
    return () => clearTimeout(t);
  }, [etapa]);
  return { etapa, simular: () => setEtapa("chegou"), reiniciar: () => setEtapa("aguardando") };
}

function BotaoCopiar({ codigo, grande = false }: { codigo: string; grande?: boolean }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(codigo).catch(() => undefined);
        setCopiado(true);
        setTimeout(() => setCopiado(false), 1800);
      }}
      className={`inline-flex items-center gap-1.5 rounded-xl border border-primary/30 text-primary font-medium hover:bg-primary/5 transition-all ${grande ? "px-4 py-2.5 text-sm" : "px-3 py-1.5 text-xs"}`}
    >
      {copiado ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
      {copiado ? "Copiado" : "Copiar código"}
    </button>
  );
}

function Codigo({ codigo, tamanho }: { codigo: string; tamanho: "g" | "m" }) {
  return (
    <span className={`font-mono font-bold tracking-wider text-slate-900 ${tamanho === "g" ? "text-4xl" : "text-xl"}`}>
      {codigo}
    </span>
  );
}

function PreviaDoEmail({ titulo }: { titulo: string }) {
  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-[11px] uppercase tracking-wide text-slate-400 mb-2 flex items-center gap-1.5">
        <Mail className="w-3.5 h-3.5" /> Prévia do e-mail ao Facilitador
      </p>
      <p className="text-sm font-semibold text-slate-800">A Ata da reunião {titulo} está pronta para revisão</p>
      <p className="text-sm text-slate-600 mt-1">
        A gravação do Fireflies chegou e a Ata foi gerada. Revise e valide quando puder. A gravação já foi apagada do
        Fireflies.
      </p>
      <span className="inline-block mt-3 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-medium">Revisar a Ata</span>
    </div>
  );
}

function BotaoSimular({ etapa, simular, reiniciar }: ReturnType<typeof useSimulacao>) {
  if (etapa === "aguardando")
    return (
      <button
        onClick={simular}
        className="text-xs px-3 py-1.5 rounded-lg border border-dashed border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100"
      >
        Protótipo: simular que o Fireflies terminou a gravação
      </button>
    );
  return (
    <button onClick={reiniciar} className="text-xs px-3 py-1.5 rounded-lg border border-dashed border-slate-300 text-slate-500 hover:bg-slate-50">
      Protótipo: voltar ao começo
    </button>
  );
}

function Situacao({ etapa }: { etapa: Etapa }) {
  if (etapa === "aguardando")
    return (
      <p className="text-sm text-slate-500 flex items-center gap-2">
        <Mic className="w-4 h-4" /> Esperando a gravação. Assim que o Fireflies terminar, a Transcrição entra aqui sozinha.
      </p>
    );
  if (etapa === "chegou")
    return (
      <p className="text-sm text-indigo-700 flex items-center gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> A Transcrição chegou do Fireflies. A Ata está sendo gerada.
      </p>
    );
  return (
    <p className="text-sm text-emerald-700 flex items-center gap-2">
      <Check className="w-4 h-4" /> A Ata está pronta para revisão. O Facilitador recebeu o e-mail e o aviso no Início.
    </p>
  );
}

// ── Versão A: cartão com o código grande e os três passos ─────────────────
function VersaoA({ codigo, titulo }: { codigo: string; titulo: string }) {
  const sim = useSimulacao();
  return (
    <div className="bg-white rounded-2xl border-2 border-primary/20 shadow-premium">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2.5">
        <Mic className="w-4 h-4 text-primary" strokeWidth={1.5} />
        <h2 className="font-semibold text-slate-900">Gravar no Fireflies</h2>
      </div>
      <div className="px-6 py-5 space-y-5">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <p className="text-xs text-slate-500 mb-1">Código da gravação</p>
            <Codigo codigo={codigo} tamanho="g" />
          </div>
          <BotaoCopiar codigo={codigo} grande />
        </div>
        <ol className="space-y-2.5 text-sm text-slate-700">
          <li className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center flex-shrink-0">1</span>
            <span>
              Abra o Fireflies no celular <Smartphone className="inline w-3.5 h-3.5" /> ou no computador <Monitor className="inline w-3.5 h-3.5" /> e toque em gravar.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center flex-shrink-0">2</span>
            <span>
              Quando o Fireflies pedir o título, digite <span className="font-mono font-semibold">{codigo}</span>. Pode escrever mais coisa junto.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center flex-shrink-0">3</span>
            <span>Encerre a gravação. A Transcrição chega aqui sozinha e a Ata é gerada.</span>
          </li>
        </ol>
        <div className="pt-1 space-y-3">
          <Situacao etapa={sim.etapa} />
          <BotaoSimular {...sim} />
          {sim.etapa === "pronta" && <PreviaDoEmail titulo={titulo} />}
        </div>
      </div>
    </div>
  );
}

// ── Versão B: faixa fina no topo da página, sem cartão ────────────────────
function VersaoB({ codigo, titulo }: { codigo: string; titulo: string }) {
  const sim = useSimulacao();
  const cor =
    sim.etapa === "pronta" ? "bg-emerald-50 border-emerald-200" : sim.etapa === "chegou" ? "bg-indigo-50 border-indigo-200" : "bg-primary/5 border-primary/20";
  return (
    <div className={`rounded-2xl border px-5 py-3.5 ${cor}`}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Mic className="w-5 h-5 text-primary flex-shrink-0" />
        <p className="text-sm text-slate-700">
          No Fireflies, use o título <Codigo codigo={codigo} tamanho="m" />
        </p>
        <BotaoCopiar codigo={codigo} />
        <div className="ml-auto">
          <BotaoSimular {...sim} />
        </div>
      </div>
      {sim.etapa !== "aguardando" && (
        <div className="mt-2.5">
          <Situacao etapa={sim.etapa} />
          {sim.etapa === "pronta" && <PreviaDoEmail titulo={titulo} />}
        </div>
      )}
    </div>
  );
}

// ── Versão C: linha do tempo, com o código dentro do primeiro passo ───────
function VersaoC({ codigo, titulo }: { codigo: string; titulo: string }) {
  const sim = useSimulacao();
  const passos = [
    { icone: CalendarDays, nome: "Reunião agendada", feito: true },
    { icone: Mic, nome: "Gravação no Fireflies", feito: sim.etapa !== "aguardando" },
    { icone: FileText, nome: "Transcrição recebida", feito: sim.etapa !== "aguardando" },
    { icone: Sparkles, nome: "Ata pronta para revisão", feito: sim.etapa === "pronta" },
  ];
  return (
    <div className="bg-white rounded-2xl border border-border shadow-premium">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2.5">
        <Mic className="w-4 h-4 text-primary" strokeWidth={1.5} />
        <h2 className="font-semibold text-slate-900">Da gravação à Ata</h2>
      </div>
      <div className="px-6 py-5">
        <ol className="relative border-l-2 border-slate-100 ml-3 space-y-5">
          {passos.map((p, i) => (
            <li key={p.nome} className="ml-6">
              <span
                className={`absolute -left-[13px] w-6 h-6 rounded-full flex items-center justify-center ${p.feito ? "bg-emerald-500 text-white" : "bg-slate-100 text-slate-400"}`}
              >
                {p.feito ? <Check className="w-3.5 h-3.5" /> : <p.icone className="w-3.5 h-3.5" />}
              </span>
              <p className={`text-sm font-medium ${p.feito ? "text-slate-900" : "text-slate-500"}`}>{p.nome}</p>
              {i === 1 && (
                <div className="mt-2 rounded-xl bg-slate-50 border border-slate-200 p-3 flex flex-wrap items-center gap-3">
                  <span className="text-xs text-slate-500">Título no Fireflies:</span>
                  <Codigo codigo={codigo} tamanho="m" />
                  <BotaoCopiar codigo={codigo} />
                </div>
              )}
              {i === 2 && sim.etapa === "chegou" && (
                <p className="text-xs text-indigo-700 mt-1 flex items-center gap-1.5">
                  <Loader2 className="w-3 h-3 animate-spin" /> Gerando a Ata
                </p>
              )}
            </li>
          ))}
        </ol>
        <div className="mt-5">
          <BotaoSimular {...sim} />
          {sim.etapa === "pronta" && <PreviaDoEmail titulo={titulo} />}
        </div>
      </div>
    </div>
  );
}

/** Monta a versão escolhida no lugar certo: a B vai no topo da página, a A e a C no corpo. */
export function GravarNoFireflies({
  posicao,
  idReuniao,
  titulo,
  doNucleo,
}: {
  posicao: "topo" | "corpo";
  idReuniao: string;
  titulo: string;
  doNucleo?: boolean;
}) {
  const versao = useVersao(VERSOES_DO_CODIGO);
  const codigo = codigoDaGravacao(idReuniao, doNucleo);
  if (posicao === "topo") {
    return (
      <>
        {versao === "B" && <VersaoB codigo={codigo} titulo={titulo} />}
        <PrototypeSwitcher versoes={VERSOES_DO_CODIGO} rotulo="código na Reunião" />
      </>
    );
  }
  if (versao === "A") return <VersaoA codigo={codigo} titulo={titulo} />;
  if (versao === "C") return <VersaoC codigo={codigo} titulo={titulo} />;
  return null;
}
