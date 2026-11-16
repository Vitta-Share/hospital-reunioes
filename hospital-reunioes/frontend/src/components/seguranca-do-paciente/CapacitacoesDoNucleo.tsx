"use client";

import { useCallback, useEffect, useId, useState, type FormEvent } from "react";
import { AlertCircle, Check, Loader2, Plus } from "lucide-react";

import { createClient } from "@/lib/supabase/client";

export type Publico = "membros" | "profissionais";

export interface TemaMinimo {
  id: string;
  nome: string;
  ativo: boolean;
}

export interface ParticipanteDaCapacitacao {
  participante_id: string;
  nome: string | null;
  /** Quando a própria pessoa confirmou. Nulo = ainda não confirmou. */
  presenca_confirmada_em: string | null;
}

export interface Capacitacao {
  id: string;
  titulo: string;
  data: string;
  carga_horaria: number;
  instrutor: string;
  publico: Publico;
  tema_ids: string[];
  participantes: ParticipanteDaCapacitacao[];
}

export interface CoberturaDoMembro {
  participante_id: string;
  nome: string | null;
  papel: string;
  /** Os temas mínimos ativos cobertos com presença confirmada. */
  temas_cobertos: string[];
}

export interface RespostaDasCapacitacoes {
  capacitacoes: Capacitacao[];
  temas: TemaMinimo[];
  cobertura: CoberturaDoMembro[];
  pode_editar: boolean;
  /** O id de quem está logado: o botão de confirmar só aparece para ele. */
  eu: string | null;
  /** O dia de hoje em São Paulo (AAAA-MM-DD): antes do dia da capacitação não se confirma presença. */
  hoje: string;
}

const LABEL_PUBLICO: Record<Publico, string> = {
  membros: "Membros do Núcleo",
  profissionais: "Profissionais",
};

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO =
  "w-full min-h-[38px] px-3 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary";
const BOTAO =
  "inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-50";
const BOTAO_CLARO =
  "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 hover:border-slate-300 disabled:opacity-50";

/** "2026-12-10" vira "10/12/2026". */
function dataBr(iso: string): string {
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

const DATA_E_HORA = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

function horas(carga: number): string {
  return `${Number(carga).toLocaleString("pt-BR")} h`;
}

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

async function detalheDoErro(res: Response, padrao: string): Promise<string> {
  try {
    const corpo = await res.json();
    if (typeof corpo?.detail === "string") return corpo.detail;
  } catch {
    // resposta sem JSON (ex.: 500 do proxy)
  }
  return padrao;
}

interface Rascunho {
  titulo: string;
  data: string;
  carga_horaria: string;
  instrutor: string;
  publico: Publico;
  tema_ids: string[];
  participantes: string[];
}

const RASCUNHO_VAZIO: Rascunho = {
  titulo: "",
  data: "",
  carga_horaria: "",
  instrutor: "",
  publico: "membros",
  tema_ids: [],
  participantes: [],
};

function alternar(lista: string[], id: string): string[] {
  return lista.includes(id) ? lista.filter((x) => x !== id) : [...lista, id];
}

function FormularioDaCapacitacao({
  temas,
  salvando,
  onSalvar,
  onCancelar,
}: {
  temas: TemaMinimo[];
  salvando: boolean;
  onSalvar: (rascunho: Rascunho) => void;
  onCancelar: () => void;
}) {
  const id = useId();
  const [rascunho, setRascunho] = useState<Rascunho>(RASCUNHO_VAZIO);
  const [pessoas, setPessoas] = useState<{ id: string; nome: string }[]>([]);
  const mudar = (chave: keyof Rascunho) => (e: { target: { value: string } }) =>
    setRascunho((atual) => ({ ...atual, [chave]: e.target.value }));

  useEffect(() => {
    void (async () => {
      try {
        const sessao = await token();
        const res = await fetch("/api/nsp/membros/pessoas", { headers: { Authorization: `Bearer ${sessao}` } });
        if (res.ok) setPessoas((await res.json()).pessoas);
      } catch (e) {
        console.error("Erro ao carregar as pessoas:", e);
      }
    })();
  }, []);

  function enviar(e: FormEvent) {
    e.preventDefault();
    onSalvar(rascunho);
  }

  const ativos = temas.filter((t) => t.ativo);

  return (
    <form aria-label="Nova capacitação" onSubmit={enviar} className="grid gap-3 mt-3">
      <div>
        <label htmlFor={`${id}-titulo`} className="text-xs font-medium text-slate-600">
          Título
        </label>
        <input id={`${id}-titulo`} className={CAMPO} value={rascunho.titulo} onChange={mudar("titulo")} required />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-data`} className="text-xs font-medium text-slate-600">
            Data
          </label>
          <input
            id={`${id}-data`}
            type="date"
            className={CAMPO}
            value={rascunho.data}
            onChange={mudar("data")}
            required
          />
        </div>
        <div>
          <label htmlFor={`${id}-carga`} className="text-xs font-medium text-slate-600">
            Carga horária (horas)
          </label>
          <input
            id={`${id}-carga`}
            type="number"
            min={0.5}
            step={0.5}
            className={CAMPO}
            value={rascunho.carga_horaria}
            onChange={mudar("carga_horaria")}
            required
          />
        </div>
        <div>
          <label htmlFor={`${id}-instrutor`} className="text-xs font-medium text-slate-600">
            Instrutor
          </label>
          <input
            id={`${id}-instrutor`}
            className={CAMPO}
            value={rascunho.instrutor}
            onChange={mudar("instrutor")}
            required
          />
        </div>
        <div>
          <label htmlFor={`${id}-publico`} className="text-xs font-medium text-slate-600">
            Público
          </label>
          <select id={`${id}-publico`} className={CAMPO} value={rascunho.publico} onChange={mudar("publico")}>
            {(Object.keys(LABEL_PUBLICO) as Publico[]).map((p) => (
              <option key={p} value={p}>
                {LABEL_PUBLICO[p]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <fieldset>
        <legend className="text-xs font-medium text-slate-600">Temas tratados</legend>
        {ativos.length === 0 ? (
          <p className="text-sm text-slate-500 mt-1">A lista de temas mínimos ainda está vazia.</p>
        ) : (
          <div className="mt-1 grid gap-1 sm:grid-cols-2">
            {ativos.map((tema) => (
              <label key={tema.id} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={rascunho.tema_ids.includes(tema.id)}
                  onChange={() => setRascunho((atual) => ({ ...atual, tema_ids: alternar(atual.tema_ids, tema.id) }))}
                />
                {tema.nome}
              </label>
            ))}
          </div>
        )}
      </fieldset>

      <fieldset>
        <legend className="text-xs font-medium text-slate-600">Participantes</legend>
        <div className="mt-1 grid gap-1 sm:grid-cols-2 max-h-60 overflow-y-auto">
          {pessoas.map((pessoa) => (
            <label key={pessoa.id} className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={rascunho.participantes.includes(pessoa.id)}
                onChange={() =>
                  setRascunho((atual) => ({ ...atual, participantes: alternar(atual.participantes, pessoa.id) }))
                }
              />
              {pessoa.nome}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-2">
        <button type="submit" className={BOTAO} disabled={salvando || rascunho.participantes.length === 0}>
          {salvando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
          Salvar
        </button>
        <button type="button" className={BOTAO_CLARO} onClick={onCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function FormularioDoTema({
  inicial,
  salvando,
  onSalvar,
  onCancelar,
}: {
  inicial: string;
  salvando: boolean;
  onSalvar: (nome: string) => void;
  onCancelar: () => void;
}) {
  const id = useId();
  const [nome, setNome] = useState(inicial);

  function enviar(e: FormEvent) {
    e.preventDefault();
    onSalvar(nome.trim());
  }

  return (
    <form onSubmit={enviar} className="flex flex-wrap items-end gap-2 mt-2">
      <div className="min-w-0 flex-1">
        <label htmlFor={`${id}-nome`} className="text-xs font-medium text-slate-600">
          Nome do tema
        </label>
        <input id={`${id}-nome`} className={CAMPO} value={nome} onChange={(e) => setNome(e.target.value)} required />
      </div>
      <button type="submit" className={BOTAO} disabled={salvando}>
        Salvar tema
      </button>
      <button type="button" className={BOTAO_CLARO} onClick={onCancelar}>
        Cancelar
      </button>
    </form>
  );
}

/**
 * As Capacitações do Núcleo (issue #1778): cada capacitação com os temas e
 * quem confirmou presença, a cobertura dos temas mínimos por membro e a lista
 * de temas. A Presidência registra a capacitação e edita a lista de temas;
 * quem está na lista de uma capacitação confirma a própria presença com um
 * toque. Quem pode o quê é o servidor que diz.
 */
export function CapacitacoesDoNucleo() {
  const [dados, setDados] = useState<RespostaDasCapacitacoes | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [registrando, setRegistrando] = useState(false);
  const [incluindoTema, setIncluindoTema] = useState(false);
  const [renomeando, setRenomeando] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const sessao = await token();
      const res = await fetch("/api/nsp/capacitacoes", { headers: { Authorization: `Bearer ${sessao}` } });
      if (!res.ok) {
        setErro(await detalheDoErro(res, "Não foi possível carregar as capacitações."));
        return;
      }
      setDados(await res.json());
    } catch (e) {
      console.error("Erro ao carregar as Capacitações:", e);
      setErro("Não foi possível carregar as capacitações.");
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function enviar(url: string, metodo: "POST" | "PATCH", corpo: unknown, padrao: string): Promise<boolean> {
    setSalvando(true);
    setErro(null);
    try {
      const sessao = await token();
      const res = await fetch(url, {
        method: metodo,
        headers: { Authorization: `Bearer ${sessao}`, "Content-Type": "application/json" },
        body: corpo === undefined ? undefined : JSON.stringify(corpo),
      });
      if (!res.ok) {
        setErro(await detalheDoErro(res, padrao));
        return false;
      }
      await carregar();
      return true;
    } catch (e) {
      console.error("Erro ao gravar as Capacitações:", e);
      setErro(padrao);
      return false;
    } finally {
      setSalvando(false);
    }
  }

  async function registrar(rascunho: Rascunho) {
    const corpo = {
      titulo: rascunho.titulo.trim(),
      data: rascunho.data,
      carga_horaria: Number(rascunho.carga_horaria),
      instrutor: rascunho.instrutor.trim(),
      publico: rascunho.publico,
      tema_ids: rascunho.tema_ids,
      participantes: rascunho.participantes,
    };
    if (await enviar("/api/nsp/capacitacoes", "POST", corpo, "Não foi possível registrar a capacitação.")) {
      setRegistrando(false);
    }
  }

  async function incluirTema(nome: string) {
    if (await enviar("/api/nsp/capacitacoes/temas", "POST", { nome }, "Não foi possível incluir o tema.")) {
      setIncluindoTema(false);
    }
  }

  async function renomearTema(id: string, nome: string) {
    if (await enviar(`/api/nsp/capacitacoes/temas/${id}`, "PATCH", { nome }, "Não foi possível renomear o tema.")) {
      setRenomeando(null);
    }
  }

  if (!dados && !erro) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" aria-label="Carregando" />
      </div>
    );
  }

  const temas = dados?.temas ?? [];
  const nomeDoTema = new Map(temas.map((t) => [t.id, t.nome]));
  const ativos = temas.filter((t) => t.ativo);
  const podeEditar = Boolean(dados?.pode_editar);

  return (
    <div className="grid gap-4">
      {erro && (
        <div role="alert" className="flex gap-2 items-start rounded-xl bg-red-50 text-red-800 text-sm px-4 py-3">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
          <span>{erro}</span>
        </div>
      )}

      {podeEditar && (
        <div className={`${CARTAO} px-4 py-4`}>
          {registrando ? (
            <FormularioDaCapacitacao
              temas={temas}
              salvando={salvando}
              onSalvar={(rascunho) => void registrar(rascunho)}
              onCancelar={() => setRegistrando(false)}
            />
          ) : (
            <button type="button" className={BOTAO_CLARO} onClick={() => setRegistrando(true)}>
              <Plus className="w-4 h-4" aria-hidden />
              Registrar capacitação
            </button>
          )}
        </div>
      )}

      {dados && dados.capacitacoes.length === 0 && (
        <p className={`${CARTAO} px-4 py-4 text-sm text-slate-600`}>Nenhuma capacitação registrada ainda.</p>
      )}

      <ul className="grid gap-3">
        {dados?.capacitacoes.map((cap) => {
          const minha = cap.participantes.find((p) => p.participante_id === dados.eu);
          return (
            <li key={cap.id} className={`${CARTAO} px-4 py-4`}>
              <h2 className="text-sm font-semibold text-slate-900 break-words">{cap.titulo}</h2>
              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-slate-500">Data</dt>
                  <dd className="text-slate-900">{dataBr(cap.data)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Carga horária</dt>
                  <dd className="text-slate-900">{horas(cap.carga_horaria)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Instrutor</dt>
                  <dd className="text-slate-900 break-words">{cap.instrutor}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Público</dt>
                  <dd className="text-slate-900">{LABEL_PUBLICO[cap.publico] ?? cap.publico}</dd>
                </div>
              </dl>

              {cap.tema_ids.length > 0 && (
                <ul aria-label="Temas tratados" className="mt-3 flex flex-wrap gap-1.5">
                  {cap.tema_ids.map((tid) => (
                    <li key={tid} className="text-xs rounded-full bg-slate-100 text-slate-700 px-2 py-0.5">
                      {nomeDoTema.get(tid) ?? "Tema removido"}
                    </li>
                  ))}
                </ul>
              )}

              <ul aria-label="Participantes" className="mt-3 grid gap-1 text-sm">
                {cap.participantes.map((p) => (
                  <li key={p.participante_id} className="flex flex-wrap justify-between gap-x-3">
                    <span className="text-slate-900">{p.nome}</span>
                    {p.presenca_confirmada_em ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700">
                        <Check className="w-3.5 h-3.5" aria-hidden />
                        {`Confirmou em ${DATA_E_HORA.format(new Date(p.presenca_confirmada_em))}`}
                      </span>
                    ) : (
                      <span className="text-slate-500">Não confirmou</span>
                    )}
                  </li>
                ))}
              </ul>

              {minha && !minha.presenca_confirmada_em && cap.data <= dados.hoje && (
                <button
                  type="button"
                  className={`${BOTAO} mt-3`}
                  disabled={salvando}
                  onClick={() =>
                    void enviar(
                      `/api/nsp/capacitacoes/${cap.id}/presenca`,
                      "POST",
                      undefined,
                      "Não foi possível confirmar a presença."
                    )
                  }
                >
                  Confirmar minha presença
                </button>
              )}
            </li>
          );
        })}
      </ul>

      <section className={`${CARTAO} px-4 py-4`}>
        <h2 className="text-sm font-semibold text-slate-900">Temas mínimos por membro</h2>
        <p className="text-xs text-slate-500 mt-0.5">Conta só as capacitações em que o membro confirmou presença.</p>
        {ativos.length === 0 ? (
          <p className="text-sm text-slate-600 mt-3">A lista de temas mínimos ainda está vazia.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table aria-label="Temas mínimos por membro" className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500">
                  <th className="py-1 pr-3 font-medium">Membro</th>
                  <th className="py-1 pr-3 font-medium">Cobertos</th>
                  <th className="py-1 font-medium">Temas</th>
                </tr>
              </thead>
              <tbody>
                {dados?.cobertura.map((m) => (
                  <tr key={m.participante_id} className="border-t border-slate-100 align-top">
                    <td className="py-1.5 pr-3 text-slate-900">{m.nome}</td>
                    <td className="py-1.5 pr-3 text-slate-900 whitespace-nowrap">{`${m.temas_cobertos.length} de ${ativos.length}`}</td>
                    <td className="py-1.5 text-slate-700">
                      {m.temas_cobertos.map((tid) => (
                        <span key={tid} className="block">
                          {nomeDoTema.get(tid)}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={`${CARTAO} px-4 py-4`}>
        <h2 className="text-sm font-semibold text-slate-900">Temas mínimos</h2>
        {temas.length === 0 && <p className="text-sm text-slate-600 mt-2">Nenhum tema na lista ainda.</p>}
        <ul aria-label="Temas mínimos" className="mt-2 grid gap-1.5">
          {temas.map((tema) => (
            <li key={tema.id} className={`text-sm ${tema.ativo ? "" : "opacity-70"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-slate-900 break-words">{tema.nome}</span>
                {!tema.ativo && (
                  <span className="text-xs font-medium rounded-full bg-slate-100 text-slate-600 px-2 py-0.5">
                    Desativado
                  </span>
                )}
                {podeEditar && renomeando !== tema.id && (
                  <span className="flex gap-2">
                    <button type="button" className={BOTAO_CLARO} onClick={() => setRenomeando(tema.id)}>
                      Renomear
                    </button>
                    <button
                      type="button"
                      className={BOTAO_CLARO}
                      disabled={salvando}
                      onClick={() =>
                        void enviar(
                          `/api/nsp/capacitacoes/temas/${tema.id}`,
                          "PATCH",
                          { ativo: !tema.ativo },
                          "Não foi possível mudar o tema."
                        )
                      }
                    >
                      {tema.ativo ? "Desativar" : "Reativar"}
                    </button>
                  </span>
                )}
              </div>
              {renomeando === tema.id && (
                <FormularioDoTema
                  inicial={tema.nome}
                  salvando={salvando}
                  onSalvar={(nome) => void renomearTema(tema.id, nome)}
                  onCancelar={() => setRenomeando(null)}
                />
              )}
            </li>
          ))}
        </ul>
        {podeEditar &&
          (incluindoTema ? (
            <FormularioDoTema
              inicial=""
              salvando={salvando}
              onSalvar={(nome) => void incluirTema(nome)}
              onCancelar={() => setIncluindoTema(false)}
            />
          ) : (
            <button type="button" className={`${BOTAO_CLARO} mt-3`} onClick={() => setIncluindoTema(true)}>
              <Plus className="w-4 h-4" aria-hidden />
              Incluir tema
            </button>
          ))}
      </section>
    </div>
  );
}
