"use client";

/**
 * O Quadro e a lista da aba Tecnologia, só para ler (issue #2279, PRD #2262,
 * ADR 0113, decisões 6 e 7).
 *
 * A partir de 1280px a aba é o Quadro, as Demandas em colunas pela Etapa
 * (issue #1642, ADR 0090). Embaixo de 1280px fica a lista, com o card
 * completo e o filtro de Etapa. O clique num card abre o Documento do card:
 * na tela larga, num painel à direita, por cima do Quadro e sem ser modal
 * (issue #1643), que fecha pelo X ou pelo Esc e devolve o foco ao card; na
 * lista, ao lado dela. O Ampliar leva à largura toda.
 *
 * Saíram, com a issue #2279, o chat do Assistente e o Novo pedido, a
 * Conversa da Demanda, os botões Apagar, Revisar com o código de hoje,
 * Reenviar e Designar de novo e o Conversar do card: o pedido nasce no
 * GitHub e a aba acompanha.
 *
 * Os filtros ficam numa barra em cima, um campo com rótulo por categoria
 * (issue #1578): Tipo, Etapa (só na lista), Origem e Projeto (issue #1715)
 * para todos; o recorte (Para mim, Minhas, Todas), o Responsável e o "Só
 * envio falhou" só para o Desenvolvedor, que é o servidor que diz. Tudo
 * combina, e quem filtra é o servidor.
 *
 * O endereço acompanha o card aberto, em `?demanda=<id>`, sem empilhar o
 * histórico (issue #1586): recarregar e o link de um aviso antigo do sino ou
 * do e-mail abrem o mesmo card. A Demanda do endereço que o filtro esconde
 * troca a barra para o recorte mais largo, sem filtros, e abre; a que não
 * está nem nele vira o aviso "Você não tem acesso a esta Demanda".
 */

import { ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ArrowLeft, Loader2, Maximize2, Search, X } from "lucide-react";

import { Select } from "@/components/ui/Select";
import { useTelaLarga } from "@/hooks/useTelaLarga";

import { CabecalhoDaDemanda, DocumentoDoCard, SeloDoPlanoValidado } from "./DocumentoDoCard";
import { useProjetosDoFiltro } from "./useProjetosDoFiltro";
import { QuadroDaTecnologia } from "./QuadroDaTecnologia";
import { SeloDeEtapa } from "./SeloDeEtapa";
import {
  BASE_TECNOLOGIA,
  CLASSIFICACAO_CLASSE,
  CLASSIFICACAO_ROTULO,
  Classificacao,
  Demanda,
  Desenvolvedor,
  desenvolvedoresValidos,
  ENVIO_FALHOU,
  ETAPA_CLASSE,
  EtapaDemanda,
  ETAPA_ROTULO,
  FALHA_DE_CONEXAO,
  iniciais,
  linkDaDemonstracao,
  nomeDoNumero,
  Origem,
  ORIGEM_CLASSE,
  ORIGEM_ROTULO,
  partesDoCard,
  classeDoProjeto,
  Projeto,
  rotuloDaEtapa,
  rotuloDoProjeto,
  TEM_DEMONSTRACAO,
  temSelo,
  textoDaAbertura,
  URL_DA_LISTA,
  URL_DOS_DESENVOLVEDORES,
} from "./demandas";

export const VOLTAR_PARA_A_LISTA = "Voltar à lista";
export const VOLTAR_AO_QUADRO = "Voltar ao quadro";
export const AMPLIAR = "Ampliar";
/** O fechar do painel à direita do Quadro (issue #1643). */
export const FECHAR_O_PAINEL = "Fechar o pedido";
/** O link de uma Demanda que quem abriu não pode ver (issue #1586): sem título nem número. */
export const SEM_ACESSO = "Você não tem acesso a esta Demanda";
const AMPLIAR_EXPLICADO = "Abrir este pedido em tela cheia";
const LISTA_VAZIA = "Nenhum pedido ainda.";
const LISTA_FALHOU = "Não foi possível carregar os pedidos. Tente recarregar a página.";
const URL_QUEM_SOU = `${BASE_TECNOLOGIA}/eu`;

type Filtro = "para_mim" | "minhas" | "todas";
const FILTROS: { valor: Filtro; rotulo: string }[] = [
  { valor: "para_mim", rotulo: "Para mim" },
  { valor: "minhas", rotulo: "Minhas" },
  { valor: "todas", rotulo: "Todas" },
];
const CLASSIFICACOES = Object.keys(CLASSIFICACAO_ROTULO) as Classificacao[];
const ETAPAS = Object.keys(ETAPA_ROTULO) as EtapaDemanda[];
const ORIGENS = Object.keys(ORIGEM_ROTULO) as Origem[];
/** As opções de cada campo da barra; o valor vazio é "sem filtro" (issue #1578). */
const OPCOES_DE_TIPO = [
  { value: "", label: "Todos" },
  ...CLASSIFICACOES.map((valor) => ({ value: valor, label: CLASSIFICACAO_ROTULO[valor] })),
];
const OPCOES_DE_ETAPA = [
  { value: "", label: "Todas" },
  ...ETAPAS.map((valor) => ({ value: valor, label: ETAPA_ROTULO[valor] })),
];
const OPCOES_DE_ORIGEM = [
  { value: "", label: "Todas" },
  ...ORIGENS.map((valor) => ({ value: valor, label: ORIGEM_ROTULO[valor] })),
];
const LIMPAR_FILTROS = "Limpar filtros";
const SO_ENVIO_FALHOU = "Só envio falhou";
/** O interruptor do Quadro que mostra a coluna Não será feita, no fim (ADR 0090, decisões 2 e 8). */
export const MOSTRAR_AS_QUE_NAO_SERAO_FEITAS = "Mostrar as que não serão feitas";
/** A espera depois da última tecla, para a busca não pedir a lista a cada letra. */
const ESPERA_DA_BUSCA_MS = 300;

/** O que a lista pede ao servidor (issue #1551). */
type FiltrosDaLista = {
  recorte: Filtro;
  busca: string;
  tipo: Classificacao | null;
  etapa: EtapaDemanda | null;
  origem: Origem | null;
  projeto: Projeto | null;
  responsavel: string | null;
  envioFalhou: boolean;
};

/** A URL da lista: sem nenhum filtro, a de antes (as Demandas de quem está logado). */
function urlDaLista(filtros: FiltrosDaLista): string {
  const consulta = new URLSearchParams();
  if (filtros.recorte !== "minhas") consulta.set("filtro", filtros.recorte);
  if (filtros.busca) consulta.set("busca", filtros.busca);
  if (filtros.tipo) consulta.set("tipo", filtros.tipo);
  if (filtros.etapa) consulta.set("etapa", filtros.etapa);
  if (filtros.origem) consulta.set("origem", filtros.origem);
  if (filtros.projeto) consulta.set("projeto", filtros.projeto);
  if (filtros.responsavel) consulta.set("responsavel", filtros.responsavel);
  if (filtros.envioFalhou) consulta.set("envio_falhou", "true");
  const texto = consulta.toString();
  return texto ? `${URL_DA_LISTA}?${texto}` : URL_DA_LISTA;
}

/**
 * Põe a Demanda aberta no endereço (`?demanda=<id>`), ou a tira com `null`,
 * trocando a entrada do histórico em vez de empilhar uma a cada clique (issue
 * #1586). O resto do endereço fica como está.
 */
function demandaNoEndereco(demandaId: string | null) {
  const url = new URL(window.location.href);
  if (demandaId) url.searchParams.set("demanda", demandaId);
  else url.searchParams.delete("demanda");
  window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

/** Um chip de filtro. Nada de `flex-1` nem `nowrap`: a linha quebra dentro da coluna. */
export function Chip({ ativo, onClick, children }: { ativo: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      aria-pressed={ativo}
      onClick={onClick}
      className={`px-3 py-1 rounded-full border text-xs font-semibold ${
        ativo ? "border-primary bg-primary/5 text-primary" : "border-border text-text-secondary"
      }`}
    >
      {children}
    </button>
  );
}

export function GrupoDeChips({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={rotulo} className="flex flex-wrap gap-1">
      {children}
    </div>
  );
}

/** O item serve para a lista? O resto da Demanda é opcional para ela. */
function itemValido(item: unknown): item is Demanda {
  if (typeof item !== "object" || item === null) return false;
  const d = item as Record<string, unknown>;
  return typeof d.id === "string" && typeof d.titulo === "string";
}

/**
 * A Etapa na lista. Aqui "Registrada" aparece escrita: é a conversa sem card,
 * e a lista mostra a Etapa de toda conversa (na conversa aberta ela é a
 * ausência de selo).
 */
function EtapaNaLista({ demanda }: { demanda: Demanda }) {
  const classe = temSelo(demanda) && demanda.etapa ? ETAPA_CLASSE[demanda.etapa] : ETAPA_CLASSE.registrada;
  return <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${classe}`}>{rotuloDaEtapa(demanda)}</span>;
}

/** Bug ou Melhoria, ao lado da Etapa (issue #1438). O pedido de antes do chat fica sem. */
function ClassificacaoNaLista({ demanda }: { demanda: Demanda }) {
  if (!demanda.classificacao) return null;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${CLASSIFICACAO_CLASSE[demanda.classificacao]}`}>
      {CLASSIFICACAO_ROTULO[demanda.classificacao]}
    </span>
  );
}

/** Pedido do diretor ou Vitta (issue #1554). Sem o campo, sem selo. */
function OrigemNaLista({ demanda }: { demanda: Demanda }) {
  if (!demanda.origem) return null;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${ORIGEM_CLASSE[demanda.origem]}`}>
      {ORIGEM_ROTULO[demanda.origem]}
    </span>
  );
}

/** Aplicativo do Hospital, Ana ou um projeto novo da Vitta (issues #1715 e #1967). Sem o campo, sem selo. */
function ProjetoNaLista({ demanda }: { demanda: Demanda }) {
  if (!demanda.projeto) return null;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${classeDoProjeto(demanda.projeto)}`}>
      {rotuloDoProjeto(demanda.projeto, demanda.projeto_nome)}
    </span>
  );
}

/** O pedido que tem vídeo de demonstração (issue #1559). Sem link, sem selo. */
function SeloDaDemonstracao({ demanda }: { demanda: Demanda }) {
  if (!linkDaDemonstracao(demanda)) return null;
  return <span className="px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700">{TEM_DEMONSTRACAO}</span>;
}

/** O selo do card que não chegou ao GitHub (issue #1535). */
function SeloDoEnvioFalhou({ demanda }: { demanda: Demanda }) {
  if (!demanda.envio_falhou) return null;
  return <span className="px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700">{ENVIO_FALHOU}</span>;
}

/** Quem pediu ou quem cuida, com as iniciais num círculo (issue #1578). */
function PessoaNoCard({ papel, nome }: { papel: string; nome: string }) {
  return (
    <span className="flex items-center gap-2 min-w-0">
      <span
        aria-hidden="true"
        className="w-7 h-7 shrink-0 rounded-full bg-primary/10 text-primary text-[11px] font-bold flex items-center justify-center"
      >
        {iniciais(nome)}
      </span>
      <span className="flex flex-col min-w-0 leading-tight">
        <span className="text-[10px] font-semibold tracking-wide text-slate-400">{papel}</span>
        <span className="normal-case text-xs font-medium text-text-primary truncate">{nome}</span>
      </span>
    </span>
  );
}

/** As partes do PRD numa barra (issue #1578). A issue simples não tem barra. */
function PartesNoCard({ demanda }: { demanda: Demanda }) {
  const partes = partesDoCard(demanda);
  if (!partes) return null;
  const largura = `${Math.round((partes.entregues / partes.total) * 100)}%`;
  return (
    <span className="flex items-center gap-3">
      <span
        role="progressbar"
        aria-label="Partes entregues"
        aria-valuemin={0}
        aria-valuemax={partes.total}
        aria-valuenow={partes.entregues}
        className="h-1.5 flex-1 rounded-full bg-slate-100 overflow-hidden"
      >
        <span className="block h-full rounded-full bg-emerald-500" style={{ width: largura }} />
      </span>
      <span className="normal-case text-xs font-medium text-text-secondary whitespace-nowrap">
        {partes.entregues} de {partes.total} partes
      </span>
    </span>
  );
}

/**
 * O card de um pedido na lista (issue #1578). Contorno sempre visível; no
 * hover e no foco ele se destaca e sobe um pouco, sem movimento para quem
 * pediu menos animação ao sistema. O Ampliar fica num botão próprio, ao lado
 * do card, porque botão dentro de botão não existe no HTML (issue #1593).
 */
function CardDaConversa({
  demanda,
  destacada,
  onAbrir,
  onAmpliar,
}: {
  demanda: Demanda;
  destacada: boolean;
  onAbrir: () => void;
  onAmpliar: () => void;
}) {
  const abertura = textoDaAbertura(demanda.criado_em);
  const numero = nomeDoNumero(demanda);
  return (
    <div
      className={`group relative rounded-2xl border bg-white transition duration-150 ease-out motion-reduce:transition-none ${
        destacada
          ? "border-primary ring-2 ring-primary/15 shadow-md"
          : "border-border shadow-sm motion-safe:hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-within:border-primary/40 focus-within:shadow-md"
      }`}
    >
      <button
        type="button"
        onClick={onAbrir}
        aria-current={destacada ? "true" : undefined}
        className="w-full flex flex-col gap-3 p-4 pr-14 md:pr-24 text-left rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <span className="flex flex-col gap-1">
          <span className="normal-case text-[15px] font-semibold leading-snug text-text-primary line-clamp-2">
            {demanda.titulo}
          </span>
          {(numero || abertura) && (
            <span className="flex flex-wrap items-center gap-x-3 normal-case text-xs text-text-secondary">
              {numero && <span className="font-medium">{numero}</span>}
              {abertura && <span>{abertura}</span>}
            </span>
          )}
        </span>
        {(demanda.autor || demanda.responsavel) && (
          <span className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {demanda.autor && <PessoaNoCard papel="Pediu" nome={demanda.autor} />}
            {demanda.responsavel && <PessoaNoCard papel="Responsável" nome={demanda.responsavel} />}
          </span>
        )}
        <PartesNoCard demanda={demanda} />
        <span className="flex flex-wrap items-center gap-1.5">
          <EtapaNaLista demanda={demanda} />
          <ClassificacaoNaLista demanda={demanda} />
          <OrigemNaLista demanda={demanda} />
          <ProjetoNaLista demanda={demanda} />
          <SeloDaDemonstracao demanda={demanda} />
          <SeloDoEnvioFalhou demanda={demanda} />
        </span>
      </button>
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        <button
          type="button"
          onClick={onAmpliar}
          aria-label={AMPLIAR}
          title={AMPLIAR_EXPLICADO}
          className="hidden md:inline-flex w-9 h-9 items-center justify-center rounded-xl border border-border bg-white text-primary shadow-sm hover:bg-primary/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

/** Para mim, Minhas e Todas, numa peça só: um dos três está sempre escolhido. */
function RecorteDaLista({ valor, onMudar }: { valor: Filtro | null; onMudar: (filtro: Filtro) => void }) {
  return (
    <div role="group" aria-label="Recorte" className="inline-flex shrink-0 p-1 rounded-xl bg-slate-100">
      {FILTROS.map(({ valor: opcao, rotulo }) => (
        <button
          key={opcao}
          type="button"
          aria-pressed={valor === opcao}
          onClick={() => onMudar(opcao)}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors motion-reduce:transition-none ${
            valor === opcao ? "bg-white text-primary shadow-sm" : "text-text-secondary hover:text-text-primary"
          }`}
        >
          {rotulo}
        </button>
      ))}
    </div>
  );
}

/**
 * Um interruptor da barra: o "Só envio falhou" do Desenvolvedor, que não é
 * Etapa (issue #1578), e o "Mostrar as que não serão feitas" do Quadro (issue #1644).
 */
function InterruptorDaBarra({
  rotulo,
  ligado,
  onMudar,
}: {
  rotulo: string;
  ligado: boolean;
  onMudar: (ligado: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligado}
      onClick={() => onMudar(!ligado)}
      className="inline-flex items-center gap-2 text-xs font-semibold text-text-secondary"
    >
      <span
        aria-hidden="true"
        className={`relative w-9 h-5 rounded-full transition-colors motion-reduce:transition-none ${
          ligado ? "bg-primary" : "bg-slate-300"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform motion-reduce:transition-none ${
            ligado ? "translate-x-4" : ""
          }`}
        />
      </span>
      {rotulo}
    </button>
  );
}

/** O nome da área do pedido aberto: a Etapa, a Origem, quem pediu e o Documento do card. */
export const ACOMPANHAMENTO = "Acompanhamento do pedido";

/**
 * O pedido aberto, só para ler (issue #2279): a Etapa, a Origem, quem pediu e
 * o Documento do card. A Demanda ainda sem card (o bug do Assistente do app
 * antes do envio) mostra só o cabeçalho, com o número e o Copiar link.
 */
function Acompanhamento({ demanda }: { demanda: Demanda }) {
  const semDocumento = !temSelo(demanda) && !demanda.raiz_url;
  return (
    <section aria-label={ACOMPANHAMENTO} className="w-full bg-white rounded-2xl border border-primary/30 shadow-premium p-5 space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <h2 className="normal-case text-base font-bold text-slate-900">{demanda.titulo}</h2>
        <SeloDeEtapa demanda={demanda} />
        <SeloDoPlanoValidado demanda={demanda} />
        <OrigemNaLista demanda={demanda} />
        {demanda.autor && <span className="normal-case text-text-secondary">{demanda.autor}</span>}
      </div>
      {semDocumento ? <CabecalhoDaDemanda demanda={demanda} /> : <DocumentoDoCard demanda={demanda} />}
    </section>
  );
}

export function ConversasDaTecnologia({
  token,
  demandaInicial = null,
  onVerEntregas,
}: {
  token: string | null;
  /** A Demanda que o aviso do sino pediu para abrir. */
  demandaInicial?: string | null;
  /** O "Ver todos nas Entregas" da coluna Entregue troca para a aba Entregas (issue #1644). */
  onVerEntregas?: () => void;
}) {
  /** A partir de 1280px a aba é o Quadro, e a Demanda abre na largura toda (issue #1642, ADR 0090). */
  const largo = useTelaLarga();
  const [demandas, setDemandas] = useState<Demanda[] | null>(null);
  const [erroDaLista, setErroDaLista] = useState<string | null>(null);
  /** A Demanda clicada, aberta no Documento do card. */
  const [aberta, setAberta] = useState<Demanda | null>(null);
  /** A que a lista destaca: a clicada. */
  const [destacada, setDestacada] = useState<string | null>(null);
  const [naTela, setNaTela] = useState<"lista" | "pedido">("lista");
  /** O pedido aberto na largura toda, com a lista recolhida: só o Ampliar liga (issue #1593). */
  const [ampliada, setAmpliada] = useState(false);
  /** Na tela larga, a Demanda aberta no painel à direita, com o Quadro atrás (issue #1643). */
  const [noPainel, setNoPainel] = useState(false);
  /** O Quadro, onde o painel procura o card para devolver o foco quando fecha. */
  const quadroRef = useRef<HTMLDivElement>(null);
  const [desenvolvedor, setDesenvolvedor] = useState(false);
  /** Nulo até o servidor dizer quem está logado: o Desenvolvedor abre em Para mim. */
  const [filtro, setFiltro] = useState<Filtro | null>(null);
  const [textoDaBusca, setTextoDaBusca] = useState("");
  const [busca, setBusca] = useState("");
  const [tipo, setTipo] = useState<Classificacao | null>(null);
  const [etapa, setEtapa] = useState<EtapaDemanda | null>(null);
  const [origem, setOrigem] = useState<Origem | null>(null);
  const [projeto, setProjeto] = useState<Projeto | null>(null);
  const [responsavel, setResponsavel] = useState<string | null>(null);
  const [envioFalhou, setEnvioFalhou] = useState(false);
  /** A coluna Não será feita no Quadro: só a tela decide, o servidor já manda todas. */
  const [naoSeraFeita, setNaoSeraFeita] = useState(false);
  const [desenvolvedores, setDesenvolvedores] = useState<Desenvolvedor[]>([]);
  /** O filtro Projeto (issue #1715, ADR 0093, decisão 8): abre em Todos e lista os projetos com Demanda (issue #1967). */
  const projetos = useProjetosDoFiltro(token);
  const opcoesDeProjeto = [
    { value: "", label: "Todos" },
    ...projetos.map((p) => ({ value: p.valor, label: p.nome })),
  ];
  /** O último pedido da lista: a resposta de um pedido mais velho não sobrescreve a do novo. */
  const ultimoPedido = useRef(0);
  /** A Demanda que a tela pôs no endereço, ou já tratou dele: o mesmo id não abre de novo. */
  const noEndereco = useRef<string | null>(null);
  /** O endereço trouxe uma Demanda fora da lista de quem abriu (issue #1586). */
  const [semAcesso, setSemAcesso] = useState(false);

  // Sem resposta, a tela fica como a do diretor: o filtro só aparece com o
  // sim do servidor.
  useEffect(() => {
    if (!token) return;
    let viva = true;
    (async () => {
      let sim = false;
      try {
        const resposta = await fetch(URL_QUEM_SOU, { headers: { Authorization: `Bearer ${token}` } });
        if (resposta.ok) {
          const corpo: unknown = await resposta.json();
          sim = (corpo as { desenvolvedor?: unknown })?.desenvolvedor === true;
        }
      } catch (e) {
        console.error("[admin/tecnologia] falha ao saber quem está logado", e);
      }
      if (!viva) return;
      setDesenvolvedor(sim);
      setFiltro(sim ? "para_mim" : "minhas");
    })();
    return () => {
      viva = false;
    };
  }, [token]);

  // Os nomes do chip Responsável, só para o Desenvolvedor.
  useEffect(() => {
    if (!token || !desenvolvedor) return;
    let viva = true;
    (async () => {
      try {
        const resposta = await fetch(URL_DOS_DESENVOLVEDORES, { headers: { Authorization: `Bearer ${token}` } });
        if (!resposta.ok) return;
        const lidos = desenvolvedoresValidos(await resposta.json());
        if (viva) setDesenvolvedores(lidos);
      } catch (e) {
        console.error("[admin/tecnologia] falha ao listar quem cuida", e);
      }
    })();
    return () => {
      viva = false;
    };
  }, [token, desenvolvedor]);

  useEffect(() => {
    const espera = setTimeout(() => setBusca(textoDaBusca.trim()), ESPERA_DA_BUSCA_MS);
    return () => clearTimeout(espera);
  }, [textoDaBusca]);

  /** Relê a lista e devolve o que veio; nulo quando não deu. */
  const carregar = useCallback(async (): Promise<Demanda[] | null> => {
    if (!token || filtro === null) return null;
    // Na tela larga a Etapa é a coluna, e a barra não tem o campo (ADR 0090, decisão 8).
    const url = urlDaLista({ recorte: filtro, busca, tipo, etapa: largo ? null : etapa, origem, projeto, responsavel, envioFalhou });
    const pedido = ++ultimoPedido.current;
    try {
      const resposta = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (pedido !== ultimoPedido.current) return null;
      if (!resposta.ok) {
        setErroDaLista(LISTA_FALHOU);
        return null;
      }
      const corpo: unknown = await resposta.json();
      if (pedido !== ultimoPedido.current) return null;
      if (!Array.isArray(corpo)) {
        setErroDaLista(LISTA_FALHOU);
        return null;
      }
      const lidas = corpo.filter(itemValido);
      setDemandas(lidas);
      setErroDaLista(null);
      return lidas;
    } catch (e) {
      console.error("[admin/tecnologia] falha ao carregar os pedidos", e);
      setErroDaLista(FALHA_DE_CONEXAO);
      return null;
    }
  }, [token, filtro, busca, tipo, etapa, largo, origem, projeto, responsavel, envioFalhou]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  /** Escreve no endereço e lembra o que escreveu, para o eco do endereço não reabrir o card. */
  const escreverNoEndereco = useCallback((demandaId: string | null) => {
    noEndereco.current = demandaId;
    demandaNoEndereco(demandaId);
  }, []);

  const abrir = useCallback(
    (demanda: Demanda, ampliar = false) => {
      // Na tela larga, o Documento do card abre no painel, por cima do Quadro;
      // o Ampliar segue na largura toda (issue #1643).
      const painel = largo && !ampliar;
      escreverNoEndereco(demanda.id);
      setSemAcesso(false);
      setAberta(demanda);
      setDestacada(demanda.id);
      setAmpliada(ampliar);
      setNoPainel(painel);
      setNaTela(painel ? "lista" : "pedido");
    },
    [escreverNoEndereco, largo],
  );

  /** Fecha o painel, tira a Demanda do endereço e devolve o foco ao card que o abriu. */
  const fecharPainel = useCallback(() => {
    const id = aberta?.id;
    escreverNoEndereco(null);
    setNoPainel(false);
    setAberta(null);
    setDestacada(null);
    const cards = quadroRef.current?.querySelectorAll<HTMLElement>("[data-demanda]") ?? [];
    Array.from(cards)
      .find((card) => card.dataset.demanda === id)
      ?.focus();
  }, [aberta, escreverNoEndereco]);

  const painelAberto = largo && naTela === "lista" && noPainel && aberta !== null;

  // Esc fecha o painel. Fica de fora o Esc que outra peça já tratou e o de um
  // diálogo por cima.
  useEffect(() => {
    if (!painelAberto) return;
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key !== "Escape" || evento.defaultPrevented) return;
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      fecharPainel();
    }
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [painelAberto, fecharPainel]);

  const filtroAtivo = Boolean(
    textoDaBusca.trim() ||
      tipo ||
      (!largo && etapa) ||
      origem ||
      projeto ||
      responsavel ||
      envioFalhou ||
      (largo && naoSeraFeita),
  );

  /** Volta a barra ao padrão. O recorte fica: ele é a vista do Desenvolvedor, não um filtro. */
  function limparFiltros() {
    setTextoDaBusca("");
    setBusca("");
    setTipo(null);
    setEtapa(null);
    setOrigem(null);
    setProjeto(null);
    setResponsavel(null);
    setEnvioFalhou(false);
    setNaoSeraFeita(false);
  }

  // A Demanda do endereço (o aviso antigo do sino, o e-mail, o recarregar):
  // abre se está na lista; se o filtro a esconde, a barra vai ao recorte mais
  // largo e a lista relê; se nem lá ela está, o aviso de sem acesso.
  useEffect(() => {
    const alvo = demandaInicial;
    if (!alvo || alvo === noEndereco.current || demandas === null || filtro === null) return;
    const achada = demandas.find((d) => d.id === alvo);
    if (achada) {
      abrir(achada);
      return;
    }
    const maisLargo: Filtro = desenvolvedor ? "todas" : "minhas";
    if (filtro !== maisLargo || filtroAtivo) {
      setTextoDaBusca("");
      setBusca("");
      setTipo(null);
      setEtapa(null);
      setOrigem(null);
      setProjeto(null);
      setResponsavel(null);
      setEnvioFalhou(false);
      setNaoSeraFeita(false);
      setFiltro(maisLargo);
      setDemandas(null);
      return;
    }
    noEndereco.current = alvo;
    setSemAcesso(true);
    setAberta(null);
    setDestacada(null);
    setAmpliada(false);
    setNoPainel(false);
    setNaTela("pedido");
  }, [demandaInicial, demandas, filtro, desenvolvedor, filtroAtivo, abrir]);

  /**
   * A lista recolhe na tela média só com o pedido ampliado (issue #1593, que
   * reverteu a #1551). Na tela larga, o que se abre na largura toda a partir
   * do Quadro (o Ampliar, o aviso de sem acesso) a ocupa inteira.
   */
  const recolhida = naTela === "pedido" && (largo || (aberta !== null && ampliada));
  /** Na tela larga o Quadro sai de cena quando algo abre na largura toda. */
  const quadroAVista = largo && naTela === "lista";

  /** A falha e o carregando, os mesmos na lista e no Quadro. */
  const estadoDaLista = (
    <>
      {erroDaLista && (
        <p role="alert" className="px-3 py-2 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          {erroDaLista}
        </p>
      )}
      {demandas === null && !erroDaLista && (
        <p role="status" className="flex items-center gap-2 px-1 text-xs text-text-secondary">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Carregando os pedidos...
        </p>
      )}
    </>
  );

  return (
    <div className="space-y-4">
      <section
        role="region"
        aria-label="Filtros da lista"
        className={`${naTela === "lista" ? "" : "hidden"} ${recolhida ? "md:hidden" : "md:block"} rounded-2xl border border-border bg-white shadow-sm p-4 space-y-4`}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1 min-w-0">
            <Search aria-hidden="true" className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="search"
              aria-label="Buscar pelo título"
              placeholder="Buscar pelo título"
              value={textoDaBusca}
              onChange={(e) => setTextoDaBusca(e.target.value)}
              className="w-full min-h-[38px] pl-9 pr-3 py-2 rounded-lg border border-slate-200 text-sm normal-case bg-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            />
          </div>
          {desenvolvedor && <RecorteDaLista valor={filtro} onMudar={setFiltro} />}
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Select
            label="Tipo"
            value={tipo ?? ""}
            options={OPCOES_DE_TIPO}
            onChange={(valor) => setTipo((valor || null) as Classificacao | null)}
          />
          {!largo && (
            <Select
              label="Etapa"
              value={etapa ?? ""}
              options={OPCOES_DE_ETAPA}
              onChange={(valor) => setEtapa((valor || null) as EtapaDemanda | null)}
            />
          )}
          <Select
            label="Origem"
            value={origem ?? ""}
            options={OPCOES_DE_ORIGEM}
            onChange={(valor) => setOrigem((valor || null) as Origem | null)}
          />
          <Select
            label="Projeto"
            value={projeto ?? ""}
            options={opcoesDeProjeto}
            onChange={(valor) => setProjeto((valor || null) as Projeto | null)}
          />
          {desenvolvedor && desenvolvedores.length > 0 && (
            <Select
              label="Responsável"
              value={responsavel ?? ""}
              options={[{ value: "", label: "Todos" }, ...desenvolvedores.map((d) => ({ value: d.id, label: d.nome }))]}
              onChange={(valor) => setResponsavel(valor || null)}
            />
          )}
        </div>
        {(desenvolvedor || largo || filtroAtivo) && (
          <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-3">
            {desenvolvedor && <InterruptorDaBarra rotulo={SO_ENVIO_FALHOU} ligado={envioFalhou} onMudar={setEnvioFalhou} />}
            {largo && (
              <InterruptorDaBarra
                rotulo={MOSTRAR_AS_QUE_NAO_SERAO_FEITAS}
                ligado={naoSeraFeita}
                onMudar={setNaoSeraFeita}
              />
            )}
            {filtroAtivo && (
              <button
                type="button"
                onClick={limparFiltros}
                className="ml-auto inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
              >
                <X aria-hidden="true" className="w-3.5 h-3.5" />
                {LIMPAR_FILTROS}
              </button>
            )}
          </div>
        )}
      </section>

      <div
        className={`md:grid ${recolhida || largo ? "md:grid-cols-1" : "md:grid-cols-[24rem_minmax(0,1fr)]"} md:gap-6 md:items-start`}
      >
        <div className={`${naTela === "lista" ? "" : "hidden"} ${recolhida ? "md:hidden" : "md:block"}`}>
          {largo ? (
            quadroAVista && (
              <div ref={quadroRef} className="space-y-3">
                {estadoDaLista}
                {demandas !== null && (
                  <QuadroDaTecnologia
                    demandas={demandas}
                    comNaoSeraFeita={naoSeraFeita}
                    onAbrir={(demanda) => abrir(demanda)}
                    onVerEntregas={onVerEntregas}
                  />
                )}
              </div>
            )
          ) : (
            <nav aria-label="Pedidos" className="md:max-h-[calc(100vh-18rem)] md:overflow-y-auto p-1 -m-1">
              {estadoDaLista}
              {demandas !== null && demandas.length === 0 && (
                <p className="px-1 text-sm text-text-secondary">{LISTA_VAZIA}</p>
              )}
              {demandas !== null && demandas.length > 0 && (
                <ul className="space-y-3">
                  {demandas.map((demanda) => (
                    <li key={demanda.id}>
                      <CardDaConversa
                        demanda={demanda}
                        destacada={destacada === demanda.id}
                        onAbrir={() => abrir(demanda)}
                        onAmpliar={() => abrir(demanda, true)}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </nav>
          )}
        </div>

        {!quadroAVista && (
          <div
            role="region"
            aria-label="Pedido na tela"
            className={`${naTela === "pedido" ? "" : "hidden"} md:block min-w-0 space-y-3`}
          >
            <button
              type="button"
              onClick={() => {
                // Ampliado na tela média, o Voltar traz a lista e o pedido segue aberto
                // ao lado. Na tela larga, o Quadro volta e a Demanda sai do endereço.
                if (largo || !recolhida) escreverNoEndereco(null);
                setSemAcesso(false);
                setNaTela("lista");
              }}
              className={`${recolhida || semAcesso ? "" : "md:hidden"} inline-flex items-center gap-1.5 text-sm font-semibold text-primary`}
            >
              <ArrowLeft className="w-4 h-4" />
              {largo ? VOLTAR_AO_QUADRO : VOLTAR_PARA_A_LISTA}
            </button>
            {aberta && !recolhida && (
              <button
                type="button"
                onClick={() => {
                  setAmpliada(true);
                  setNaTela("pedido");
                }}
                title={AMPLIAR_EXPLICADO}
                className="hidden md:inline-flex items-center gap-1.5 text-sm font-semibold text-primary"
              >
                <Maximize2 className="w-4 h-4" />
                {AMPLIAR}
              </button>
            )}
            {semAcesso ? (
              <p role="alert" className="px-4 py-3 rounded-2xl border border-border bg-white text-sm text-text">
                {SEM_ACESSO}
              </p>
            ) : (
              aberta && <Acompanhamento demanda={aberta} />
            )}
          </div>
        )}
      </div>

      {/* Portal no body: o wrapper .animate-fade-in-up do módulo deixa um transform
          aplicado, e ele prenderia o `fixed` à caixa do módulo em vez da janela.
          O `top-16` é a altura da barra do topo (Header, `h-16`, camada 100): o painel
          começa embaixo dela, senão a barra cobre o Ampliar e o Fechar (#1686). */}
      {painelAberto &&
        aberta &&
        createPortal(
        <aside
          aria-label="Pedido aberto"
          className="fixed top-16 bottom-0 right-0 z-40 w-[min(40rem,100vw)] overflow-y-auto border-l border-border bg-bg shadow-premium-strong p-5 space-y-3 animate-fade-in-right"
        >
          <div className="flex items-center gap-2">
            <span className="normal-case mr-auto text-xs text-text-secondary">{textoDaAbertura(aberta.criado_em)}</span>
            <button
              type="button"
              onClick={() => {
                setNoPainel(false);
                setAmpliada(true);
                setNaTela("pedido");
              }}
              title={AMPLIAR_EXPLICADO}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-semibold text-primary hover:bg-primary/5"
            >
              <Maximize2 className="w-4 h-4" />
              {AMPLIAR}
            </button>
            <button
              type="button"
              onClick={fecharPainel}
              aria-label={FECHAR_O_PAINEL}
              title={FECHAR_O_PAINEL}
              className="w-9 h-9 inline-flex items-center justify-center rounded-xl text-text-secondary hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <Acompanhamento demanda={aberta} />
        </aside>,
          document.body,
        )}
    </div>
  );
}
