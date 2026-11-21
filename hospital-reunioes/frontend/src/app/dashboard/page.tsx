"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { fetchParticipantesAtivos } from "@/lib/participantes";
import KpiCards from "@/components/dashboard/KpiCards";
import type { ListaDoCard } from "@/components/dashboard/KpiCards";
import ListaAtasModal from "@/components/dashboard/ListaAtasModal";
import type { AtaDoDashboard } from "@/lib/reunioes/atasDoDashboard";
import DashboardFilters from "@/components/dashboard/DashboardFilters";
import StatusPieChart from "@/components/dashboard/StatusPieChart";
import SetorBarChart from "@/components/dashboard/SetorBarChart";
import type { SetorBarEntry } from "@/components/dashboard/SetorBarChart";
import type { PieEntry } from "@/components/dashboard/StatusPieChart";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Stats {
  atasParadas: number;
  aguardamAssinatura: number;
  atrasadas: number;
  vencemEm3Dias: number;
  conformidade: number; // 0-100
  totalPendencias: number;
}

// O que `/api/pendencias/painel` devolve (issue #1868): os números já
// contados no servidor, da base inteira e no recorte de quem pede.
interface PainelDoServidor {
  cards: {
    atas_paradas: number;
    aguardam_assinatura: number;
    atrasadas: number;
    vencem_em_3_dias: number;
    conformidade: number;
    ativas: number;
  };
  situacoes: {
    pendente: number;
    em_progresso: number;
    concluido: number;
    atrasado: number;
    repactuada: number;
  };
  por_setor: {
    setor: string;
    pendente: number;
    em_progresso: number;
    concluido: number;
    atrasado: number;
    repactuada: number;
  }[];
  atas_paradas: AtaDoDashboard[];
  aguardam_assinatura: AtaDoDashboard[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  Pendente: "#FFC067",      // Pastel Orange
  "Em Progresso": "#7CC2F2",// Pastel Blue
  Concluído: "#88D7A4",     // Pastel Green
  Atrasado: "#FC9D9D",      // Pastel Red
  Repactuada: "#C4B5FD",   // Pastel Purple
};

// ─── Main Component ───────────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter();

  const [stats, setStats] = useState<Stats | null>(null);
  const [nome, setNome] = useState("Usuário");
  const [loading, setLoading] = useState(false);
  const [participantes, setParticipantes] = useState<
    { id: string; nome_completo: string; setor?: string }[]
  >([]);
  const [token, setToken] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  // Filtros (arrays para multisseleção)
  const [filtroResponsaveis, setFiltroResponsaveis] = useState<string[]>([]);
  const [filtroPrazoDe, setFiltroPrazoDe] = useState<string>("");
  const [filtroPrazoAte, setFiltroPrazoAte] = useState<string>("");
  const [filtroSetores, setFiltroSetores] = useState<string[]>([]);

  // Lista de setores
  const [listaSetores, setListaSetores] = useState<string[]>([]);

  // Dados dos gráficos
  const [pieStats, setPieStats] = useState<PieEntry[]>([]);
  const [setorBarData, setSetorBarData] = useState<SetorBarEntry[]>([]);
  const [loadingCharts, setLoadingCharts] = useState(false);

  // Atas que os cards contam, e qual lista está aberta no modal (issue #1055)
  const [listasDeAtas, setListasDeAtas] = useState<Record<ListaDoCard, AtaDoDashboard[]>>({
    "atas-paradas": [],
    "aguardam-assinatura": [],
  });
  const [listaAberta, setListaAberta] = useState<ListaDoCard | null>(null);

  // Debounce ref
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initialLoadDone = useRef(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const supabase = createClient();
    // Usa ref (sobrevive ao double-effect do React StrictMode em dev) para
    // evitar que fetchAllData dispare duas vezes quando o listener
    // onAuthStateChange e o getSession() inicial chegam juntos.

    // A tela não fala com o PostgREST: `participantes` tem RLS default-deny
    // (migration 009) e nenhuma policy de SELECT, então a leitura direta do
    // navegador volta sempre vazia, e pedir uma linha só transformava isso num
    // 406 no console (issue #492). Quem precisa do papel do usuário usa o
    // `useCurrentParticipante`, que passa pelo backend.
    async function init(sessionToken: string) {
      setToken(sessionToken);

      fetchParticipantesAtivos<{ id: string; nome_completo: string; setor?: string }>(sessionToken)
        .then(setParticipantes)
        .catch((e) => console.error("Erro ao carregar participantes:", e));

      fetch(`/api/participantes/setores`, {
        headers: { Authorization: `Bearer ${sessionToken}` },
      })
        .then((res) => res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`)))
        .then((data) => {
          if (Array.isArray(data)) setListaSetores(data);
        })
        .catch((e) => console.error("Erro ao carregar setores:", e));

      return sessionToken;
    }

    // Listener para capturar sessão que pode chegar depois do redirect OAuth
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if ((event === "SIGNED_IN" || event === "TOKEN_REFRESHED") && session?.access_token && !initialLoadDone.current) {
          initialLoadDone.current = true;
          const meta = session.user.user_metadata as Record<string, unknown>;
          setNome(
            (meta?.nome as string) ||
              session.user.email?.split("@")[0] ||
              "Usuário"
          );
          const tk = await init(session.access_token);
          fetchAllData(tk);
        }
      }
    );

    // Tenta inicializar com a sessão atual
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (session?.access_token && !initialLoadDone.current) {
        initialLoadDone.current = true;
        const meta = session.user.user_metadata as Record<string, unknown>;
        setNome(
          (meta?.nome as string) ||
            session.user.email?.split("@")[0] ||
            "Usuário"
        );
        const tk = await init(session.access_token);
        fetchAllData(tk);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Constrói params de query com suporte a múltiplos valores (CSV)
  function buildParams() {
    const params = new URLSearchParams();
    if (filtroResponsaveis.length > 0) params.append("responsavel_id", filtroResponsaveis.join(","));
    if (filtroPrazoDe) params.append("prazo_de", filtroPrazoDe);
    if (filtroPrazoAte) params.append("prazo_ate", filtroPrazoAte);
    if (filtroSetores.length > 0) params.append("setor", filtroSetores.join(","));
    return params;
  }

  const fetchAllData = useCallback(
    async (tk?: string) => {
      const accessToken = tk ?? token;
      if (!accessToken) return;

      setLoadingCharts(true);
      setLoading(true);

      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        };

        const params = buildParams();
        const queryStr = params.toString() ? `?${params.toString()}` : "";

        // Um pedido só: o servidor lê a base inteira e conta (issue #1868).
        const painelRes = await fetch(`/api/pendencias/painel${queryStr}`, { headers });
        const corpo = painelRes.ok ? await painelRes.json() : null;
        const painel: PainelDoServidor | null = corpo && corpo.cards ? corpo : null;
        if (!painel) {
          setStats(null);
          return;
        }

        setListasDeAtas({
          "atas-paradas": painel.atas_paradas,
          "aguardam-assinatura": painel.aguardam_assinatura,
        });

        setStats({
          atasParadas: painel.cards.atas_paradas,
          aguardamAssinatura: painel.cards.aguardam_assinatura,
          atrasadas: painel.cards.atrasadas,
          vencemEm3Dias: painel.cards.vencem_em_3_dias,
          conformidade: painel.cards.conformidade,
          totalPendencias: painel.cards.ativas,
        });

        const sit = painel.situacoes;
        const pieData: PieEntry[] = [
          { name: "Pendente", value: sit.pendente, color: STATUS_COLORS.Pendente },
          { name: "Em Progresso", value: sit.em_progresso, color: STATUS_COLORS["Em Progresso"] },
          { name: "Concluído", value: sit.concluido, color: STATUS_COLORS.Concluído },
          { name: "Atrasado", value: sit.atrasado, color: STATUS_COLORS.Atrasado },
          { name: "Repactuada", value: sit.repactuada, color: STATUS_COLORS.Repactuada },
        ].filter((item) => item.value > 0);
        setPieStats(pieData);

        setSetorBarData(
          painel.por_setor.map((linha) => ({
            setor: linha.setor,
            Pendente: linha.pendente,
            "Em Progresso": linha.em_progresso,
            Concluído: linha.concluido,
            Atrasado: linha.atrasado,
            Repactuada: linha.repactuada,
          }))
        );
      } catch (e) {
        console.error("Erro ao carregar dashboard:", e);
      } finally {
        setLoading(false);
        setLoadingCharts(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      filtroResponsaveis,
      filtroPrazoDe,
      filtroPrazoAte,
      filtroSetores,

      token,
    ]
  );

  // Refetch com debounce ao mudar filtros (pula o primeiro trigger do token inicial)
  useEffect(() => {
    if (!token) return;
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchAllData();
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [
    filtroResponsaveis,
    filtroPrazoDe,
    filtroPrazoAte,
    filtroSetores,
    token,
    fetchAllData,
  ]);

  // ─── Navigation helper ────────────────────────────────────────────────────

  const today = new Date().toLocaleDateString("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  function navigateToPendencias(
    statusParam: string | null,
    overrides?: { setor?: string; responsavel_id?: string }
  ) {
    if (!statusParam && !overrides?.responsavel_id) return;

    const params = new URLSearchParams();
    if (statusParam === "CRITICAS") {
      params.append("criticas", "true");
    } else if (statusParam) {
      params.append("status", statusParam);
    }

    if (overrides?.responsavel_id) {
      params.append("responsavel", overrides.responsavel_id);
    } else if (filtroResponsaveis.length > 0) {
      params.append("responsavel", filtroResponsaveis.join(","));
    }

    if (overrides?.setor) {
      params.append("setor", overrides.setor);
    } else if (filtroSetores.length > 0) {
      params.append("setor", filtroSetores.join(","));
    }

    if (filtroPrazoDe) params.append("prazo_de", filtroPrazoDe);
    if (filtroPrazoAte) params.append("prazo_ate", filtroPrazoAte);

    router.push(`/pendencias?${params.toString()}`);
  }

  // Opções do MultiSelect responsável filtradas por setores selecionados
  const participantesFiltrados = useMemo(
    () =>
      participantes.filter(
        (p) =>
          filtroSetores.length === 0 ||
          (p.setor && filtroSetores.includes(p.setor))
      ),
    [participantes, filtroSetores]
  );

  const setoresOptions = useMemo(
    () => listaSetores.map((s) => ({ value: s, label: s })),
    [listaSetores]
  );

  const responsavelOptions = useMemo(
    () =>
      participantesFiltrados.map((p) => ({
        value: p.id,
        label: p.nome_completo,
      })),
    [participantesFiltrados]
  );

  return (
    <div className="max-w-7xl mx-auto animate-fade-in-up pb-10">
      {/* Welcome */}
      <div className="mb-8 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-text">Olá, <span className="normal-case">{nome}</span></h1>
          <p className="text-text-secondary mt-1 capitalize">
            {mounted ? today : ""}
          </p>
        </div>
        {/* O painel não tem fila própria: o que depende de cada um mora no Início (ADR 0104). */}
        <Link href="/inicio" className="text-sm font-medium text-primary hover:underline">
          O que depende de você está no Início
        </Link>
      </div>

      {/* Alert Cards */}
      <KpiCards
        stats={stats}
        loading={loading}
        onNavigate={(href) => router.push(href)}
        onAbrirLista={setListaAberta}
      />

      {listaAberta && (
        <ListaAtasModal
          titulo={listaAberta === "atas-paradas" ? "Atas Paradas" : "Aguardam Assinatura"}
          atas={listasDeAtas[listaAberta]}
          token={listaAberta === "aguardam-assinatura" ? token : null}
          onClose={() => setListaAberta(null)}
        />
      )}

      {/* Filtros Dinâmicos */}
      <DashboardFilters
        filtroSetores={filtroSetores}
        filtroResponsaveis={filtroResponsaveis}
        filtroPrazoDe={filtroPrazoDe}
        filtroPrazoAte={filtroPrazoAte}
        setoresOptions={setoresOptions}
        responsavelOptions={responsavelOptions}
        onSetFiltroSetores={setFiltroSetores}
        onSetFiltroResponsaveis={setFiltroResponsaveis}
        onSetFiltroPrazoDe={setFiltroPrazoDe}
        onSetFiltroPrazoAte={setFiltroPrazoAte}
        onReset={() => {
          setFiltroResponsaveis([]);
          setFiltroPrazoDe("");
          setFiltroPrazoAte("");
          setFiltroSetores([]);
        }}
      />

      {/* Chart Grid 2x2 — Layout A */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 1. Donut — Status das Pendências */}
        <StatusPieChart
          data={pieStats}
          loading={loadingCharts}
          onSliceClick={(statusEnum) => navigateToPendencias(statusEnum)}
        />

        {/* 2. Stacked Bar Horizontal — Pendências por Setor */}
        <SetorBarChart
          data={setorBarData}
          loading={loadingCharts}
          onBarClick={(statusEnum, setor) =>
            navigateToPendencias(statusEnum, { setor })
          }
        />
      </div>
    </div>
  );
}
