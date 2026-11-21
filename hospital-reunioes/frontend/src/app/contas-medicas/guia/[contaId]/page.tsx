"use client";

/**
 * O Guia da faturista na Mesa de trabalho (issue #1952, PRD #1933; antes
 * issue #1121, PRD #1113, ADR 0070).
 *
 * A conta aberta ocupa o monitor inteiro, com o MV no outro: cabeçalho da
 * conta, a faixa dos números (Nota de entrada, R$ a ajustar, Itens feitos) e
 * a Mesa de trabalho, com a lista das Linhas por dia e setor de um lado e o
 * Item da vez do outro. Abaixo de 1000 px a lista fica em cima do item. Depois
 * de marcar, o Item da vez passa para a próxima Linha aberta. O rodapé fixo
 * tem a observação e o "Concluir e abrir a próxima", sempre habilitado; na
 * conta concluída, o "Reenviar conta corrigida" (issue #1136).
 *
 * Quem decide tudo é o servidor: a faturista só abre a própria conta, abrir
 * muda A fazer para Em correção, e concluída não aceita marcação. Depois de
 * cada clique a tela relê o Guia, para os números nunca saírem da conta.
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Undo2, Upload } from "lucide-react";

import { ConversaDaConta } from "@/components/contas-medicas/ConversaDaConta";
import { Ditar, juntarDitado } from "@/components/contas-medicas/Ditar";
import { ItemDaVez, type Marcacao } from "@/components/contas-medicas/ItemDaVez";
import { ListaDoGuia } from "@/components/contas-medicas/ListaDoGuia";
import { Dica } from "@/components/ui/Dica";
import { Legenda } from "@/components/ui/Legenda";
import { useToast } from "@/components/ui/Toast";
import { diasDoPeriodo } from "@/lib/contas-medicas/faltouIsto";
import {
  CONCLUIDAS,
  PERGUNTA_DE_DEVOLVER,
  type GrupoGuia,
  type Guia,
  ROTULO_SITUACAO,
  dataCurta,
  esperaMarcacao,
  itensQueFaltam,
  linhasEmOrdem,
  perguntaDeConclusao,
  proximaAberta,
  reais,
  resumoDoReenvio,
  rotuloDoGrupo,
} from "@/lib/contas-medicas/guia";
import { createClient } from "@/lib/supabase/client";

const COR_DA_SITUACAO: Record<string, string> = {
  A_FAZER: "bg-[#FEE2E2] text-[#991B1B]",
  EM_CORRECAO: "bg-[#FEF3C7] text-[#92400E]",
  CONCLUIDA: "bg-[#DCFCE7] text-[#166534]",
  CONCLUIDA_COM_PENDENCIA: "bg-[#FEF3C7] text-[#92400E]",
  RETORNO: "bg-[#FEF3C7] text-[#92400E]",
};

const DICA_DE_DEVOLVER = "A conta volta para a Fila, livre, com as marcações que você já fez.";
const DICA_DE_REANALISAR =
  "A conta volta para a análise com a memória e as tabelas de agora. As linhas já marcadas ficam como estão.";

const TITULO = "text-xs font-semibold uppercase tracking-[0.04em] text-slate-500";
const BOTAO_DO_TOPO =
  "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700 hover:border-slate-300 disabled:opacity-50";

function coluna(valor: string): string {
  return valor.charAt(0).toUpperCase() + valor.slice(1).toLowerCase();
}

function subtitulo(guia: Guia): string {
  const c = guia.cabecalho;
  const parcial =
    c.periodo_inicio && c.periodo_fim
      ? `parcial de ${dataCurta(c.periodo_inicio)} a ${dataCurta(c.periodo_fim)}`
      : null;
  return [
    c.numero_conta ? `conta ${c.numero_conta}` : null,
    c.operadora,
    c.coluna_preco ? `coluna ${coluna(c.coluna_preco)}` : null,
    parcial,
  ]
    .filter(Boolean)
    .join(" · ");
}

/** Os dias em que o Faltou isto vale: o período da conta, ou os dias dos grupos quando ele falta. */
function diasDoFaltouIsto(guia: Guia): string[] {
  const doPeriodo = diasDoPeriodo(guia.cabecalho.periodo_inicio, guia.cabecalho.periodo_fim);
  if (doPeriodo.length > 0) return doPeriodo;
  return [...new Set(guia.grupos.map((grupo) => grupo.data).filter((dia): dia is string => Boolean(dia)))].sort();
}

async function detalhe(resposta: Response, padrao: string): Promise<string> {
  try {
    const corpo = await resposta.json();
    return typeof corpo?.detail === "string" ? corpo.detail : padrao;
  } catch {
    return padrao;
  }
}

export default function GuiaPage() {
  const params = useParams<{ contaId: string }>();
  const bruto = params?.contaId;
  const contaId = Array.isArray(bruto) ? bruto[0] : (bruto ?? "");
  const router = useRouter();
  const { toast } = useToast();

  const [token, setToken] = useState<string | null>(null);
  const [guia, setGuia] = useState<Guia | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [observacao, setObservacao] = useState("");
  const [resultadoDoReenvio, setResultadoDoReenvio] = useState<string | null>(null);
  const [escolhaDoFaltouIsto, setEscolhaDoFaltouIsto] = useState<{ dia: string; vez: number } | null>(null);
  const [idDaVez, setIdDaVez] = useState<string | null>(null);
  const seletorDoPdf = useRef<HTMLInputElement>(null);

  const base = `/api/contas-medicas/contas/${contaId}/guia`;

  const carregar = useCallback(
    async (tk: string): Promise<Guia | null> => {
      const resposta = await fetch(base, { headers: { Authorization: `Bearer ${tk}` } });
      if (!resposta.ok) {
        setErro(await detalhe(resposta, "Não consegui abrir o guia desta conta."));
        return null;
      }
      setErro(null);
      const lido: Guia = await resposta.json();
      setGuia(lido);
      return lido;
    },
    [base],
  );

  useEffect(() => {
    let vivo = true;
    async function iniciar() {
      const {
        data: { session },
      } = await createClient().auth.getSession();
      const tk = session?.access_token ?? null;
      if (!vivo) return;
      setToken(tk);
      setGuia(null);
      setObservacao("");
      setResultadoDoReenvio(null);
      if (!tk) {
        setErro("Sessão expirada. Entre de novo.");
        return;
      }
      const lido = await carregar(tk);
      if (lido && vivo) setIdDaVez(proximaAberta(lido, null));
    }
    iniciar();
    return () => {
      vivo = false;
    };
  }, [carregar]);

  async function enviar(caminho: string, metodo: string, corpo?: unknown): Promise<Response | null> {
    if (!token) return null;
    setOcupado(true);
    try {
      const resposta = await fetch(`${base}${caminho}`, {
        method: metodo,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(corpo !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        ...(corpo !== undefined ? { body: JSON.stringify(corpo) } : {}),
      });
      if (!resposta.ok) {
        toast(await detalhe(resposta, "Não deu certo. Tente de novo."), "error");
        return null;
      }
      return resposta;
    } finally {
      setOcupado(false);
    }
  }

  async function marcar(linhaId: string, marcacao: Marcacao) {
    if (!(await enviar(`/linhas/${linhaId}/marcacao`, "POST", marcacao))) return;
    const lido = await carregar(token as string);
    if (lido) setIdDaVez(proximaAberta(lido, linhaId));
  }

  async function desfazer(linhaId: string) {
    if (await enviar(`/linhas/${linhaId}/marcacao`, "DELETE")) await carregar(token as string);
  }

  async function marcarODia(grupo: GrupoGuia) {
    if (!(await enviar("/dia/feito", "POST", { data: grupo.data, setor: grupo.setor }))) return;
    const lido = await carregar(token as string);
    if (!lido) return;
    const atual = linhasEmOrdem(lido).find((linha) => linha.id === idDaVez);
    if (!atual || !esperaMarcacao(atual)) setIdDaVez(proximaAberta(lido, idDaVez));
  }

  function copiar(codigo: string) {
    if (!navigator.clipboard) {
      toast("Não consegui copiar o código", "error");
      return;
    }
    navigator.clipboard.writeText(codigo).then(
      () => toast("Código copiado", "success"),
      () => toast("Não consegui copiar o código", "error"),
    );
  }

  async function reanalisar() {
    if (!token) return;
    setOcupado(true);
    try {
      const resposta = await fetch(`/api/contas-medicas/contas/${contaId}/reanalisar`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resposta.ok) {
        toast(await detalhe(resposta, "Não deu certo. Tente de novo."), "error");
        return;
      }
      toast("A conta voltou para a análise", "success");
      router.push("/contas-medicas");
    } finally {
      setOcupado(false);
    }
  }

  async function devolver() {
    if (!token || !window.confirm(PERGUNTA_DE_DEVOLVER)) return;
    setOcupado(true);
    try {
      const resposta = await fetch(`/api/contas-medicas/contas/${contaId}/devolver`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resposta.ok) {
        toast(await detalhe(resposta, "Não deu certo. Tente de novo."), "error");
        return;
      }
      toast("A conta voltou para a Fila", "success");
      router.push("/contas-medicas");
    } finally {
      setOcupado(false);
    }
  }

  async function reenviar(arquivo: File | undefined) {
    if (!token || !arquivo) return;
    const corpo = new FormData();
    corpo.append("arquivo", arquivo, arquivo.name);
    setOcupado(true);
    try {
      const resposta = await fetch(`/api/contas-medicas/contas/${contaId}/reenvio`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: corpo,
      });
      if (!resposta.ok) {
        toast(await detalhe(resposta, "Não consegui ler a conta corrigida. Envie de novo."), "error");
        return;
      }
      setResultadoDoReenvio(resumoDoReenvio(await resposta.json()));
    } finally {
      setOcupado(false);
      if (seletorDoPdf.current) seletorDoPdf.current.value = "";
    }
    await carregar(token);
  }

  async function concluir() {
    if (!guia) return;
    const pergunta = perguntaDeConclusao(guia.numeros.itens_sem_marcacao);
    if (pergunta && !window.confirm(pergunta)) return;
    const texto = observacao.trim();
    const resposta = await enviar("/concluir", "POST", texto ? { observacao: texto } : {});
    if (!resposta) return;
    const { proxima_conta_id: proxima } = await resposta.json();
    toast("Conta concluída", "success");
    router.push(proxima ? `/contas-medicas/guia/${proxima}` : "/contas-medicas");
  }

  if (erro) {
    return (
      <div className="max-w-3xl mx-auto">
        <VoltarParaContas />
        <p className="bg-white rounded-2xl border border-border p-6 text-sm text-slate-600">{erro}</p>
      </div>
    );
  }

  if (!guia) {
    return (
      <div className="max-w-3xl mx-auto">
        <VoltarParaContas />
        <p className="text-sm text-slate-500">Abrindo o guia...</p>
      </div>
    );
  }

  const { cabecalho, numeros } = guia;
  const concluida = CONCLUIDAS.includes(cabecalho.situacao);
  const resumoDoAjuste =
    numeros.valor_em_validacao > 0
      ? `em ${numeros.itens_a_ajustar} itens, mais ${reais(numeros.valor_em_validacao)} em validação`
      : `em ${numeros.itens_a_ajustar} itens`;
  const linhas = linhasEmOrdem(guia);
  const posicao = linhas.findIndex((linha) => linha.id === idDaVez);
  const daVez = posicao >= 0 ? linhas[posicao] : null;
  const grupoDaVez = daVez ? guia.grupos.find((grupo) => grupo.linhas.includes(daVez)) : undefined;
  const andamento = numeros.itens_total > 0 ? Math.round((100 * numeros.itens_feitos) / numeros.itens_total) : 0;

  return (
    <div data-testid="guia" className="w-full min-w-0 overflow-x-clip space-y-4">
      <VoltarParaContas />

      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="flex flex-wrap items-baseline gap-x-3 font-bold text-slate-900">
            <span className="text-3xl">{cabecalho.numero_atendimento}</span>{" "}
            {cabecalho.paciente_rotulo && <span className="text-xl normal-case">{cabecalho.paciente_rotulo}</span>}
          </h1>
          <span
            className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold ${
              COR_DA_SITUACAO[cabecalho.situacao] ?? "bg-[#F1F5F9] text-[#475569]"
            }`}
          >
            {ROTULO_SITUACAO[cabecalho.situacao] ?? cabecalho.situacao}
          </span>
          {guia.regra_nova_desde_analise && (
            <span className="inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#EDE9FE] text-[#5B21B6]">
              Regra nova desde a análise
            </span>
          )}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {cabecalho.situacao === "EM_CORRECAO" && (
              <Dica texto={DICA_DE_DEVOLVER}>
                <button type="button" onClick={devolver} disabled={ocupado} className={BOTAO_DO_TOPO}>
                  <Undo2 className="w-4 h-4" aria-hidden="true" />
                  Devolver à fila
                </button>
              </Dica>
            )}
            {guia.pode_reanalisar && (
              <Dica texto={DICA_DE_REANALISAR}>
                <button type="button" onClick={reanalisar} disabled={ocupado} className={BOTAO_DO_TOPO}>
                  <RefreshCw className="w-4 h-4" aria-hidden="true" />
                  {guia.regra_nova_desde_analise ? "Reanalisar com a regra nova" : "Reanalisar"}
                </button>
              </Dica>
            )}
          </div>
        </div>
        <p className="text-sm text-slate-500 break-words">{subtitulo(guia)}</p>
      </header>

      <section
        aria-label="Números do guia"
        className="bg-white rounded-2xl border border-border shadow-premium px-4 py-3 space-y-3"
      >
        <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
          <Numero rotulo="Nota de entrada" dica="De 0 a 100, quanto a conta estava certa antes da correção.">
            {numeros.nota_entrada}
          </Numero>
          {guia.reenvio?.nota_saida != null && (
            <Numero rotulo="Nota de saída" dica="A mesma nota, feita sobre a conta corrigida que você reenviou.">
              {guia.reenvio.nota_saida}
            </Numero>
          )}
          <Numero
            rotulo="R$ a ajustar"
            dica="Quanto falta corrigir no MV. O que está em validação aparece à parte."
            apoio={resumoDoAjuste}
          >
            R$ {reais(numeros.valor_a_ajustar)}
          </Numero>
          <Numero rotulo="Itens feitos" dica="Quantos itens você já marcou, de quantos a conta tem.">
            {numeros.itens_feitos} de {numeros.itens_total}
          </Numero>
        </div>
        <div
          role="progressbar"
          aria-label="Andamento da conta"
          aria-valuemin={0}
          aria-valuemax={numeros.itens_total}
          aria-valuenow={numeros.itens_feitos}
          className="h-2 w-full rounded-full bg-slate-100 overflow-hidden"
        >
          <div className="h-full bg-primary" style={{ width: `${andamento}%` }} />
        </div>
      </section>

      {cabecalho.parecer_parcial && (
        <div
          role="note"
          aria-label="Parecer parcial"
          className="rounded-xl border border-[#FDE68A] bg-[#FEF3C7] px-4 py-3 text-sm text-[#92400E]"
        >
          <p className="font-semibold uppercase tracking-[0.04em]">PARECER PARCIAL</p>
          {cabecalho.faltantes.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {cabecalho.faltantes.map((faltante, indice) => (
                <li key={indice}>{String(faltante)}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(guia.respostas ?? []).length > 0 && (
        <div
          role="note"
          aria-label="Resposta da Validação"
          className="rounded-xl border border-border bg-[#EEEEF6] px-4 py-3 text-sm text-slate-700 space-y-2"
        >
          <p className="font-semibold uppercase tracking-[0.04em] text-primary">Resposta da Validação</p>
          {(guia.respostas ?? []).map((resposta, indice) => (
            <div key={indice}>
              <p className="text-xs text-slate-500">
                {resposta.regra_codigo ? `Regra ${resposta.regra_codigo}` : resposta.titulo}
              </p>
              <p className="whitespace-pre-line break-words">{resposta.resposta}</p>
            </div>
          ))}
        </div>
      )}

      <section
        aria-label="Mesa de trabalho"
        className="grid grid-cols-1 min-[1000px]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-4 items-start"
      >
        <ListaDoGuia
          grupos={guia.grupos}
          idDaVez={idDaVez}
          concluida={concluida}
          ocupado={ocupado}
          onEscolher={setIdDaVez}
          onFaltouIsto={(dia) => setEscolhaDoFaltouIsto({ dia, vez: Date.now() })}
          onMarcarODia={marcarODia}
        />
        <section aria-label="Item da vez" className="min-w-0 bg-white rounded-2xl border border-border shadow-premium p-5">
          {daVez ? (
            <ItemDaVez
              key={daVez.id}
              linha={daVez}
              posicao={posicao + 1}
              total={linhas.length}
              grupo={grupoDaVez ? rotuloDoGrupo(grupoDaVez) : ""}
              concluida={concluida}
              ocupado={ocupado}
              onMarcar={(marcacao) => marcar(daVez.id, marcacao)}
              onDesfazer={() => desfazer(daVez.id)}
              onCopiar={copiar}
            />
          ) : linhas.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">Nada a corrigir nesta conta.</p>
          ) : (
            <div className="text-center py-6 space-y-1">
              <p className="text-sm font-semibold text-slate-700">Todos os itens estão marcados.</p>
              <p className="text-sm text-slate-500">Clique num item da lista para ver de novo.</p>
            </div>
          )}
        </section>
      </section>

      <ConversaDaConta
        contaId={contaId}
        token={token}
        dias={diasDoFaltouIsto(guia)}
        iniciais={guia.faltou_isto ?? []}
        escolha={escolhaDoFaltouIsto}
      />

      <footer className="sticky bottom-0 z-10 bg-white rounded-2xl border border-border shadow-premium p-4 space-y-3">
        {concluida ? (
          <>
            <p className="text-sm text-slate-600">Conta concluída. As marcações não mudam mais.</p>
            {guia.pode_reenviar && (
              <div className="space-y-2">
                <input
                  ref={seletorDoPdf}
                  type="file"
                  accept="application/pdf"
                  aria-label="PDF da conta corrigida"
                  className="hidden"
                  onChange={(evento) => reenviar(evento.target.files?.[0])}
                />
                <button
                  type="button"
                  onClick={() => seletorDoPdf.current?.click()}
                  disabled={ocupado}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 bg-white text-sm font-semibold text-slate-700 hover:border-slate-300 disabled:opacity-50"
                >
                  <Upload className="w-4 h-4" aria-hidden="true" />
                  Reenviar conta corrigida
                </button>
                {resultadoDoReenvio && (
                  <p role="status" className="text-sm font-semibold text-slate-700">
                    {resultadoDoReenvio}
                  </p>
                )}
                <Legenda className="text-xs">
                  Opcional. Depois de corrigir no MV, envie só o PDF da conta para ver se a correção pegou. A conta já
                  está na sua produção.
                </Legenda>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-col min-[1000px]:flex-row min-[1000px]:items-start gap-3">
            <p className="text-sm font-semibold text-slate-700 min-[1000px]:w-48 shrink-0">
              {itensQueFaltam(numeros.itens_sem_marcacao)}
            </p>
            <div className="flex-1 min-w-0 space-y-1">
              <label htmlFor="observacao-gestao" className={`block ${TITULO}`}>
                Observação para a gestão de contas médicas
              </label>
              <textarea
                id="observacao-gestao"
                value={observacao}
                onChange={(evento) => setObservacao(evento.target.value)}
                rows={1}
                placeholder="Opcional"
                className="w-full rounded-lg border border-border px-3 py-2 text-sm"
              />
              <Ditar
                campo="Observação para a gestão de contas médicas"
                aoTranscrever={(ditado) => setObservacao((atual) => juntarDitado(atual, ditado))}
              />
            </div>
            <div className="min-[1000px]:w-72 shrink-0">
              <button
                type="button"
                onClick={concluir}
                className="w-full px-4 py-2 rounded-xl bg-primary text-white text-sm font-semibold uppercase tracking-[0.04em]"
              >
                Concluir e abrir a próxima
              </button>
              <Legenda className="text-xs">
                Você pode concluir com pendência. Os itens em validação e os bloqueados seguem para a gestão, e a
                conta já entra na sua produção.
              </Legenda>
            </div>
          </div>
        )}
      </footer>
    </div>
  );
}

/** Um número da faixa: o rótulo com a dica, o valor grande e, se houver, a linha de apoio. */
function Numero({ rotulo, dica, apoio, children }: { rotulo: string; dica: string; apoio?: string; children: ReactNode }) {
  return (
    <div>
      <Dica texto={dica}>
        <span tabIndex={0} className={TITULO}>
          {rotulo}
        </span>
      </Dica>
      <p className="text-2xl font-bold text-primary">{children}</p>
      {apoio && <p className="text-xs text-slate-500">{apoio}</p>}
    </div>
  );
}

function VoltarParaContas() {
  return (
    <Link
      href="/contas-medicas"
      className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 mb-2"
    >
      <ArrowLeft className="w-4 h-4" />
      Contas médicas
    </Link>
  );
}
