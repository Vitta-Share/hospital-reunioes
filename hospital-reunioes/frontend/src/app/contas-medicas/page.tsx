"use client";

/**
 * A tela Contas de Contas médicas (issues #1114, #1123 e #1951, PRD #1113 e
 * PRD #1933, ADR 0070).
 *
 * Quem envia arrasta a conta e o prontuário do MV (ou clica em "Selecionar
 * arquivos"), recebe na hora o "Último envio" por atendimento e acompanha na
 * etapa Envios o que ainda não ficou pronto. A faturista pega da Fila comum,
 * em ordem de envio, e segue em "Em análise" (issue #1307, ADR 0073). Cada
 * etapa aparece pela permissão: "Enviar contas" dá o envio e Envios, e
 * "Analisar contas" dá a Fila, Em análise e Concluídas (issue #1308). Quem
 * pareia, recusa, ordena e decide quem vê o quê é o servidor; a tela só
 * confere os limites que dá para conferir antes de subir e manda os arquivos
 * em lotes que cabem no teto do corpo.
 *
 * Desde a issue #1951 a tela é feita de peças: a barra do topo, a Esteira com
 * o número de cada etapa, o bloco "Continue de onde parou", a lista de contas
 * (uma linha por conta, pelo número do atendimento e o rótulo do paciente) e
 * o cartão do envio, que segue como era.
 *
 * Desde a issue #1954 a área de envio abre pelo botão "Enviar contas" da
 * barra: fechada para quem analisa, aberta para quem só envia. Soltar os PDFs
 * em qualquer ponto da tela inicia o envio, com os mesmos limites.
 *
 * Desde a issue #1955 (ADR 0105) Em análise e Concluídas trazem as contas de
 * todas as faturistas, cada uma com quem está com ela, e o filtro "Todas" e
 * "Minhas" da barra recorta essas duas etapas pelas contas da pessoa.
 *
 * A busca da barra (issue #1956) vai ao servidor 300 ms depois da última
 * tecla, a partir do segundo caractere. Com texto no campo, os resultados
 * ocupam o lugar da Esteira e da lista; limpar o campo devolve a etapa que
 * estava aberta.
 *
 * Desde a issue #1958 (ADR 0105) Concluídas vem agrupada por Competência,
 * com "Arquivar" em cada conta e "Arquivar o mês" no cabeçalho do grupo, e a
 * Esteira ganha a etapa Arquivadas, cuja lista só vem do servidor quando a
 * etapa é aberta, com "Desarquivar".
 */

import { type DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2, ReceiptText, Upload } from "lucide-react";

import { BarraDeContas } from "@/components/contas-medicas/contas/BarraDeContas";
import { CampoDaBusca, ResultadosDaBusca } from "@/components/contas-medicas/contas/BuscaDeContas";
import { BarraDeTempos, CartaoDoEnvio } from "@/components/contas-medicas/contas/CartaoDoEnvio";
import { ContasPorCompetencia } from "@/components/contas-medicas/contas/ContasPorCompetencia";
import { ContinueDeOndeParou } from "@/components/contas-medicas/contas/ContinueDeOndeParou";
import { Esteira } from "@/components/contas-medicas/contas/Esteira";
import { FiltroTodasMinhas, useRecorte } from "@/components/contas-medicas/contas/FiltroTodasMinhas";
import { ListaDeContas } from "@/components/contas-medicas/contas/ListaDeContas";
import { PainelDoProcessamento } from "@/components/contas-medicas/PainelDoProcessamento";
import { Dica } from "@/components/ui/Dica";
import { Legenda } from "@/components/ui/Legenda";
import {
  ANALISAR_CONTAS,
  ENVIAR_CONTAS,
  type Fila,
  type ItemDaFila,
  type RespostaDoEnvio,
  ROTA_FILA,
  ROTA_ME,
  ROTA_MEUS_ENVIOS,
  analisarAssimMesmo,
  analisarDeNovo,
  avisosDeProntas,
  enviarEmLotes,
  perguntaDoDescarte,
  rotaDoDescarte,
  separarArquivos,
} from "@/lib/contas-medicas/envio";
import {
  FALHA_DO_ARQUIVAR,
  FALHA_DO_DESARQUIVAR,
  ROTA_ARQUIVADAS,
  postar,
  resultadoDoMes,
  rotaDoArquivar,
  rotaDoArquivarOMes,
  rotaDoDesarquivar,
} from "@/lib/contas-medicas/arquivo";
import {
  ESPERA_DA_BUSCA_MS,
  MINIMO_DA_BUSCA,
  type RespostaDaBusca,
  rotaDaBusca,
} from "@/lib/contas-medicas/busca";
import {
  DICA_DO_ENVIAR,
  ETAPAS_DO_RECORTE,
  LEGENDA_DO_ENVIAR,
  LEGENDA_DO_ENVIO,
  SOLTE_PARA_ENVIAR,
  VAZIO_DA_ETAPA,
  type Etapa,
} from "@/lib/contas-medicas/textos";
import { createClient } from "@/lib/supabase/client";

const CARTAO = "bg-white rounded-2xl border border-border shadow-premium";
const ID_DA_AREA = "area-de-envio";

/**
 * Enquanto houver conta esperando a análise, a fila se relê sozinha: a cada
 * 5 s com conta Processando, para a etapa andar na tela, e a cada 20 s só com
 * conta Na fila (issue #1416).
 */
const RELER_A_CADA_MS = 20_000;
const RELER_PROCESSANDO_A_CADA_MS = 5_000;
const ESPERANDO_ANALISE = ["NA_FILA", "PROCESSANDO"];
/** Quanto tempo o aviso "31310 ficou pronta e foi para a Fila" fica na tela. */
const AVISO_DE_PRONTA_MS = 10_000;

/** O que a pessoa pode fazer na tela, pela matriz que `/contas-medicas/me` resolve. */
interface Pode {
  enviar: boolean;
  analisar: boolean;
}

/** As etapas da Esteira na ordem do caminho da conta, só as das permissões da pessoa. */
function etapasDe(pode: Pode): Etapa[] {
  const etapas: Etapa[] = [];
  if (pode.enviar) etapas.push("envios");
  if (pode.analisar) etapas.push("fila", "em_analise", "concluidas", "arquivadas");
  return etapas;
}

/** A lista da resposta do servidor que cada etapa mostra; a das Arquivadas vem à parte. */
const LISTA_DA_ETAPA: Record<Exclude<Etapa, "arquivadas">, "meus_envios" | "fila" | "minhas" | "concluidas"> = {
  envios: "meus_envios",
  fila: "fila",
  em_analise: "minhas",
  concluidas: "concluidas",
};

/** O arrasto traz arquivos (e não um texto ou um link da própria tela). */
function temArquivos(e: DragEvent): boolean {
  return Array.from(e.dataTransfer?.types ?? []).includes("Files");
}

async function lerJson(rota: string, token: string) {
  const resposta = await fetch(rota, { headers: { Authorization: `Bearer ${token}` } });
  if (!resposta.ok) throw new Error(rota);
  return resposta.json();
}

function UltimoEnvio({ resposta }: { resposta: RespostaDoEnvio }) {
  return (
    <section aria-label="Último envio" className={`${CARTAO} p-5`}>
      <h2 className="text-sm font-semibold text-slate-900 mb-3">Último envio</h2>
      {resposta.ultimo_envio.length > 0 ? (
        <ul className="space-y-2">
          {resposta.ultimo_envio.map((linha) => (
            <li key={linha.numero_atendimento} className="text-sm tabular-nums text-slate-800">
              {linha.texto}
              {linha.aviso && <p className="mt-0.5 text-xs text-amber-700">{linha.aviso}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">Nenhum atendimento entrou neste envio.</p>
      )}
      {resposta.recusas.length > 0 && (
        <ul aria-label="Arquivos recusados" className="mt-4 space-y-2 border-t border-border pt-3">
          {resposta.recusas.map((recusa, i) => (
            <li key={`${recusa.arquivo}-${i}`} className="flex gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
              <span>
                {recusa.motivo}
                <span className="block text-xs text-slate-500">
                  {[recusa.arquivo, recusa.numero_atendimento]
                    .filter(Boolean)
                    .join(", ")}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function ContasMedicasPage() {
  const [token, setToken] = useState<string | null>(null);
  const [pode, setPode] = useState<Pode | null>(null);
  const [fila, setFila] = useState<Fila | null>(null);
  const [erroDaFila, setErroDaFila] = useState<string | null>(null);
  const [etapa, setEtapa] = useState<Etapa>("fila");
  const [recorte, setRecorte] = useRecorte();
  /** A área de envio: fechada para quem analisa, aberta para quem só envia (issue #1954). */
  const [areaAberta, setAreaAberta] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const [enviando, setEnviando] = useState<number | null>(null);
  const [ultimo, setUltimo] = useState<RespostaDoEnvio | null>(null);
  const [recusaDoDescarte, setRecusaDoDescarte] = useState<string | null>(null);
  const [prontas, setProntas] = useState<string[]>([]);
  /** A conta do painel lateral do Processamento (issue #1418). */
  const [painel, setPainel] = useState<string | null>(null);
  const seletor = useRef<HTMLInputElement>(null);
  /** Quantos elementos da tela o arrasto de arquivos já cruzou para dentro. */
  const entradasDoArrasto = useRef(0);
  /** Os envios da leitura anterior: a conta Processando que sumiu ficou pronta. */
  const enviosAntes = useRef<ItemDaFila[] | null>(null);
  /** O texto do campo de busca e a resposta da última busca (issue #1956). */
  const [busca, setBusca] = useState("");
  const [achadas, setAchadas] = useState<RespostaDaBusca | null>(null);
  const [erroDaBusca, setErroDaBusca] = useState(false);
  /** A etapa Arquivadas (issue #1958): a lista só vem quando a etapa é aberta. */
  const [arquivadas, setArquivadas] = useState<ItemDaFila[] | null>(null);
  const [erroDasArquivadas, setErroDasArquivadas] = useState(false);
  const [releituraDasArquivadas, setReleituraDasArquivadas] = useState(0);
  /** O aviso do arquivar e a recusa do servidor, na própria lista. */
  const [avisoDoArquivo, setAvisoDoArquivo] = useState<string | null>(null);
  const [recusaDoArquivo, setRecusaDoArquivo] = useState<string | null>(null);

  /** Cada lista vem da rota da permissão dela; a que a pessoa não tem fica vazia. */
  const carregarFila = useCallback(async (tk: string, quem: Pode) => {
    try {
      const [analise, envios] = await Promise.all([
        quem.analisar ? lerJson(ROTA_FILA, tk) : null,
        quem.enviar ? lerJson(ROTA_MEUS_ENVIOS, tk) : null,
      ]);
      setErroDaFila(null);
      if (envios) {
        const avisos = enviosAntes.current ? avisosDeProntas(enviosAntes.current, envios.meus_envios ?? []) : [];
        if (avisos.length > 0) setProntas(avisos);
        enviosAntes.current = envios.meus_envios ?? [];
      }
      setFila({
        todas: Boolean(analise?.todas ?? envios?.todas),
        fila: analise?.fila ?? [],
        minhas: analise?.minhas ?? [],
        meus_envios: envios?.meus_envios ?? [],
        concluidas: analise?.concluidas ?? [],
        barra: envios?.barra ?? null,
        contagem: { ...analise?.contagem, ...envios?.contagem },
        contagem_minhas: analise?.contagem_minhas,
      });
    } catch {
      setErroDaFila("Não consegui carregar a fila.");
    }
  }, []);

  useEffect(() => {
    let vivo = true;
    async function iniciar() {
      const {
        data: { session },
      } = await createClient().auth.getSession();
      const tk = session?.access_token ?? null;
      if (!vivo) return;
      setToken(tk);
      if (!tk) {
        setErroDaFila("Sessão expirada. Entre de novo.");
        return;
      }
      let quem: Pode;
      try {
        const { permissoes } = await lerJson(ROTA_ME, tk);
        const lista: string[] = Array.isArray(permissoes) ? permissoes : [];
        quem = { enviar: lista.includes(ENVIAR_CONTAS), analisar: lista.includes(ANALISAR_CONTAS) };
      } catch {
        if (vivo) setErroDaFila("Não consegui carregar a fila.");
        return;
      }
      if (!vivo) return;
      setPode(quem);
      setAreaAberta(!quem.analisar);
      // A faturista entra na Fila; quem só envia, em Envios.
      setEtapa(quem.analisar ? "fila" : "envios");
      await carregarFila(tk, quem);
    }
    iniciar();
    return () => {
      vivo = false;
    };
  }, [carregarFila]);

  const envios = fila?.meus_envios ?? [];
  const intervalo = envios.some((conta) => conta.situacao === "PROCESSANDO")
    ? RELER_PROCESSANDO_A_CADA_MS
    : envios.some((conta) => ESPERANDO_ANALISE.includes(conta.situacao))
      ? RELER_A_CADA_MS
      : null;
  useEffect(() => {
    if (!token || !pode || intervalo === null) return;
    const relogio = setInterval(() => carregarFila(token, pode), intervalo);
    return () => clearInterval(relogio);
  }, [token, pode, intervalo, carregarFila]);

  /** Busca 300 ms depois da última tecla; a resposta de um texto antigo é jogada fora. */
  const termo = busca.trim();
  useEffect(() => {
    setAchadas(null);
    setErroDaBusca(false);
    if (!token || termo.length < MINIMO_DA_BUSCA) return;
    let valendo = true;
    const relogio = setTimeout(async () => {
      try {
        const resposta = await lerJson(rotaDaBusca(termo), token);
        if (valendo) setAchadas(resposta);
      } catch {
        if (valendo) setErroDaBusca(true);
      }
    }, ESPERA_DA_BUSCA_MS);
    return () => {
      valendo = false;
      clearTimeout(relogio);
    };
  }, [termo, token]);

  /** A lista das Arquivadas vem do servidor ao abrir a etapa, e de novo depois de desarquivar. */
  useEffect(() => {
    if (etapa !== "arquivadas" || !token) return;
    let valendo = true;
    setErroDasArquivadas(false);
    lerJson(ROTA_ARQUIVADAS, token)
      .then((resposta) => {
        if (valendo) setArquivadas(resposta.arquivadas ?? []);
      })
      .catch(() => {
        if (valendo) setErroDasArquivadas(true);
      });
    return () => {
      valendo = false;
    };
  }, [etapa, token, releituraDasArquivadas]);

  /** O aviso de que a conta foi para a Fila some sozinho depois de uns segundos. */
  useEffect(() => {
    if (prontas.length === 0) return;
    const relogio = setTimeout(() => setProntas([]), AVISO_DE_PRONTA_MS);
    return () => clearTimeout(relogio);
  }, [prontas]);

  async function enviar(lista: FileList | File[] | null) {
    const arquivos = Array.from(lista ?? []);
    if (!token || !pode || arquivos.length === 0 || enviando !== null) return;
    const { aceitos, recusas } = separarArquivos(arquivos);
    // O andamento do envio aparece na área, mesmo quando os arquivos vieram soltos na tela.
    setAreaAberta(true);
    setEnviando(aceitos.length);
    try {
      const resposta = aceitos.length > 0 ? await enviarEmLotes(aceitos, token) : null;
      setUltimo({
        envio_id: resposta?.envio_id ?? null,
        ultimo_envio: resposta?.ultimo_envio ?? [],
        recusas: [...recusas, ...(resposta?.recusas ?? [])],
      });
    } finally {
      setEnviando(null);
      if (seletor.current) seletor.current.value = "";
    }
    await carregarFila(token, pode);
  }

  /** Pergunta antes; confirmado, o servidor apaga a conta e os PDFs, e a lista se relê. */
  async function descartar(conta: ItemDaFila) {
    if (!token || !pode || !window.confirm(perguntaDoDescarte(conta))) return;
    setRecusaDoDescarte(null);
    try {
      const resposta = await fetch(rotaDoDescarte(conta.id), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => null);
        setRecusaDoDescarte(typeof corpo?.detail === "string" ? corpo.detail : "Não consegui descartar. Tente de novo.");
      }
    } catch {
      setRecusaDoDescarte("Não consegui descartar. Tente de novo.");
    }
    await carregarFila(token, pode);
  }

  /**
   * A conta volta para a fila e a lista se relê: o cartão passa para Na fila.
   * `assimMesmo` é a conta parada por folha escaneada ilegível (issue #1401).
   */
  async function analisarContaDeNovo(contaId: string, assimMesmo = false): Promise<string | null> {
    if (!token || !pode) return null;
    const recusa = await (assimMesmo ? analisarAssimMesmo : analisarDeNovo)(contaId, token);
    if (recusa === null) await carregarFila(token, pode);
    return recusa;
  }

  /** Arquivar uma conta, desarquivar ou o mês: o servidor responde e a lista se relê. */
  async function arquivarAConta(conta: ItemDaFila, desfazer = false) {
    if (!token || !pode) return;
    setAvisoDoArquivo(null);
    const { recusa } = await postar(
      desfazer ? rotaDoDesarquivar(conta.id) : rotaDoArquivar(conta.id),
      token,
      desfazer ? FALHA_DO_DESARQUIVAR : FALHA_DO_ARQUIVAR,
    );
    setRecusaDoArquivo(recusa);
    if (recusa === null) {
      const numero = conta.numero_atendimento ?? "";
      setAvisoDoArquivo(desfazer ? `${numero} voltou para Concluídas.` : `${numero} arquivada.`);
    }
    setReleituraDasArquivadas((n) => n + 1);
    await carregarFila(token, pode);
  }

  async function arquivarOMes(mes: string) {
    if (!token || !pode) return;
    setAvisoDoArquivo(null);
    const { recusa, corpo } = await postar(rotaDoArquivarOMes(mes), token, FALHA_DO_ARQUIVAR);
    setRecusaDoArquivo(recusa);
    if (recusa === null) setAvisoDoArquivo(resultadoDoMes(corpo as { arquivadas: number; com_pendencia: number }));
    await carregarFila(token, pode);
  }

  /** Em "Minhas", Em análise e Concluídas ficam só com as contas da pessoa; Fila e Envios não mudam. */
  const recortada = (qual: Etapa) => recorte === "minhas" && ETAPAS_DO_RECORTE.includes(qual);
  const listaDa = (qual: Etapa): ItemDaFila[] | undefined => {
    const lista = qual === "arquivadas" ? (arquivadas ?? undefined) : fila?.[LISTA_DA_ETAPA[qual]];
    return lista && recortada(qual) ? lista.filter((conta) => conta.minha) : lista;
  };
  const concluidasDoMes = (mes: string | null) => (fila?.concluidas ?? []).filter((c) => (c.competencia ?? null) === mes);
  const contas = listaDa(etapa);
  // A conta que ficou pronta sai dos envios, e o painel dela fecha junto.
  const contaDoPainel = painel ? envios.find((conta) => conta.id === painel) : undefined;
  const fecharOPainel = useCallback(() => setPainel(null), []);
  const etapas = pode ? etapasDe(pode) : [];
  // Sem nenhuma das duas permissões (o credenciamento), a tela fica só com as abas do módulo.
  const semListas = pode !== null && etapas.length === 0;
  /** O número da etapa vem do servidor; antes da primeira leitura, nenhum. */
  const contagemDa = (qual: Etapa): number | null => {
    if (!fila) return null;
    const doServidor = recortada(qual)
      ? fila.contagem_minhas?.[qual as "em_analise" | "concluidas"]
      : fila.contagem?.[qual];
    if (qual === "arquivadas") return doServidor ?? arquivadas?.length ?? 0;
    return doServidor ?? listaDa(qual)?.length ?? 0;
  };
  /** As contas em análise da própria pessoa, para o "Continue de onde parou". */
  const minhasEmAnalise = (fila?.minhas ?? []).filter((conta) => conta.minha);

  /**
   * Soltar os PDFs em qualquer ponto da tela inicia o envio (issue #1954). O
   * realce acende só para arquivos, e o contador de entradas evita que ele
   * pisque ao passar de um elemento para outro dentro da tela.
   */
  const arrastoNaTela = pode?.enviar
    ? {
        onDragEnter: (e: DragEvent<HTMLDivElement>) => {
          if (!temArquivos(e)) return;
          e.preventDefault();
          entradasDoArrasto.current += 1;
          setArrastando(true);
        },
        onDragOver: (e: DragEvent<HTMLDivElement>) => {
          if (temArquivos(e)) e.preventDefault();
        },
        onDragLeave: (e: DragEvent<HTMLDivElement>) => {
          if (!temArquivos(e)) return;
          entradasDoArrasto.current = Math.max(0, entradasDoArrasto.current - 1);
          if (entradasDoArrasto.current === 0) setArrastando(false);
        },
        onDrop: (e: DragEvent<HTMLDivElement>) => {
          e.preventDefault();
          entradasDoArrasto.current = 0;
          setArrastando(false);
          enviar(e.dataTransfer?.files ?? null);
        },
      }
    : {};

  return (
    <div className="relative space-y-6" {...arrastoNaTela}>
      {arrastando && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 z-30 flex items-start justify-center rounded-2xl border-2 border-dashed border-primary bg-primary/5 pt-24"
        >
          <p className="flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-medium text-primary shadow-premium">
            <Upload className="w-4 h-4" aria-hidden="true" />
            {SOLTE_PARA_ENVIAR}
          </p>
        </div>
      )}

      <BarraDeContas>
        {pode?.analisar && <CampoDaBusca texto={busca} onMudar={setBusca} />}
        {pode?.analisar && <FiltroTodasMinhas valor={recorte} onMudar={setRecorte} />}
        {pode?.enviar && (
          <div className="flex max-w-xs flex-col items-end text-right">
            <Dica texto={DICA_DO_ENVIAR} abrePara="esquerda">
              <button
                type="button"
                aria-expanded={areaAberta}
                aria-controls={ID_DA_AREA}
                onClick={() => setAreaAberta((aberta) => !aberta)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium"
              >
                <Upload className="w-4 h-4" aria-hidden="true" />
                Enviar contas
              </button>
            </Dica>
            <Legenda className="text-xs">{LEGENDA_DO_ENVIAR}</Legenda>
          </div>
        )}
      </BarraDeContas>

      {pode?.enviar && areaAberta && (
        <section
          id={ID_DA_AREA}
          aria-label="Envio de contas"
          className={`rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
            arrastando ? "border-primary bg-primary/5" : "border-slate-300 bg-white"
          }`}
        >
          {enviando !== null ? (
            <p className="flex items-center justify-center gap-2 text-sm text-slate-600">
              <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
              Enviando {enviando === 1 ? "1 arquivo" : `${enviando} arquivos`} e lendo cada PDF
            </p>
          ) : (
            <>
              <Upload className="w-8 h-8 text-slate-400 mx-auto mb-3" aria-hidden="true" />
              <p className="text-sm font-medium text-slate-800">Arraste aqui a conta e o prontuário do MV</p>
              <Legenda>{LEGENDA_DO_ENVIO}</Legenda>
              <button
                type="button"
                onClick={() => seletor.current?.click()}
                className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium"
              >
                Selecionar arquivos
              </button>
            </>
          )}
        </section>
      )}

      {pode?.enviar && (
        // Fora da área: o "Enviar a conta" do cartão abre o seletor com a área fechada.
        <input
          ref={seletor}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          aria-label="Arquivos da conta e do prontuário"
          onChange={(e) => enviar(e.target.files)}
        />
      )}

      {ultimo && <UltimoEnvio resposta={ultimo} />}

      {prontas.length > 0 && (
        <div role="status" className="space-y-1 rounded-2xl border border-emerald-100 bg-emerald-50 px-5 py-3">
          {prontas.map((aviso) => (
            <p key={aviso} className="text-sm font-medium text-emerald-800">
              {aviso}
            </p>
          ))}
        </div>
      )}

      {contaDoPainel && token && (
        <PainelDoProcessamento conta={contaDoPainel} token={token} onFechar={fecharOPainel} />
      )}

      {termo && pode?.analisar ? (
        <ResultadosDaBusca texto={busca} resposta={achadas} erro={erroDaBusca} />
      ) : !semListas && (
        <div className="space-y-4">
          <Esteira etapas={etapas} aberta={etapa} contagem={contagemDa} onAbrir={setEtapa} />

          {etapa === "envios" && fila?.barra && <BarraDeTempos barra={fila.barra} />}

          {etapa === "fila" && <ContinueDeOndeParou contas={minhasEmAnalise} />}

          {avisoDoArquivo && (etapa === "concluidas" || etapa === "arquivadas") && (
            <p role="status" className="rounded-2xl border border-emerald-100 bg-emerald-50 px-5 py-3 text-sm font-medium text-emerald-800">
              {avisoDoArquivo}
            </p>
          )}

          {recusaDoArquivo && (etapa === "concluidas" || etapa === "arquivadas") && (
            <p role="alert" className="flex items-center gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4" aria-hidden="true" /> {recusaDoArquivo}
            </p>
          )}

          {recusaDoDescarte && (
            <p role="alert" className="flex items-center gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4" aria-hidden="true" /> {recusaDoDescarte}
            </p>
          )}

          <section aria-label="Lista de contas" className={CARTAO}>
            <div role="tabpanel">
              {etapa === "arquivadas" && erroDasArquivadas ? (
                <p role="alert" className="flex items-center gap-2 p-6 text-sm text-red-700">
                  <AlertCircle className="w-4 h-4" aria-hidden="true" /> Não consegui carregar as arquivadas.
                </p>
              ) : etapa === "arquivadas" && arquivadas === null ? (
                <p className="flex items-center gap-2 p-6 text-sm text-slate-500">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> Carregando as arquivadas
                </p>
              ) : erroDaFila ? (
                <p role="alert" className="flex items-center gap-2 p-6 text-sm text-red-700">
                  <AlertCircle className="w-4 h-4" aria-hidden="true" /> {erroDaFila}
                </p>
              ) : !fila ? (
                <p className="flex items-center gap-2 p-6 text-sm text-slate-500">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> Carregando a fila
                </p>
              ) : contas && contas.length > 0 && etapa === "envios" ? (
                <ul className="space-y-3 p-3">
                  {contas.map((conta) => (
                    <CartaoDoEnvio
                      key={conta.id}
                      conta={conta}
                      onAbrir={() => setPainel(conta.id)}
                      onEnviar={() => seletor.current?.click()}
                      onAnalisarDeNovo={() => analisarContaDeNovo(conta.id)}
                      onAnalisarAssimMesmo={() => analisarContaDeNovo(conta.id, true)}
                      onDescartar={() => descartar(conta)}
                    />
                  ))}
                </ul>
              ) : contas && contas.length > 0 && (etapa === "concluidas" || etapa === "arquivadas") ? (
                <ContasPorCompetencia
                  etapa={etapa}
                  contas={contas}
                  todasDoMes={concluidasDoMes}
                  todas={fila.todas}
                  onArquivar={(conta) => arquivarAConta(conta)}
                  onDesarquivar={(conta) => arquivarAConta(conta, true)}
                  onArquivarOMes={arquivarOMes}
                />
              ) : contas && contas.length > 0 ? (
                <ListaDeContas contas={contas} abreAlheias={fila.todas} />
              ) : (
                <div className="p-10 text-center">
                  <ReceiptText className="w-8 h-8 text-slate-300 mx-auto mb-3" aria-hidden="true" />
                  <p className="text-slate-500 text-sm">{VAZIO_DA_ETAPA[etapa]}</p>
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
