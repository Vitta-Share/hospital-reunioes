"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, Send, Trash2 } from "lucide-react";

import { createClient } from "@/lib/supabase/client";

export interface ItemDaPauta {
  texto: string;
  id_acao?: string | null;
  situacao?: string | null;
}

export interface BlocoDaPauta {
  chave?: string | null;
  titulo: string;
  sem_dados: boolean;
  itens: ItemDaPauta[];
}

export interface Convocado {
  participante_id: string;
  nome: string | null;
  estado: string;
  email_enviado: boolean;
}

export interface Pauta {
  id_reuniao: string;
  disponivel: boolean;
  disponivel_em: string | null;
  blocos: BlocoDaPauta[];
  editada_em: string | null;
  pode_editar: boolean;
  convocacao: { convocada_em: string | null; convocados: Convocado[] } | null;
  pode_convocar: boolean;
  recusa_da_convocacao: string | null;
}

/** "2027-03-08" vira "08/03/2027", sem passar pelo fuso. */
function dataBr(iso: string): string {
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

function resumoDaConvocacao(convocacao: NonNullable<Pauta["convocacao"]>): string {
  const quando = convocacao.convocada_em
    ? new Date(convocacao.convocada_em).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" })
    : "data não registrada";
  const n = convocacao.convocados.length;
  return `Convocada em ${quando}, ${n} ${n === 1 ? "pessoa" : "pessoas"}:`;
}

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

async function detalhe(res: Response, padrao: string): Promise<string> {
  try {
    const corpo = await res.json();
    return typeof corpo?.detail === "string" ? corpo.detail : padrao;
  } catch {
    return padrao;
  }
}

/**
 * A pauta de uma reunião do Núcleo (issue #1773): montada pelo sistema 5 dias
 * úteis antes da ordinária, com a situação de hoje de cada pendência. A
 * Presidência ajusta os itens e convoca em um clique; quem decide o prazo e
 * quem recebe é o servidor.
 */
export function PautaDaReuniao({ idReuniao }: { idReuniao: string }) {
  const rota = `/api/nsp/reunioes/${idReuniao}`;
  const [pauta, setPauta] = useState<Pauta | null>(null);
  const [rascunho, setRascunho] = useState<BlocoDaPauta[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    const tk = await token();
    const res = await fetch(`${rota}/pauta`, { headers: { Authorization: `Bearer ${tk}` } });
    if (!res.ok) {
      setErro("Não consegui carregar a pauta.");
      return;
    }
    setPauta(await res.json());
  }, [rota]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function salvar() {
    if (!rascunho) return;
    setOcupado(true);
    setErro(null);
    const tk = await token();
    const res = await fetch(`${rota}/pauta`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${tk}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        blocos: rascunho.map((b) => ({ ...b, itens: b.itens.filter((i) => i.texto.trim()) })),
      }),
    });
    setOcupado(false);
    if (!res.ok) {
      setErro(await detalhe(res, "Não consegui salvar a pauta."));
      return;
    }
    setRascunho(null);
    await carregar();
  }

  async function convocar() {
    setOcupado(true);
    setErro(null);
    const tk = await token();
    const res = await fetch(`${rota}/convocacao`, { method: "POST", headers: { Authorization: `Bearer ${tk}` } });
    setOcupado(false);
    if (!res.ok) {
      setErro(await detalhe(res, "Não consegui convocar."));
      return;
    }
    await carregar();
  }

  function mudarItem(b: number, i: number, texto: string) {
    setRascunho((atual) =>
      atual!.map((bloco, x) =>
        x === b ? { ...bloco, itens: bloco.itens.map((item, y) => (y === i ? { ...item, texto } : item)) } : bloco,
      ),
    );
  }

  function tirarItem(b: number, i: number) {
    setRascunho((atual) =>
      atual!.map((bloco, x) => (x === b ? { ...bloco, itens: bloco.itens.filter((_, y) => y !== i) } : bloco)),
    );
  }

  function incluirItem(b: number) {
    setRascunho((atual) =>
      atual!.map((bloco, x) =>
        x === b ? { ...bloco, sem_dados: false, itens: [...bloco.itens, { texto: "" }] } : bloco,
      ),
    );
  }

  if (!pauta) {
    return erro ? <p className="text-sm text-red-700">{erro}</p> : null;
  }

  if (!pauta.disponivel) {
    return (
      <p className="text-sm text-slate-600">
        A pauta aparece em {pauta.disponivel_em ? dataBr(pauta.disponivel_em) : "breve"}, 5 dias úteis antes da reunião.
      </p>
    );
  }

  const blocos = rascunho ?? pauta.blocos;

  return (
    <div className="space-y-4" aria-label="Pauta da reunião">
      {blocos.map((bloco, b) => (
        <section key={`${bloco.chave ?? "bloco"}-${b}`} aria-label={bloco.titulo} className="space-y-1.5">
          <h3 className="text-sm font-semibold text-slate-900">{bloco.titulo}</h3>
          {bloco.sem_dados && bloco.itens.length === 0 && (
            <p className="text-xs text-slate-500">Sem dados nesta fase.</p>
          )}
          {!bloco.sem_dados && bloco.itens.length === 0 && !rascunho && (
            <p className="text-xs text-slate-500">Nada para este bloco.</p>
          )}
          <ul className="space-y-1.5">
            {bloco.itens.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                {rascunho ? (
                  <>
                    <textarea
                      aria-label={`Item ${i + 1} de ${bloco.titulo}`}
                      value={item.texto}
                      onChange={(e) => mudarItem(b, i, e.target.value)}
                      rows={2}
                      className="w-full rounded-lg border border-border px-3 py-2 text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => tirarItem(b, i)}
                      aria-label={`Tirar o item ${i + 1} de ${bloco.titulo}`}
                      className="shrink-0 rounded-lg border border-border p-2"
                    >
                      <Trash2 className="w-4 h-4" aria-hidden />
                    </button>
                  </>
                ) : (
                  <>
                    <span className="min-w-0">{item.texto}</span>
                    {item.situacao && (
                      <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        {item.situacao}
                      </span>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
          {rascunho && (
            <button
              type="button"
              onClick={() => incluirItem(b)}
              className="inline-flex items-center gap-1 text-xs font-semibold text-[#282760]"
            >
              <Plus className="w-3.5 h-3.5" aria-hidden />
              Incluir item em {bloco.titulo}
            </button>
          )}
        </section>
      ))}

      {rascunho && (
        <button
          type="button"
          onClick={() =>
            setRascunho((atual) => [...atual!, { chave: null, titulo: "Outros assuntos", sem_dados: false, itens: [{ texto: "" }] }])
          }
          className="inline-flex items-center gap-1 text-xs font-semibold text-[#282760]"
        >
          <Plus className="w-3.5 h-3.5" aria-hidden />
          Incluir o bloco Outros assuntos
        </button>
      )}

      {erro && <p className="text-sm text-red-700">{erro}</p>}

      <div className="flex flex-wrap gap-2">
        {pauta.pode_editar && !rascunho && (
          <button
            type="button"
            onClick={() => setRascunho(pauta.blocos.map((b) => ({ ...b, itens: b.itens.map((i) => ({ ...i })) })))}
            className="rounded-xl border border-border text-sm px-4 py-2.5"
          >
            Editar a pauta
          </button>
        )}
        {rascunho && (
          <>
            <button
              type="button"
              disabled={ocupado}
              onClick={salvar}
              className="rounded-xl bg-[#282760] text-white text-sm font-semibold px-4 py-2.5 disabled:opacity-60"
            >
              Salvar a pauta
            </button>
            <button
              type="button"
              onClick={() => setRascunho(null)}
              className="rounded-xl border border-border text-sm px-4 py-2.5"
            >
              Cancelar
            </button>
          </>
        )}
        {pauta.pode_convocar && !rascunho && (
          <button
            type="button"
            disabled={ocupado || Boolean(pauta.recusa_da_convocacao)}
            onClick={convocar}
            className="inline-flex items-center gap-2 rounded-xl bg-[#282760] text-white text-sm font-semibold px-4 py-2.5 disabled:opacity-60"
          >
            <Send className="w-4 h-4" aria-hidden />
            Convocar os membros
          </button>
        )}
      </div>

      {pauta.pode_convocar && pauta.recusa_da_convocacao && (
        <p className="text-sm text-amber-800">{pauta.recusa_da_convocacao}</p>
      )}

      {pauta.convocacao && (
        <div className="text-sm text-slate-700">
          <p className="font-semibold">{resumoDaConvocacao(pauta.convocacao)}</p>
          <ul className="mt-1 list-disc pl-5">
            {pauta.convocacao.convocados.map((c) => (
              <li key={c.participante_id}>
                {c.nome ?? "Sem nome no cadastro"}
                {c.email_enviado ? "" : " (e-mail não enviado)"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
