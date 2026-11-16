"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { AlertCircle, ChevronDown, Loader2, Plus } from "lucide-react";

import { useCurrentParticipante } from "@/hooks/useCurrentParticipante";
import {
  ACOES_DO_TERMO,
  COR_ESTADO,
  LABEL_ACAO,
  LABEL_CAMPO,
  LABEL_ESTADO,
  LABEL_PAPEL,
  PAPEIS,
  chamarNsp,
  diaDoCarimbo,
  formatarDia,
  hojeLocal,
  registroDoMembro,
  situacaoDoTermo,
  termoPendente,
  type EnvioDoTermo,
  type LinhaDaTrilha,
  type Membro,
  type Papel,
} from "@/lib/seguranca-do-paciente/membros";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const CAMPO =
  "w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40";
const ROTULO = "block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1";
const BOTAO =
  "inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold uppercase tracking-wide bg-primary text-white hover:bg-primary/90 disabled:opacity-50 transition-colors";
const BOTAO_LEVE =
  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wide bg-slate-100 text-slate-700 hover:bg-slate-200 disabled:opacity-50 transition-colors";

// As 7 colunas da lista (issue #1766: no máximo 7 campos por vez). O resto de
// cada membro fica na seção recolhida que o nome abre.
const COLUNAS = ["Membro", "Papel", "Área", "Registro", "Vigência", "Estado", "Termo"];

/**
 * A tela Núcleo, Membros (issue #1766, PRD #1764): quem compõe o Núcleo, até
 * quando, e quem ainda precisa assinar. Os encerrados ficam no histórico,
 * recolhido; a composição de qualquer data vem do servidor. Cadastrar, editar,
 * renovar e encerrar só aparecem para quem gere o Núcleo, e o servidor recusa
 * de novo para quem chamar a API direto.
 */
export function MembrosDoNucleo() {
  const { participante } = useCurrentParticipante();
  const gere = participante?.recursos_nsp?.includes("gerir_nucleo") ?? false;

  const [membros, setMembros] = useState<Membro[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aberto, setAberto] = useState<string | null>(null);
  const [cadastrando, setCadastrando] = useState(false);
  const [avisoDoTermo, setAvisoDoTermo] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    try {
      const corpo = await chamarNsp<{ membros: Membro[] }>("/api/nsp/membros");
      setMembros(corpo.membros);
      setErro(null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar os membros.");
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const atuais = (membros ?? []).filter((m) => m.estado !== "encerrado");
  const encerrados = (membros ?? []).filter((m) => m.estado === "encerrado");

  return (
    <div className="space-y-5">
      {erro && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
          {erro}
        </div>
      )}

      {avisoDoTermo && (
        <div className="flex items-start gap-2 px-4 py-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
          {avisoDoTermo}
        </div>
      )}

      {gere && (
        <div>
          {cadastrando ? (
            <FormularioDeCadastro
              aoCancelar={() => setCadastrando(false)}
              aoSalvar={async (aviso) => {
                setAvisoDoTermo(aviso);
                setCadastrando(false);
                await carregar();
              }}
            />
          ) : (
            <button type="button" className={BOTAO} onClick={() => setCadastrando(true)}>
              <Plus className="w-4 h-4" aria-hidden />
              Cadastrar membro
            </button>
          )}
        </div>
      )}

      <div className={`${CARTAO} overflow-x-auto`}>
        {membros === null && !erro ? (
          <div className="flex items-center justify-center h-32 gap-2 text-slate-400 text-sm">
            <Loader2 className="w-5 h-5 animate-spin text-primary/40" aria-hidden />
            Carregando os membros...
          </div>
        ) : (
          <table aria-label="Membros do Núcleo" className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500 border-b border-slate-100">
                {COLUNAS.map((coluna) => (
                  <th key={coluna} scope="col" className="px-3 py-2.5 whitespace-nowrap">
                    {coluna}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {atuais.length === 0 && (
                <tr>
                  <td colSpan={COLUNAS.length} className="px-3 py-8 text-center text-slate-500">
                    Ninguém cadastrado no Núcleo ainda.
                  </td>
                </tr>
              )}
              {atuais.map((m) => {
                const nome = m.nome ?? "Pessoa sem nome no cadastro";
                const expandido = aberto === m.id;
                return (
                  <Fragment key={m.id}>
                    <tr className="align-top">
                      <td className="px-3 py-2.5">
                        <button
                          type="button"
                          aria-expanded={expandido}
                          onClick={() => setAberto(expandido ? null : m.id)}
                          className="inline-flex items-center gap-1 font-medium text-slate-900 text-left hover:text-primary"
                        >
                          <ChevronDown
                            aria-hidden
                            className={`w-4 h-4 shrink-0 transition-transform ${expandido ? "rotate-180" : ""}`}
                          />
                          {nome}
                        </button>
                      </td>
                      <td className="px-3 py-2.5 text-slate-700">{LABEL_PAPEL[m.papel]}</td>
                      <td className="px-3 py-2.5 text-slate-700">{m.area ?? "Sem área"}</td>
                      <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{registroDoMembro(m)}</td>
                      <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">
                        {formatarDia(m.vigencia_inicio)} a {formatarDia(m.vigencia_fim)}
                      </td>
                      <td className="px-3 py-2.5">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold whitespace-nowrap ${COR_ESTADO[m.estado]}`}
                        >
                          {LABEL_ESTADO[m.estado]}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{situacaoDoTermo(m)}</td>
                    </tr>
                    {expandido && (
                      <tr>
                        <td colSpan={COLUNAS.length} className="px-3 pb-4 bg-slate-50/60">
                          <DetalhesDoMembro membro={m} nome={nome} gere={gere} aoMudar={carregar} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {encerrados.length > 0 && (
        <details className={`${CARTAO} px-4 py-3`}>
          <summary className="cursor-pointer text-sm font-semibold text-slate-700">
            Histórico de participações encerradas
          </summary>
          <ul className="mt-3 space-y-1.5 text-sm text-slate-700">
            {encerrados.map((m) => (
              <li key={m.id}>
                <span className="font-medium">{m.nome}</span>, {LABEL_PAPEL[m.papel]}, de{" "}
                {formatarDia(m.vigencia_inicio)} a {formatarDia(m.vigencia_fim)}
              </li>
            ))}
          </ul>
        </details>
      )}

      <Composicao />
    </div>
  );
}

function Composicao() {
  const [dia, setDia] = useState("");
  const [membros, setMembros] = useState<Membro[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function escolher(valor: string) {
    setDia(valor);
    setMembros(null);
    setErro(null);
    if (!valor) return;
    try {
      const corpo = await chamarNsp<{ membros: Membro[] }>(`/api/nsp/membros?data=${valor}`);
      setMembros(corpo.membros);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível consultar a composição.");
    }
  }

  return (
    <section className={`${CARTAO} px-4 py-4`}>
      <label className={ROTULO} htmlFor="nsp-composicao-dia">
        Composição do Núcleo em
      </label>
      <input
        id="nsp-composicao-dia"
        type="date"
        className={`${CAMPO} max-w-xs`}
        value={dia}
        onChange={(e) => escolher(e.target.value)}
      />
      {erro && <p className="text-sm text-red-700 mt-2">{erro}</p>}
      {membros && membros.length === 0 && (
        <p className="text-sm text-slate-600 mt-3">Ninguém tinha participação vigente nesse dia.</p>
      )}
      {membros && membros.length > 0 && (
        <ul aria-label={`Composição em ${formatarDia(dia)}`} className="mt-3 space-y-1.5 text-sm text-slate-700">
          {membros.map((m) => (
            <li key={m.id}>
              <span className="font-medium">{m.nome}</span>, {LABEL_PAPEL[m.papel]}
              {m.area ? `, ${m.area}` : ""}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

interface Rascunho {
  papel: Papel;
  area: string;
  conselho_profissional: string;
  registro_profissional: string;
  registro_uf: string;
  vigencia_inicio: string;
  vigencia_fim: string;
}

function CamposDoMembro({
  rascunho,
  mudar,
  prefixo,
  setores,
}: {
  rascunho: Rascunho;
  mudar: (r: Rascunho) => void;
  prefixo: string;
  setores: string[];
}) {
  const campo = (nome: keyof Rascunho, rotulo: string, tipo = "text") => (
    <div>
      <label className={ROTULO} htmlFor={`${prefixo}-${nome}`}>
        {rotulo}
      </label>
      <input
        id={`${prefixo}-${nome}`}
        type={tipo}
        className={CAMPO}
        value={rascunho[nome]}
        list={nome === "area" ? `${prefixo}-setores` : undefined}
        onChange={(e) => mudar({ ...rascunho, [nome]: e.target.value })}
      />
    </div>
  );
  return (
    <>
      <div>
        <label className={ROTULO} htmlFor={`${prefixo}-papel`}>
          Papel
        </label>
        <select
          id={`${prefixo}-papel`}
          className={CAMPO}
          value={rascunho.papel}
          onChange={(e) => mudar({ ...rascunho, papel: e.target.value as Papel })}
        >
          {PAPEIS.map((papel) => (
            <option key={papel} value={papel}>
              {LABEL_PAPEL[papel]}
            </option>
          ))}
        </select>
      </div>
      {campo("area", "Área")}
      <datalist id={`${prefixo}-setores`}>
        {setores.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      {campo("conselho_profissional", "Conselho")}
      {campo("registro_profissional", "Número do registro")}
      {campo("registro_uf", "UF do registro")}
      {campo("vigencia_inicio", "Início da vigência", "date")}
      {campo("vigencia_fim", "Fim da vigência", "date")}
    </>
  );
}

function useSetores(): string[] {
  const [setores, setSetores] = useState<string[]>([]);
  useEffect(() => {
    chamarNsp<string[]>("/api/participantes/setores")
      .then(setSetores)
      .catch(() => setSetores([]));
  }, []);
  return setores;
}

function textoOuNulo(valor: string): string | null {
  const limpo = valor.trim();
  return limpo ? limpo : null;
}

function FormularioDeCadastro({
  aoCancelar,
  aoSalvar,
}: {
  aoCancelar: () => void;
  aoSalvar: (avisoDoTermo: string | null) => Promise<void>;
}) {
  const setores = useSetores();
  const [pessoas, setPessoas] = useState<{ id: string; nome: string }[]>([]);
  const [pessoa, setPessoa] = useState("");
  const [rascunho, setRascunho] = useState<Rascunho>({
    papel: "membro",
    area: "",
    conselho_profissional: "",
    registro_profissional: "",
    registro_uf: "",
    vigencia_inicio: hojeLocal(),
    vigencia_fim: "",
  });
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    chamarNsp<{ pessoas: { id: string; nome: string }[] }>("/api/nsp/membros/pessoas")
      .then((corpo) => setPessoas(corpo.pessoas))
      .catch((e) => setErro(e instanceof Error ? e.message : "Não foi possível carregar as pessoas."));
  }, []);

  const pronto = Boolean(pessoa && rascunho.vigencia_inicio && rascunho.vigencia_fim) && !salvando;

  async function salvar() {
    setSalvando(true);
    setErro(null);
    try {
      const novo = await chamarNsp<Membro>("/api/nsp/membros", {
        method: "POST",
        body: {
          participante_id: pessoa,
          papel: rascunho.papel,
          area: textoOuNulo(rascunho.area),
          conselho_profissional: textoOuNulo(rascunho.conselho_profissional),
          registro_profissional: textoOuNulo(rascunho.registro_profissional),
          registro_uf: textoOuNulo(rascunho.registro_uf),
          vigencia_inicio: rascunho.vigencia_inicio,
          vigencia_fim: rascunho.vigencia_fim,
        },
      });
      await aoSalvar(novo.aviso_termo ?? null);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível cadastrar.");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <section aria-label="Cadastrar membro" className={`${CARTAO} p-5`}>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700 mb-3">Cadastrar membro</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="md:col-span-2">
          <label className={ROTULO} htmlFor="nsp-novo-pessoa">
            Pessoa
          </label>
          <select id="nsp-novo-pessoa" className={CAMPO} value={pessoa} onChange={(e) => setPessoa(e.target.value)}>
            <option value="">Escolha no cadastro de pessoas</option>
            {pessoas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nome}
              </option>
            ))}
          </select>
        </div>
        <CamposDoMembro rascunho={rascunho} mudar={setRascunho} prefixo="nsp-novo" setores={setores} />
      </div>
      {erro && <p className="text-sm text-red-700 mt-3">{erro}</p>}
      <div className="flex flex-wrap justify-end gap-2 mt-4">
        <button type="button" className={BOTAO_LEVE} onClick={aoCancelar}>
          Cancelar
        </button>
        <button type="button" className={BOTAO} onClick={salvar} disabled={!pronto}>
          {salvando && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
          Salvar cadastro
        </button>
      </div>
    </section>
  );
}

function DetalhesDoMembro({
  membro,
  nome,
  gere,
  aoMudar,
}: {
  membro: Membro;
  nome: string;
  gere: boolean;
  aoMudar: () => Promise<void>;
}) {
  const setores = useSetores();
  const original: Rascunho = {
    papel: membro.papel,
    area: membro.area ?? "",
    conselho_profissional: membro.conselho_profissional ?? "",
    registro_profissional: membro.registro_profissional ?? "",
    registro_uf: membro.registro_uf ?? "",
    vigencia_inicio: membro.vigencia_inicio,
    vigencia_fim: membro.vigencia_fim,
  };
  const [rascunho, setRascunho] = useState<Rascunho>(original);
  const [novoFim, setNovoFim] = useState("");
  const [encerrarEm, setEncerrarEm] = useState(hojeLocal());
  const [confirmando, setConfirmando] = useState(false);
  const [trilha, setTrilha] = useState<LinhaDaTrilha[] | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    chamarNsp<{ trilha: LinhaDaTrilha[] }>(`/api/nsp/membros/${membro.id}/trilha`)
      .then((corpo) => setTrilha(corpo.trilha))
      .catch(() => setTrilha([]));
  }, [membro.id]);

  async function enviar(caminho: string, method: string, body?: unknown) {
    setOcupado(true);
    setErro(null);
    try {
      const corpo = await chamarNsp<Partial<Membro>>(caminho, { method, body });
      if (corpo?.aviso_termo) setErro(corpo.aviso_termo);
      await aoMudar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível concluir.");
    } finally {
      setOcupado(false);
    }
  }

  function salvarEdicao() {
    const mudancas: Record<string, string | null> = {};
    for (const chave of Object.keys(rascunho) as (keyof Rascunho)[]) {
      if (rascunho[chave] !== original[chave]) {
        mudancas[chave] = chave.startsWith("vigencia") || chave === "papel" ? rascunho[chave] : textoOuNulo(rascunho[chave]);
      }
    }
    if (Object.keys(mudancas).length === 0) return;
    enviar(`/api/nsp/membros/${membro.id}`, "PATCH", mudancas);
  }

  return (
    <section aria-label={`Detalhes de ${nome}`} className="pt-3 space-y-4">
      {erro && <p className="text-sm text-red-700">{erro}</p>}

      {gere && termoPendente(membro) && (
        <TermoDoMembro membro={membro} ocupado={ocupado} enviar={enviar} />
      )}

      {gere && (
        <>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Editar</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <CamposDoMembro
                rascunho={rascunho}
                mudar={setRascunho}
                prefixo={`nsp-editar-${membro.id}`}
                setores={setores}
              />
            </div>
            <div className="flex justify-end mt-3">
              <button type="button" className={BOTAO_LEVE} onClick={salvarEdicao} disabled={ocupado}>
                Salvar alterações
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className={ROTULO} htmlFor={`nsp-renovar-${membro.id}`}>
                Novo fim da vigência
              </label>
              <input
                id={`nsp-renovar-${membro.id}`}
                type="date"
                className={CAMPO}
                value={novoFim}
                onChange={(e) => setNovoFim(e.target.value)}
              />
            </div>
            <button
              type="button"
              className={BOTAO_LEVE}
              disabled={!novoFim || ocupado}
              onClick={() => enviar(`/api/nsp/membros/${membro.id}/renovar`, "POST", { vigencia_fim: novoFim })}
            >
              Renovar
            </button>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className={ROTULO} htmlFor={`nsp-encerrar-${membro.id}`}>
                Encerrar em
              </label>
              <input
                id={`nsp-encerrar-${membro.id}`}
                type="date"
                className={CAMPO}
                value={encerrarEm}
                onChange={(e) => setEncerrarEm(e.target.value)}
              />
            </div>
            {confirmando ? (
              <button
                type="button"
                className={BOTAO_LEVE}
                disabled={!encerrarEm || ocupado}
                onClick={() => enviar(`/api/nsp/membros/${membro.id}/encerrar`, "POST", { data: encerrarEm })}
              >
                Confirmar encerramento
              </button>
            ) : (
              <button type="button" className={BOTAO_LEVE} onClick={() => setConfirmando(true)}>
                Encerrar participação
              </button>
            )}
          </div>
          <p className="text-xs text-slate-500">
            A participação encerrada vai para o histórico e continua na composição dos dias em que valia.
          </p>
        </>
      )}

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Histórico de mudanças</h3>
        {trilha === null ? (
          <p className="text-sm text-slate-400">Carregando...</p>
        ) : trilha.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma mudança registrada.</p>
        ) : (
          <ul className="space-y-1 text-sm text-slate-700">
            {trilha.map((t, i) => (
              <li key={`${t.created_at}-${i}`}>
                {new Date(t.created_at).toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" })},{" "}
                {t.autor ?? "autor desconhecido"}: {LABEL_ACAO[t.acao] ?? t.acao}
                {ACOES_DO_TERMO.has(t.acao) ? (
                  t.motivo ? `, justificativa: ${t.motivo}` : ""
                ) : (
                  <>
                    {t.campo ? ` (${LABEL_CAMPO[t.campo] ?? t.campo})` : ""}
                    {t.valor_anterior || t.valor_novo
                      ? `, de ${t.valor_anterior ?? "vazio"} para ${t.valor_novo ?? "vazio"}`
                      : ""}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/**
 * O Termo de Adesão à espera da assinatura (issues #1768 e #1769): o documento
 * enviado, o erro do último envio e os três caminhos da Presidência quando a
 * assinatura eletrônica falha. O servidor recusa de novo quem não gere o Núcleo.
 */
function TermoDoMembro({
  membro,
  ocupado,
  enviar,
}: {
  membro: Membro;
  ocupado: boolean;
  enviar: (caminho: string, method: string, body?: unknown) => Promise<void>;
}) {
  const [envio, setEnvio] = useState<EnvioDoTermo | null>(null);
  const [liberando, setLiberando] = useState(false);
  const [justificativa, setJustificativa] = useState("");
  const base = `/api/nsp/membros/${membro.id}/termo`;

  useEffect(() => {
    chamarNsp<EnvioDoTermo>(base)
      .then(setEnvio)
      .catch(() => setEnvio(null));
  }, [base, membro.estado, membro.termo_enviado_em]);

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3 space-y-3">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-amber-800">Termo de Adesão</h3>
        <p className="text-sm text-slate-700 mt-1">
          {envio?.situacao === "enviado"
            ? `Enviado para assinatura em ${envio.enviado_em ? diaDoCarimbo(envio.enviado_em) : "data não registrada"}.`
            : envio?.erro ?? "O Termo ainda não foi enviado para assinatura."}
        </p>
        {envio?.documento_url && (
          <a
            href={envio.documento_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-semibold text-primary hover:underline"
          >
            Abrir o documento enviado
          </a>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={BOTAO_LEVE} disabled={ocupado} onClick={() => enviar(`${base}/reconsultar`, "POST")}>
          Reconsultar status da assinatura
        </button>
        <button type="button" className={BOTAO_LEVE} disabled={ocupado} onClick={() => enviar(`${base}/reenviar`, "POST")}>
          Reenviar o Termo
        </button>
        {!liberando && (
          <button type="button" className={BOTAO_LEVE} disabled={ocupado} onClick={() => setLiberando(true)}>
            Liberar sem assinatura
          </button>
        )}
      </div>
      {liberando && (
        <div className="space-y-2">
          <label className={ROTULO} htmlFor={`nsp-liberar-${membro.id}`}>
            Justificativa da liberação
          </label>
          <textarea
            id={`nsp-liberar-${membro.id}`}
            className={CAMPO}
            rows={2}
            maxLength={1000}
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
          />
          <p className="text-xs text-slate-500">A justificativa fica no histórico, com quem liberou e quando.</p>
          <div className="flex flex-wrap justify-end gap-2">
            <button type="button" className={BOTAO_LEVE} onClick={() => setLiberando(false)}>
              Cancelar
            </button>
            <button
              type="button"
              className={BOTAO_LEVE}
              disabled={!justificativa.trim() || ocupado}
              onClick={() => enviar(`${base}/liberar`, "POST", { justificativa: justificativa.trim() })}
            >
              Confirmar liberação
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
