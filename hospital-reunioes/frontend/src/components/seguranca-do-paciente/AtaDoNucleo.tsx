"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BadgeCheck, Pen, Plus, Trash2 } from "lucide-react";

import { createClient } from "@/lib/supabase/client";

export interface BlocoDaAta {
  chave: string;
  titulo: string;
  origem: "sistema" | "agente";
  itens: string[];
}

export interface Deliberacao {
  texto: string;
  responsavel: string;
  prazo: string;
  notificacao?: string | null;
}

export interface AtaDoNucleoJson {
  modelo: string;
  resumida: boolean;
  blocos: BlocoDaAta[];
  deliberacoes: Deliberacao[];
  trechos_a_conferir: string[];
  aviso: string | null;
  validacao?: { por: string; em: string } | null;
}

export interface LeituraDaAta {
  id_reuniao: string;
  status_ata: string;
  ata: AtaDoNucleoJson | null;
  pode_conduzir: boolean;
}

// Os blocos que a Presidência reescreve; os outros vêm do sistema.
const BLOCOS_DE_TEXTO = ["plano_de_acao", "alertas_sanitarios", "proxima_reuniao"];

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

async function detalhe(res: Response, padrao: string): Promise<string> {
  try {
    const corpo = await res.json();
    return typeof corpo.detail === "string" ? corpo.detail : padrao;
  } catch {
    return padrao;
  }
}

/**
 * A ata do Núcleo em dez blocos (issue #1775).
 *
 * Identificação, presenças e quórum, pendências da reunião anterior,
 * indicadores, casos e assinaturas vêm do sistema e não se editam aqui. Quem
 * conduz a ata (Presidência, suplente em exercício, Acesso pleno) revisa os
 * blocos do agente e as deliberações e valida; cada deliberação vira
 * pendência. Quem decide quem conduz é o servidor.
 */
export function AtaDoNucleo({ idReuniao, onMudou }: { idReuniao: string; onMudou?: () => void }) {
  const rota = `/api/nsp/reunioes/${idReuniao}/ata`;
  const [leitura, setLeitura] = useState<LeituraDaAta | null>(null);
  const [editando, setEditando] = useState(false);
  const [textos, setTextos] = useState<Record<string, string>>({});
  const [deliberacoes, setDeliberacoes] = useState<Deliberacao[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    const tk = await token();
    const res = await fetch(rota, { headers: { Authorization: `Bearer ${tk}` } });
    if (!res.ok) {
      setErro("Não consegui carregar a ata do Núcleo.");
      return;
    }
    const corpo: LeituraDaAta = await res.json();
    setLeitura(corpo);
    if (corpo.ata) {
      setTextos(
        Object.fromEntries(
          corpo.ata.blocos.filter((b) => BLOCOS_DE_TEXTO.includes(b.chave)).map((b) => [b.chave, b.itens.join("\n")]),
        ),
      );
      setDeliberacoes(corpo.ata.deliberacoes);
      // Sem minuta, a Presidência já começa redigindo.
      setEditando(Boolean(corpo.ata.aviso) && corpo.pode_conduzir && corpo.status_ata === "AGUARDANDO_VALIDACAO");
    }
  }, [rota]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function salvar(): Promise<boolean> {
    setSalvando(true);
    setErro(null);
    const tk = await token();
    const blocos = Object.fromEntries(
      BLOCOS_DE_TEXTO.map((chave) => [
        chave,
        (textos[chave] ?? "")
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean),
      ]),
    );
    const res = await fetch(rota, {
      method: "PUT",
      headers: { Authorization: `Bearer ${tk}`, "Content-Type": "application/json" },
      body: JSON.stringify({ blocos, deliberacoes: deliberacoes.filter((d) => d.texto.trim()) }),
    });
    setSalvando(false);
    if (!res.ok) {
      setErro(await detalhe(res, "Não consegui salvar a ata."));
      return false;
    }
    setEditando(false);
    await carregar();
    return true;
  }

  async function validar() {
    if (editando && !(await salvar())) return;
    setSalvando(true);
    setErro(null);
    const tk = await token();
    const res = await fetch(`${rota}/validar`, { method: "POST", headers: { Authorization: `Bearer ${tk}` } });
    setSalvando(false);
    if (!res.ok) {
      setErro(await detalhe(res, "Não consegui validar a ata."));
      return;
    }
    await carregar();
    onMudou?.();
  }

  function mudarDeliberacao(i: number, campo: keyof Deliberacao, valor: string) {
    setDeliberacoes((atual) => atual.map((d, j) => (j === i ? { ...d, [campo]: valor } : d)));
  }

  if (!leitura) {
    return erro ? <p className="text-sm text-red-700">{erro}</p> : null;
  }
  const ata = leitura.ata;
  if (!ata) {
    return <p className="text-sm text-slate-600">A ata aparece aqui depois que a transcrição for importada.</p>;
  }
  const emValidacao = leitura.status_ata === "AGUARDANDO_VALIDACAO";
  const conduz = leitura.pode_conduzir && emValidacao;

  return (
    <section aria-label="Ata do Núcleo" className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold text-slate-900">
          {ata.resumida ? "Ata resumida do Núcleo" : "Ata do Núcleo"}
        </h2>
        {ata.validacao && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-semibold px-2 py-0.5">
            <BadgeCheck className="w-3.5 h-3.5" aria-hidden />
            Validada
          </span>
        )}
      </div>

      {ata.aviso && emValidacao && (
        <div role="alert" className="flex items-start gap-3 px-4 py-3 rounded-2xl bg-amber-50 border border-amber-200">
          <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" aria-hidden />
          <p className="text-sm text-amber-800">{ata.aviso}</p>
        </div>
      )}

      {emValidacao && !leitura.pode_conduzir && (
        <p className="text-sm text-slate-600">A Presidência revisa e valida esta ata.</p>
      )}

      {ata.blocos.map((bloco, n) => (
        <div key={bloco.chave} className={`${CARTAO} px-4 py-3`}>
          <h3 className="text-sm font-semibold text-slate-900">
            {n + 1}. {bloco.titulo}
            {bloco.origem === "sistema" && <span className="ml-2 text-xs font-normal text-slate-500">do sistema</span>}
          </h3>
          {editando && BLOCOS_DE_TEXTO.includes(bloco.chave) ? (
            <textarea
              aria-label={bloco.titulo}
              value={textos[bloco.chave] ?? ""}
              onChange={(e) => setTextos((atual) => ({ ...atual, [bloco.chave]: e.target.value }))}
              rows={3}
              placeholder="Um item por linha"
              className="mt-2 w-full rounded-lg border border-border px-3 py-2 text-sm"
            />
          ) : editando && bloco.chave === "deliberacoes" ? (
            <div className="mt-2 space-y-2">
              {deliberacoes.map((d, i) => (
                <div key={i} className="flex flex-wrap gap-2 items-center">
                  <input
                    aria-label={`Deliberação ${i + 1}`}
                    value={d.texto}
                    onChange={(e) => mudarDeliberacao(i, "texto", e.target.value)}
                    className="flex-1 min-w-48 rounded-lg border border-border px-3 py-2 text-sm"
                  />
                  <input
                    aria-label={`Responsável da deliberação ${i + 1}`}
                    value={d.responsavel}
                    onChange={(e) => mudarDeliberacao(i, "responsavel", e.target.value)}
                    placeholder="Responsável (função)"
                    className="w-48 rounded-lg border border-border px-3 py-2 text-sm"
                  />
                  <input
                    aria-label={`Prazo da deliberação ${i + 1}`}
                    type="date"
                    value={/^\d{4}-\d{2}-\d{2}$/.test(d.prazo) ? d.prazo : ""}
                    onChange={(e) => mudarDeliberacao(i, "prazo", e.target.value)}
                    className="rounded-lg border border-border px-3 py-2 text-sm"
                  />
                  <button
                    type="button"
                    aria-label={`Tirar a deliberação ${i + 1}`}
                    onClick={() => setDeliberacoes((atual) => atual.filter((_, j) => j !== i))}
                    className="p-2 text-slate-500"
                  >
                    <Trash2 className="w-4 h-4" aria-hidden />
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() => setDeliberacoes((atual) => [...atual, { texto: "", responsavel: "", prazo: "" }])}
                className="inline-flex items-center gap-1 text-sm font-semibold text-[#282760]"
              >
                <Plus className="w-4 h-4" aria-hidden />
                Incluir deliberação
              </button>
            </div>
          ) : bloco.itens.length === 0 ? (
            <p className="mt-1 text-sm text-slate-500">Em branco.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm text-slate-700 list-disc pl-5">
              {bloco.itens.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      ))}

      {ata.trechos_a_conferir.length > 0 && (
        <div className={`${CARTAO} px-4 py-3`}>
          <h3 className="text-sm font-semibold text-slate-900">Trechos para conferir na gravação</h3>
          <ul className="mt-1 space-y-1 text-sm text-slate-700 list-disc pl-5">
            {ata.trechos_a_conferir.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      {erro && <p className="text-sm text-red-700">{erro}</p>}

      {conduz && (
        <div className="flex flex-wrap gap-2">
          {editando ? (
            <button
              type="button"
              onClick={salvar}
              disabled={salvando}
              className="rounded-xl border border-border text-sm font-semibold px-4 py-2.5 disabled:opacity-60"
            >
              Salvar a revisão
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setEditando(true)}
              className="inline-flex items-center gap-2 rounded-xl border border-border text-sm font-semibold px-4 py-2.5"
            >
              <Pen className="w-4 h-4" aria-hidden />
              Revisar
            </button>
          )}
          <button
            type="button"
            onClick={validar}
            disabled={salvando}
            className="inline-flex items-center gap-2 rounded-xl bg-[#282760] text-white text-sm font-semibold px-4 py-2.5 disabled:opacity-60"
          >
            <BadgeCheck className="w-4 h-4" aria-hidden />
            Validar a ata
          </button>
        </div>
      )}
    </section>
  );
}
