"use client";

import { useCallback, useEffect, useId, useState, type FormEvent } from "react";
import { AlertCircle, ExternalLink, Loader2, Plus } from "lucide-react";

import { createClient } from "@/lib/supabase/client";

export type Periodicidade = "mensal" | "anual" | "bienal" | "avulsa";

export interface ResultadoRegistrado {
  data_prevista: string;
  resultado: string;
  realizada_em: string | null;
  registrado_por: string | null;
  registrado_em: string | null;
}

/** A Pendência de lembrete que o job criou e ainda não foi fechada. */
export interface LembreteAberto {
  id_acao: string;
  prazo: string | null;
  status: string;
}

export interface EventoDaAgenda {
  id: string;
  evento: string;
  periodicidade: Periodicidade;
  regra: string | null;
  proxima_data: string | null;
  link: string | null;
  antecedencia_dias: number;
  ativo: boolean;
  /** Os resultados registrados, o mais novo primeiro. */
  historico: ResultadoRegistrado[];
  /** O lembrete aberto da próxima data, se o job já o criou. */
  lembrete?: LembreteAberto | null;
}

const LABEL_PERIODICIDADE: Record<Periodicidade, string> = {
  mensal: "Mensal",
  anual: "Anual",
  bienal: "A cada dois anos",
  avulsa: "Avulsa",
};

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO =
  "w-full min-h-[38px] px-3 py-1.5 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary";
const BOTAO =
  "inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium disabled:opacity-50";
const BOTAO_CLARO =
  "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 hover:border-slate-300 disabled:opacity-50";

/** "2026-12-10" vira "10/12/2026". */
function dataBr(iso: string | null): string {
  if (!iso) return "";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

function hojeLocal(): string {
  const agora = new Date();
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  const dia = String(agora.getDate()).padStart(2, "0");
  return `${agora.getFullYear()}-${mes}-${dia}`;
}

function periodicidadeDoEvento(evento: EventoDaAgenda): string {
  const rotulo = LABEL_PERIODICIDADE[evento.periodicidade] ?? evento.periodicidade;
  if (!evento.regra) return rotulo;
  return `${rotulo}, ${evento.regra.charAt(0).toLowerCase()}${evento.regra.slice(1)}`;
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

async function token(): Promise<string | null> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  return session?.access_token ?? null;
}

/** Os campos que a Presidência edita, como o formulário os guarda. */
interface Campos {
  evento: string;
  periodicidade: Periodicidade;
  regra: string;
  proxima_data: string;
  link: string;
  antecedencia_dias: string;
}

function camposDe(evento?: EventoDaAgenda): Campos {
  return {
    evento: evento?.evento ?? "",
    periodicidade: evento?.periodicidade ?? "mensal",
    regra: evento?.regra ?? "",
    proxima_data: evento?.proxima_data?.slice(0, 10) ?? "",
    link: evento?.link ?? "",
    antecedencia_dias: String(evento?.antecedencia_dias ?? 7),
  };
}

function corpoDe(campos: Campos) {
  return {
    evento: campos.evento.trim(),
    periodicidade: campos.periodicidade,
    regra: campos.regra.trim() || null,
    proxima_data: campos.proxima_data || null,
    link: campos.link.trim() || null,
    antecedencia_dias: Number(campos.antecedencia_dias) || 0,
  };
}

function FormularioDoEvento({
  nome,
  inicial,
  salvando,
  onSalvar,
  onCancelar,
}: {
  nome: string;
  inicial?: EventoDaAgenda;
  salvando: boolean;
  onSalvar: (campos: Campos) => void;
  onCancelar: () => void;
}) {
  const id = useId();
  const [campos, setCampos] = useState<Campos>(() => camposDe(inicial));
  const mudar = (chave: keyof Campos) => (e: { target: { value: string } }) =>
    setCampos((atual) => ({ ...atual, [chave]: e.target.value }));

  function enviar(e: FormEvent) {
    e.preventDefault();
    onSalvar(campos);
  }

  return (
    <form aria-label={nome} onSubmit={enviar} className="grid gap-3 mt-3">
      <div>
        <label htmlFor={`${id}-evento`} className="text-xs font-medium text-slate-600">
          Evento
        </label>
        <input id={`${id}-evento`} className={CAMPO} value={campos.evento} onChange={mudar("evento")} required />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-periodicidade`} className="text-xs font-medium text-slate-600">
            Periodicidade
          </label>
          <select
            id={`${id}-periodicidade`}
            className={CAMPO}
            value={campos.periodicidade}
            onChange={mudar("periodicidade")}
          >
            {(Object.keys(LABEL_PERIODICIDADE) as Periodicidade[]).map((p) => (
              <option key={p} value={p}>
                {LABEL_PERIODICIDADE[p]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor={`${id}-regra`} className="text-xs font-medium text-slate-600">
            Detalhe da periodicidade
          </label>
          <input
            id={`${id}-regra`}
            className={CAMPO}
            value={campos.regra}
            onChange={mudar("regra")}
            placeholder="Ex.: até o 15º dia útil"
          />
        </div>
        <div>
          <label htmlFor={`${id}-data`} className="text-xs font-medium text-slate-600">
            Próxima data
          </label>
          <input
            id={`${id}-data`}
            type="date"
            className={CAMPO}
            value={campos.proxima_data}
            onChange={mudar("proxima_data")}
          />
        </div>
        <div>
          <label htmlFor={`${id}-antecedencia`} className="text-xs font-medium text-slate-600">
            Lembrar quantos dias antes
          </label>
          <input
            id={`${id}-antecedencia`}
            type="number"
            min={0}
            max={90}
            className={CAMPO}
            value={campos.antecedencia_dias}
            onChange={mudar("antecedencia_dias")}
          />
        </div>
      </div>
      <div>
        <label htmlFor={`${id}-link`} className="text-xs font-medium text-slate-600">
          Link
        </label>
        <input
          id={`${id}-link`}
          type="url"
          className={CAMPO}
          value={campos.link}
          onChange={mudar("link")}
          placeholder="https://"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="submit" className={BOTAO} disabled={salvando}>
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

function FormularioDoResultado({
  salvando,
  onRegistrar,
  onCancelar,
}: {
  salvando: boolean;
  onRegistrar: (resultado: string, realizadaEm: string) => void;
  onCancelar: () => void;
}) {
  const id = useId();
  const [resultado, setResultado] = useState("");
  const [realizadaEm, setRealizadaEm] = useState(hojeLocal);

  function enviar(e: FormEvent) {
    e.preventDefault();
    onRegistrar(resultado.trim(), realizadaEm);
  }

  return (
    <form aria-label="Resultado do evento" onSubmit={enviar} className="grid gap-3 mt-3">
      <div>
        <label htmlFor={`${id}-resultado`} className="text-xs font-medium text-slate-600">
          Resultado
        </label>
        <textarea
          id={`${id}-resultado`}
          className={CAMPO}
          rows={3}
          value={resultado}
          onChange={(e) => setResultado(e.target.value)}
          required
        />
      </div>
      <div className="sm:max-w-xs">
        <label htmlFor={`${id}-feito`} className="text-xs font-medium text-slate-600">
          Feito em
        </label>
        <input
          id={`${id}-feito`}
          type="date"
          className={CAMPO}
          value={realizadaEm}
          onChange={(e) => setRealizadaEm(e.target.value)}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="submit" className={BOTAO} disabled={salvando}>
          {salvando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
          Registrar
        </button>
        <button type="button" className={BOTAO_CLARO} onClick={onCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

type Aberto = { id: string; modo: "editar" | "resultado" } | null;

/**
 * A Agenda regulatória do Núcleo (issue #1779): as obrigações recorrentes,
 * com a próxima data, o link e o último resultado. A Presidência inclui,
 * edita, desativa e registra o resultado. O lembrete é uma Pendência que o
 * servidor cria e que aparece aqui, no cartão do evento, até o resultado ser
 * registrado. Quem pode editar é o servidor que diz.
 */
export function AgendaRegulatoria() {
  const [itens, setItens] = useState<EventoDaAgenda[]>([]);
  const [podeEditar, setPodeEditar] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [aberto, setAberto] = useState<Aberto>(null);
  const [incluindo, setIncluindo] = useState(false);
  const [salvando, setSalvando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const sessao = await token();
      const res = await fetch("/api/nsp/agenda", { headers: { Authorization: `Bearer ${sessao}` } });
      if (!res.ok) {
        setErro(await detalheDoErro(res, "Não foi possível carregar a agenda."));
        return;
      }
      const corpo = await res.json();
      setItens(corpo.itens);
      setPodeEditar(Boolean(corpo.pode_editar));
    } catch (e) {
      console.error("Erro ao carregar a Agenda regulatória:", e);
      setErro("Não foi possível carregar a agenda.");
    } finally {
      setCarregando(false);
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
        body: JSON.stringify(corpo),
      });
      if (!res.ok) {
        setErro(await detalheDoErro(res, padrao));
        return false;
      }
      await carregar();
      return true;
    } catch (e) {
      console.error("Erro ao gravar a Agenda regulatória:", e);
      setErro(padrao);
      return false;
    } finally {
      setSalvando(false);
    }
  }

  async function incluir(campos: Campos) {
    if (await enviar("/api/nsp/agenda", "POST", corpoDe(campos), "Não foi possível incluir o evento.")) {
      setIncluindo(false);
    }
  }

  async function editar(id: string, campos: Campos) {
    if (await enviar(`/api/nsp/agenda/${id}`, "PATCH", corpoDe(campos), "Não foi possível salvar o evento.")) {
      setAberto(null);
    }
  }

  async function registrar(id: string, resultado: string, realizadaEm: string) {
    const corpo = { resultado, realizada_em: realizadaEm };
    if (await enviar(`/api/nsp/agenda/${id}/resultado`, "POST", corpo, "Não foi possível registrar o resultado.")) {
      setAberto(null);
    }
  }

  function alternarAtivo(evento: EventoDaAgenda) {
    void enviar(
      `/api/nsp/agenda/${evento.id}`,
      "PATCH",
      { ativo: !evento.ativo },
      "Não foi possível mudar o evento."
    );
  }

  if (carregando) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" aria-label="Carregando" />
      </div>
    );
  }

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
          {incluindo ? (
            <FormularioDoEvento
              nome="Novo evento"
              salvando={salvando}
              onSalvar={(campos) => void incluir(campos)}
              onCancelar={() => setIncluindo(false)}
            />
          ) : (
            <button type="button" className={BOTAO_CLARO} onClick={() => setIncluindo(true)}>
              <Plus className="w-4 h-4" aria-hidden />
              Incluir evento
            </button>
          )}
        </div>
      )}

      <ul className="grid gap-3">
        {itens.map((evento) => {
          const ultimo = evento.historico[0];
          const editando = aberto?.id === evento.id ? aberto.modo : null;
          return (
            <li key={evento.id} className={`${CARTAO} px-4 py-4 ${evento.ativo ? "" : "opacity-70"}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-slate-900">{evento.evento}</h2>
                  <p className="text-sm text-slate-600">{periodicidadeDoEvento(evento)}</p>
                </div>
                {!evento.ativo && (
                  <span className="text-xs font-medium rounded-full bg-slate-100 text-slate-600 px-2 py-0.5">
                    Desativado
                  </span>
                )}
              </div>

              <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-xs text-slate-500">Próxima data</dt>
                  <dd className="text-slate-900">
                    {evento.proxima_data ? dataBr(evento.proxima_data) : "Sem data marcada"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">Último resultado</dt>
                  {ultimo ? (
                    <dd className="text-slate-900">
                      <span className="block break-words">{ultimo.resultado}</span>
                      <span className="block text-xs text-slate-500">
                        Feito em {dataBr(ultimo.realizada_em ?? ultimo.data_prevista)}
                      </span>
                    </dd>
                  ) : (
                    <dd className="text-slate-500">Nenhum ainda</dd>
                  )}
                </div>
              </dl>

              {evento.lembrete && (
                <p
                  role="status"
                  className={`mt-3 rounded-lg px-3 py-2 text-sm ${
                    evento.lembrete.status === "ATRASADO" ? "bg-red-50 text-red-800" : "bg-amber-50 text-amber-900"
                  }`}
                >
                  {evento.lembrete.status === "ATRASADO" ? "Lembrete atrasado" : "Lembrete aberto"}: pendência{" "}
                  {evento.lembrete.id_acao}
                  {evento.lembrete.prazo ? `, prazo ${dataBr(evento.lembrete.prazo)}` : ""}. Registre o resultado para
                  fechar.
                </p>
              )}

              {evento.link && (
                <a
                  href={evento.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  Abrir o link
                  <ExternalLink className="w-3.5 h-3.5" aria-hidden />
                </a>
              )}

              {podeEditar && editando === null && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {evento.ativo && evento.proxima_data && (
                    <button
                      type="button"
                      className={BOTAO_CLARO}
                      onClick={() => setAberto({ id: evento.id, modo: "resultado" })}
                    >
                      Registrar resultado
                    </button>
                  )}
                  <button
                    type="button"
                    className={BOTAO_CLARO}
                    onClick={() => setAberto({ id: evento.id, modo: "editar" })}
                  >
                    Editar
                  </button>
                  <button
                    type="button"
                    className={BOTAO_CLARO}
                    disabled={salvando}
                    onClick={() => alternarAtivo(evento)}
                  >
                    {evento.ativo ? "Desativar" : "Reativar"}
                  </button>
                </div>
              )}

              {editando === "editar" && (
                <FormularioDoEvento
                  nome={`Editar ${evento.evento}`}
                  inicial={evento}
                  salvando={salvando}
                  onSalvar={(campos) => void editar(evento.id, campos)}
                  onCancelar={() => setAberto(null)}
                />
              )}
              {editando === "resultado" && (
                <FormularioDoResultado
                  salvando={salvando}
                  onRegistrar={(resultado, realizadaEm) => void registrar(evento.id, resultado, realizadaEm)}
                  onCancelar={() => setAberto(null)}
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
