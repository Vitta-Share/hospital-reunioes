/**
 * @vitest-environment jsdom
 */

/**
 * A fotografia semanal do painel (issue #1873).
 *
 * Toda segunda o servidor guarda os cards de cada pessoa. O painel mostra a
 * evolução das atrasadas nas semanas fotografadas e a seta de cada card, que
 * compara com a fotografia da semana anterior. Sem essa fotografia, sem seta.
 */

import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/participantes", () => ({
  fetchParticipantesAtivos: async () => [],
}));

vi.mock("@/components/dashboard/DashboardFilters", () => ({ default: () => null }));
vi.mock("@/components/dashboard/StatusPieChart", () => ({ default: () => null }));
vi.mock("@/components/dashboard/SetorBarChart", () => ({ default: () => null }));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: {
          session: {
            access_token: "token-de-teste",
            user: { id: "auth-user-1", email: "marta@hsm", user_metadata: {} },
          },
        },
      }),
      onAuthStateChange: () => ({
        data: { subscription: { unsubscribe: () => {} } },
      }),
    },
  }),
}));

const CARDS = {
  atas_paradas: 2,
  aguardam_assinatura: 1,
  atrasadas: 12,
  vencem_em_3_dias: 7,
  conformidade: 40,
  ativas: 20,
};

const PAINEL = {
  cards: CARDS,
  situacoes: { pendente: 8, em_progresso: 0, concluido: 0, atrasado: 12, repactuada: 0, cancelado: 0 },
  por_setor: [],
  atas_paradas: [],
  aguardam_assinatura: [],
  evolucao: [] as { semana: string; atrasadas: number }[],
  semana_anterior: null as typeof CARDS | null,
};

let painelAtual = PAINEL;

beforeEach(() => {
  painelAtual = PAINEL;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const corpo = url.startsWith("/api/pendencias/painel") ? painelAtual : [];
      return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function esperarOsCards() {
  render(<DashboardPage />);
  await waitFor(() => {
    expect(within(document.getElementById("vencem-3dias") as HTMLElement).getByText("7")).toBeTruthy();
  });
}

describe("fotografia semanal do painel", () => {
  it("sem a fotografia da semana anterior, nenhum card mostra seta", async () => {
    await esperarOsCards();

    expect(screen.queryAllByLabelText(/semana anterior/i)).toEqual([]);
  });

  it("com a fotografia da semana anterior, cada card mostra se subiu ou desceu", async () => {
    painelAtual = {
      ...PAINEL,
      semana_anterior: { ...CARDS, vencem_em_3_dias: 3, conformidade: 70, atas_paradas: 2, aguardam_assinatura: 4 },
    };
    await esperarOsCards();

    const vencem = document.getElementById("vencem-3dias") as HTMLElement;
    expect(within(vencem).getByLabelText("Subiu 4 desde a semana anterior")).toBeTruthy();
    const conformidade = document.getElementById("conformidade") as HTMLElement;
    expect(within(conformidade).getByLabelText("Caiu 30 desde a semana anterior")).toBeTruthy();
    const paradas = document.getElementById("atas-paradas") as HTMLElement;
    expect(within(paradas).getByLabelText("Igual à semana anterior")).toBeTruthy();
    const assinatura = document.getElementById("aguardam-assinatura") as HTMLElement;
    expect(within(assinatura).getByLabelText("Caiu 3 desde a semana anterior")).toBeTruthy();
  });

  it("a evolução mostra as atrasadas de cada semana fotografada", async () => {
    painelAtual = {
      ...PAINEL,
      evolucao: [
        { semana: "2026-11-02", atrasadas: 9 },
        { semana: "2026-11-16", atrasadas: 12 },
      ],
    };
    await esperarOsCards();

    const evolucao = screen.getByRole("region", { name: "Evolução das atrasadas" });
    const semanas = within(evolucao).getAllByRole("listitem");
    expect(semanas.map((s) => s.getAttribute("aria-label"))).toEqual([
      "Semana de 02/11: 9 atrasadas",
      "Semana de 16/11: 12 atrasadas",
    ]);
  });

  it("sem nenhuma semana fotografada, a evolução diz quando começa", async () => {
    await esperarOsCards();

    const evolucao = screen.getByRole("region", { name: "Evolução das atrasadas" });
    expect(within(evolucao).queryAllByRole("listitem")).toEqual([]);
    expect(within(evolucao).getByText(/começa a contar na próxima segunda/i)).toBeTruthy();
  });
});
