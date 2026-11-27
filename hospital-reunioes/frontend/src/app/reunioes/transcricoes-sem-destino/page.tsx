"use client";

// PROTÓTIPO, descartável (integração Fireflies, ADR 0114 proposta).
// A fila Transcrições sem destino em três versões, trocadas por `?variant=`
// (A, B, C). Os dados são fictícios e ficam só na memória da tela: nada vai ao
// backend. No produto, a fila seria uma tabela nova e as Reuniões viriam do banco.

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CalendarDays, Clock, Inbox, Link2, Plus, Smartphone, Monitor, Trash2, Sparkles, AlertTriangle, Layers, Check } from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import { PrototypeSwitcher, useVersao, type Versao } from "@/components/prototype/PrototypeSwitcher";

const VERSOES: Versao[] = [
  { chave: "A", nome: "Lista com sugestão" },
  { chave: "B", nome: "Duas colunas" },
  { chave: "C", nome: "Uma por vez" },
];

type Reuniao = { id: string; titulo: string; data: string; hora: string; situacao: "agendada" | "com_transcricao" };

const MINHAS_REUNIOES: Reuniao[] = [
  { id: "RD_20261125_090000PA", titulo: "Qualidade da farmácia (fictícia)", data: "25/11", hora: "09:00", situacao: "agendada" },
  { id: "RD_20261125_140000PB", titulo: "Compras e suprimentos (fictícia)", data: "25/11", hora: "14:00", situacao: "agendada" },
  { id: "RD_20261126_100000PC", titulo: "Diretoria assistencial (fictícia)", data: "26/11", hora: "10:00", situacao: "agendada" },
  { id: "RD_20261124_080000PD", titulo: "Escala de enfermagem (fictícia)", data: "24/11", hora: "08:00", situacao: "com_transcricao" },
];

type Motivo = "sem_codigo" | "codigo_nao_confere" | "ja_tem_transcricao";

type Item = {
  id: string;
  tituloDigitado: string;
  data: string;
  hora: string;
  duracao: string;
  aparelho: "celular" | "computador";
  motivo: Motivo;
  sugestao: string | null; // id da Reunião sugerida pelo horário
  diasParaApagar: number;
};

const FILA_INICIAL: Item[] = [
  { id: "t1", tituloDigitado: "farmacia", data: "25/11", hora: "09:04", duracao: "52 min", aparelho: "celular", motivo: "sem_codigo", sugestao: "RD_20261125_090000PA", diasParaApagar: 15 },
  { id: "t2", tituloDigitado: "R-48271 compras", data: "25/11", hora: "14:10", duracao: "47 min", aparelho: "computador", motivo: "codigo_nao_confere", sugestao: "RD_20261125_140000PB", diasParaApagar: 15 },
  { id: "t3", tituloDigitado: "Reunião rápida", data: "17/11", hora: "16:30", duracao: "25 min", aparelho: "celular", motivo: "sem_codigo", sugestao: null, diasParaApagar: 7 },
  { id: "t4", tituloDigitado: "R-30158 escala parte 2", data: "24/11", hora: "09:12", duracao: "38 min", aparelho: "celular", motivo: "ja_tem_transcricao", sugestao: "RD_20261124_080000PD", diasParaApagar: 14 },
];

const TEXTO_DO_MOTIVO: Record<Motivo, string> = {
  sem_codigo: "Chegou sem código no título",
  codigo_nao_confere: "O código não confere, deve ter sido digitado errado",
  ja_tem_transcricao: "Segunda gravação de uma Reunião que já tem Transcrição",
};

function reuniao(id: string | null) {
  return MINHAS_REUNIOES.find((r) => r.id === id) ?? null;
}

function useFila() {
  const { toast } = useToast();
  const [fila, setFila] = useState<Item[]>(FILA_INICIAL);
  function tirar(id: string) {
    setFila((f) => f.filter((i) => i.id !== id));
  }
  return {
    fila,
    puxar(item: Item, idReuniao: string) {
      const r = reuniao(idReuniao);
      tirar(item.id);
      toast(`A Transcrição entrou em "${r?.titulo}". A Ata está sendo gerada.`, "success");
    },
    juntar(item: Item) {
      const r = reuniao(item.sugestao);
      tirar(item.id);
      toast(`As duas gravações foram juntadas em "${r?.titulo}". A Ata está sendo refeita.`, "success");
    },
    criar(item: Item) {
      tirar(item.id);
      toast(`Reunião criada com a gravação de ${item.data} às ${item.hora}. A Ata está sendo gerada.`, "success");
    },
    descartar(item: Item) {
      tirar(item.id);
      toast("Transcrição descartada e apagada.", "info");
    },
    reiniciar: () => setFila(FILA_INICIAL),
  };
}

type Fila = ReturnType<typeof useFila>;

function Aparelho({ item }: { item: Item }) {
  return item.aparelho === "celular" ? <Smartphone className="w-3.5 h-3.5" /> : <Monitor className="w-3.5 h-3.5" />;
}

function SeloDoPrazo({ dias }: { dias: number }) {
  const perto = dias <= 7;
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full border ${perto ? "bg-amber-50 border-amber-200 text-amber-800" : "bg-slate-50 border-slate-200 text-slate-500"}`}>
      Apaga em {dias} dias
    </span>
  );
}

function Vazia({ reiniciar }: { reiniciar: () => void }) {
  return (
    <div className="bg-white rounded-2xl border border-border p-10 text-center">
      <Check className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
      <p className="font-medium text-slate-800">Nenhuma Transcrição esperando.</p>
      <button onClick={reiniciar} className="mt-4 text-xs px-3 py-1.5 rounded-lg border border-dashed border-slate-300 text-slate-500 hover:bg-slate-50">
        Protótipo: recolocar os exemplos
      </button>
    </div>
  );
}

function Acoes({ item, f, escolher }: { item: Item; f: Fila; escolher?: () => void }) {
  const sugerida = reuniao(item.sugestao);
  if (item.motivo === "ja_tem_transcricao")
    return (
      <div className="flex flex-wrap gap-2">
        <button onClick={() => f.juntar(item)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-primary text-white text-sm font-medium hover:shadow-md">
          <Layers className="w-4 h-4" /> Juntar e refazer a Ata
        </button>
        <button onClick={() => f.descartar(item)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-600 text-sm hover:bg-slate-50">
          <Trash2 className="w-4 h-4" /> Descartar
        </button>
      </div>
    );
  return (
    <div className="flex flex-wrap gap-2">
      {sugerida && (
        <button onClick={() => f.puxar(item, sugerida.id)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-primary text-white text-sm font-medium hover:shadow-md">
          <Link2 className="w-4 h-4" /> Puxar para esta Reunião
        </button>
      )}
      {escolher && (
        <button onClick={escolher} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-primary/30 text-primary text-sm font-medium hover:bg-primary/5">
          <CalendarDays className="w-4 h-4" /> Escolher outra Reunião
        </button>
      )}
      <button onClick={() => f.criar(item)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-700 text-sm hover:bg-slate-50">
        <Plus className="w-4 h-4" /> Criar Reunião com esta Transcrição
      </button>
      <button onClick={() => f.descartar(item)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-slate-400 text-sm hover:text-red-600 hover:bg-red-50">
        <Trash2 className="w-4 h-4" /> Descartar
      </button>
    </div>
  );
}

// ── Versão A: lista, cada linha já traz a sugestão e os botões ────────────
function VersaoA({ f }: { f: Fila }) {
  const [escolhendo, setEscolhendo] = useState<string | null>(null);
  if (!f.fila.length) return <Vazia reiniciar={f.reiniciar} />;
  return (
    <div className="space-y-3">
      {f.fila.map((item) => {
        const sugerida = reuniao(item.sugestao);
        return (
          <div key={item.id} className="bg-white rounded-2xl border border-border shadow-premium p-5">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              <span className="font-semibold text-slate-900 flex items-center gap-1.5">
                <CalendarDays className="w-4 h-4 text-slate-400" /> {item.data} às {item.hora}
              </span>
              <span className="text-slate-500 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" /> {item.duracao}
              </span>
              <span className="text-slate-500 flex items-center gap-1.5">
                <Aparelho item={item} /> Título digitado: <span className="font-mono text-slate-700">“{item.tituloDigitado}”</span>
              </span>
              <span className="ml-auto">
                <SeloDoPrazo dias={item.diasParaApagar} />
              </span>
            </div>
            <p className="text-xs text-amber-700 mt-2 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5" /> {TEXTO_DO_MOTIVO[item.motivo]}
            </p>
            <div className="mt-3 rounded-xl bg-indigo-50/60 border border-indigo-100 px-4 py-3 text-sm">
              {sugerida ? (
                <p className="text-slate-700">
                  <Sparkles className="inline w-4 h-4 text-indigo-500 mr-1" />
                  {item.motivo === "ja_tem_transcricao" ? "Reunião do código: " : "Pelo horário, parece ser: "}
                  <span className="font-semibold">{sugerida.titulo}</span>, {sugerida.data} às {sugerida.hora}
                </p>
              ) : (
                <p className="text-slate-600">Nenhuma Reunião sua estava agendada nesse horário.</p>
              )}
            </div>
            <div className="mt-4">
              <Acoes item={item} f={f} escolher={item.motivo !== "ja_tem_transcricao" ? () => setEscolhendo(escolhendo === item.id ? null : item.id) : undefined} />
            </div>
            {escolhendo === item.id && (
              <div className="mt-3 border-t border-slate-100 pt-3 space-y-1.5">
                {MINHAS_REUNIOES.filter((r) => r.situacao === "agendada").map((r) => (
                  <button key={r.id} onClick={() => f.puxar(item, r.id)} className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-50 text-sm text-slate-700">
                    {r.titulo}, {r.data} às {r.hora}
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Versão B: fila à esquerda, minhas Reuniões à direita ──────────────────
function VersaoB({ f }: { f: Fila }) {
  const [selecionada, setSelecionada] = useState<string | null>(FILA_INICIAL[0].id);
  const item = f.fila.find((i) => i.id === selecionada) ?? f.fila[0] ?? null;
  if (!item) return <Vazia reiniciar={f.reiniciar} />;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
      <div className="lg:col-span-2 bg-white rounded-2xl border border-border shadow-premium overflow-hidden">
        <p className="px-5 py-3 border-b border-slate-100 text-xs font-semibold uppercase tracking-wide text-slate-400">Chegaram do Fireflies</p>
        {f.fila.map((i) => (
          <button
            key={i.id}
            onClick={() => setSelecionada(i.id)}
            className={`w-full text-left px-5 py-3.5 border-b border-slate-50 transition-colors ${i.id === item.id ? "bg-primary/5 border-l-4 border-l-primary" : "hover:bg-slate-50"}`}
          >
            <p className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
              <Aparelho item={i} /> {i.data} às {i.hora}, {i.duracao}
            </p>
            <p className="text-xs text-slate-500 mt-0.5 font-mono">“{i.tituloDigitado}”</p>
            <p className="text-[11px] text-amber-700 mt-1">{TEXTO_DO_MOTIVO[i.motivo]}</p>
          </button>
        ))}
      </div>
      <div className="lg:col-span-3 space-y-3">
        <p className="text-sm text-slate-600">
          Para onde vai a gravação de <span className="font-semibold">{item.data} às {item.hora}</span>?
        </p>
        {MINHAS_REUNIOES.map((r) => {
          const sugerida = r.id === item.sugestao;
          const podeReceber = item.motivo === "ja_tem_transcricao" ? sugerida : r.situacao === "agendada";
          return (
            <div
              key={r.id}
              className={`rounded-2xl border p-4 flex items-center gap-4 ${sugerida ? "border-indigo-300 bg-indigo-50/60" : "border-border bg-white"} ${podeReceber ? "" : "opacity-50"}`}
            >
              <div className="flex-1">
                <p className="text-sm font-semibold text-slate-900">{r.titulo}</p>
                <p className="text-xs text-slate-500">
                  {r.data} às {r.hora}, {r.situacao === "agendada" ? "agendada" : "já tem Transcrição"}
                </p>
                {sugerida && (
                  <p className="text-xs text-indigo-700 mt-1 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5" /> {item.motivo === "ja_tem_transcricao" ? "É a Reunião do código" : "Bateu o horário"}
                  </p>
                )}
              </div>
              {podeReceber &&
                (item.motivo === "ja_tem_transcricao" ? (
                  <button onClick={() => f.juntar(item)} className="px-3 py-2 rounded-xl bg-primary text-white text-sm font-medium">
                    Juntar e refazer a Ata
                  </button>
                ) : (
                  <button
                    onClick={() => f.puxar(item, r.id)}
                    className={`px-3 py-2 rounded-xl text-sm font-medium ${sugerida ? "bg-primary text-white" : "border border-primary/30 text-primary hover:bg-primary/5"}`}
                  >
                    Puxar para cá
                  </button>
                ))}
            </div>
          );
        })}
        <div className="flex gap-2 pt-1">
          {item.motivo !== "ja_tem_transcricao" && (
            <button onClick={() => f.criar(item)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-700 text-sm hover:bg-slate-50">
              <Plus className="w-4 h-4" /> Criar Reunião com esta Transcrição
            </button>
          )}
          <button onClick={() => f.descartar(item)} className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-slate-400 text-sm hover:text-red-600 hover:bg-red-50">
            <Trash2 className="w-4 h-4" /> Descartar
          </button>
          <span className="ml-auto self-center">
            <SeloDoPrazo dias={item.diasParaApagar} />
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Versão C: uma gravação por vez, como uma pergunta ─────────────────────
function VersaoC({ f }: { f: Fila }) {
  const [escolha, setEscolha] = useState<string | null>(null);
  const item = f.fila[0] ?? null;
  const opcoes = useMemo(() => {
    if (!item) return [];
    if (item.motivo === "ja_tem_transcricao") return [];
    const agendadas = MINHAS_REUNIOES.filter((r) => r.situacao === "agendada");
    return [...agendadas].sort((a, b) => (a.id === item.sugestao ? -1 : b.id === item.sugestao ? 1 : 0));
  }, [item]);
  if (!item) return <Vazia reiniciar={f.reiniciar} />;
  const total = FILA_INICIAL.length;
  const posicao = total - f.fila.length + 1;
  const marcada = escolha ?? item.sugestao ?? "criar";
  return (
    <div className="max-w-xl mx-auto bg-white rounded-3xl border border-border shadow-premium-strong p-7">
      <p className="text-xs text-slate-400">
        {posicao} de {total}
      </p>
      <h2 className="text-xl font-bold text-slate-900 mt-1">
        {item.motivo === "ja_tem_transcricao" ? "Esta é a segunda parte de uma Reunião?" : "Esta gravação é de qual Reunião?"}
      </h2>
      <p className="text-sm text-slate-600 mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex items-center gap-1.5">
          <Aparelho item={item} /> {item.data} às {item.hora}
        </span>
        <span>{item.duracao}</span>
        <span className="font-mono">“{item.tituloDigitado}”</span>
      </p>
      <p className="text-xs text-amber-700 mt-2">{TEXTO_DO_MOTIVO[item.motivo]}</p>

      {item.motivo === "ja_tem_transcricao" ? (
        <div className="mt-5 space-y-3">
          <p className="text-sm text-slate-700">
            A Reunião <span className="font-semibold">{reuniao(item.sugestao)?.titulo}</span> já recebeu uma gravação. Juntar as duas refaz a Ata do começo, e o
            que já foi corrigido nela se perde.
          </p>
          <div className="flex gap-2">
            <button onClick={() => f.juntar(item)} className="flex-1 px-4 py-3 rounded-xl bg-primary text-white font-medium">
              Juntar e refazer a Ata
            </button>
            <button onClick={() => f.descartar(item)} className="px-4 py-3 rounded-xl border border-slate-200 text-slate-600">
              Descartar
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-5 space-y-2">
          {opcoes.map((r) => (
            <label key={r.id} className={`flex items-center gap-3 rounded-xl border px-4 py-3 cursor-pointer ${marcada === r.id ? "border-primary bg-primary/5" : "border-slate-200"}`}>
              <input type="radio" checked={marcada === r.id} onChange={() => setEscolha(r.id)} />
              <span className="flex-1 text-sm">
                <span className="font-medium text-slate-900">{r.titulo}</span>
                <span className="text-slate-500">, {r.data} às {r.hora}</span>
              </span>
              {r.id === item.sugestao && <span className="text-[11px] text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full">Bateu o horário</span>}
            </label>
          ))}
          <label className={`flex items-center gap-3 rounded-xl border px-4 py-3 cursor-pointer ${marcada === "criar" ? "border-primary bg-primary/5" : "border-slate-200"}`}>
            <input type="radio" checked={marcada === "criar"} onChange={() => setEscolha("criar")} />
            <span className="text-sm font-medium text-slate-900">Criar uma Reunião nova com esta gravação</span>
          </label>
          <div className="flex gap-2 pt-3">
            <button
              onClick={() => {
                if (marcada === "criar") f.criar(item);
                else f.puxar(item, marcada);
                setEscolha(null);
              }}
              className="flex-1 px-4 py-3 rounded-xl bg-primary text-white font-medium"
            >
              Confirmar
            </button>
            <button
              onClick={() => {
                f.descartar(item);
                setEscolha(null);
              }}
              className="px-4 py-3 rounded-xl border border-slate-200 text-slate-600"
            >
              Descartar
            </button>
          </div>
        </div>
      )}
      <div className="mt-5 flex justify-end">
        <SeloDoPrazo dias={item.diasParaApagar} />
      </div>
    </div>
  );
}

function Pagina() {
  const versao = useVersao(VERSOES);
  const f = useFila();
  return (
    <div className="space-y-6 max-w-5xl animate-fade-in-up pb-24">
      <div>
        <Link href="/reunioes/calendario" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-slate-600 mb-2">
          <ArrowLeft className="w-3.5 h-3.5" /> Calendário
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
          <Inbox className="w-6 h-6 text-primary" /> Transcrições sem destino
        </h1>
        <p className="text-sm text-slate-500 mt-1 max-w-2xl">
          Gravações que chegaram do Fireflies sem um código válido. Você vê só a data, a hora, a duração e o título. O texto só abre depois que a
          Transcrição entra numa Reunião sua. Cada uma é apagada com 15 dias.
        </p>
        <p className="text-xs text-amber-700 mt-2">Protótipo: os dados são fictícios e nada é gravado.</p>
      </div>
      {versao === "A" && <VersaoA f={f} />}
      {versao === "B" && <VersaoB f={f} />}
      {versao === "C" && <VersaoC f={f} />}
      <PrototypeSwitcher versoes={VERSOES} rotulo="fila" />
    </div>
  );
}

export default function TranscricoesSemDestinoPrototipo() {
  return (
    <Suspense>
      <Pagina />
    </Suspense>
  );
}
