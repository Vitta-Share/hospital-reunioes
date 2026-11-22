/**
 * @vitest-environment jsdom
 */

/**
 * O gráfico de atrasos por setor e o ranking de 90 dias no painel (issue
 * #1871). O endpoint só manda os dois para o Super admin e para quem facilita
 * ao menos uma Reunião; para o responsável vêm `null`, e o painel não mostra
 * ranking nenhum.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/participantes", () => ({ fetchParticipantesAtivos: async () => [] }));
vi.mock("@/components/dashboard/DashboardFilters", () => ({ default: () => null }));
vi.mock("@/components/dashboard/StatusPieChart", () => ({ default: () => null }));
vi.mock("@/components/dashboard/SetorBarChart", () => ({ default: () => null }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: { session: { access_token: "t", user: { id: "u", email: "x@hsm", user_metadata: {} } } },
      }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } }),
    },
  }),
}));

const BASE = {
  cards: { atas_paradas: 0, aguardam_assinatura: 0, atrasadas: 0, vencem_em_3_dias: 0, conformidade: 100, ativas: 0 },
  situacoes: { pendente: 0, em_progresso: 0, concluido: 0, atrasado: 0, repactuada: 0, cancelado: 0 },
  por_setor: [],
  atas_paradas: [],
  aguardam_assinatura: [],
};

function servir(corpo: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const json = url.startsWith("/api/pendencias/painel") ? corpo : [];
      return { ok: true, status: 200, json: async () => json } as unknown as Response;
    })
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ranking de atrasos no painel", () => {
  it("mostra o ranking e os atrasos por setor que o servidor mandou", async () => {
    servir({
      ...BASE,
      atrasos_por_setor: [
        { setor: "Farmácia", atrasadas: 1, repactuacoes_vencidas: 2, concluidas_com_atraso: 0, atrasos: 3, reaberturas: 1 },
      ],
      ranking: [
        {
          responsavel_id: "P_BRUNO",
          nome: "Bruno Reis",
          setor: "Farmácia",
          atrasadas: 1,
          repactuacoes_vencidas: 2,
          concluidas_com_atraso: 0,
          atrasos: 3,
          reaberturas: 1,
        },
      ],
    });
    render(<DashboardPage />);

    const ranking = await screen.findByRole("region", { name: "Ranking de atrasos" });
    const linha = within(ranking).getByText("Bruno Reis").closest("tr") as HTMLElement;
    expect(within(linha).getAllByRole("cell").map((c) => c.textContent)).toEqual([
      "Bruno Reis",
      "Farmácia",
      "1",
      "2",
      "0",
      "3",
      "1",
    ]);
    const setores = screen.getByRole("region", { name: "Atrasos por setor" });
    expect(within(setores).getByText("3 atrasos, 1 reabertura")).toBeTruthy();
  });

  it("mostra só os atrasos por setor quando o servidor não manda o ranking (o facilitador)", async () => {
    servir({
      ...BASE,
      atrasos_por_setor: [
        { setor: "Farmácia", atrasadas: 1, repactuacoes_vencidas: 2, concluidas_com_atraso: 0, atrasos: 3, reaberturas: 1 },
      ],
      ranking: null,
    });
    render(<DashboardPage />);

    const setores = await screen.findByRole("region", { name: "Atrasos por setor" });
    expect(within(setores).getByText("3 atrasos, 1 reabertura")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Ranking de atrasos" })).toBeNull();
  });

  it("não mostra ranking quando o servidor não manda (o responsável)", async () => {
    servir({ ...BASE, atrasos_por_setor: null, ranking: null });
    render(<DashboardPage />);

    await screen.findByRole("link", { name: /o que depende de você/i });
    await screen.findByText("100%");
    expect(screen.queryByRole("region", { name: "Ranking de atrasos" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Atrasos por setor" })).toBeNull();
  });
});
