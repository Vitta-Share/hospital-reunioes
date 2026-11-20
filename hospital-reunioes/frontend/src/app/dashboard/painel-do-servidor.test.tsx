/**
 * @vitest-environment jsdom
 */

/**
 * O painel de Reuniões lê o endpoint do servidor (issue #1868).
 *
 * Antes, a tela buscava 200 Pendências e 200 Reuniões e contava no navegador,
 * e os números deixavam de fora o que passava disso. Agora os cards, o gráfico
 * e as listas dos cards vêm prontos de `/api/pendencias/painel`, da base
 * inteira. O painel não tem alerta nem fila: quem procura o que depende dele
 * vai ao Início. Na lista de Atas que aguardam assinatura, o Facilitador vê
 * quem falta assinar e o botão Cobrar.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "./page";

const roteador = vi.hoisted(() => ({ push: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => roteador,
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

const PAINEL = {
  cards: {
    atas_paradas: 0,
    aguardam_assinatura: 1,
    atrasadas: 1234,
    vencem_em_3_dias: 7,
    conformidade: 40,
    ativas: 2057,
  },
  situacoes: { pendente: 800, em_progresso: 23, concluido: 10, atrasado: 1234, repactuada: 0, cancelado: 0 },
  por_setor: [],
  atas_paradas: [],
  aguardam_assinatura: [
    {
      id_reuniao: "R1",
      data: "2026-11-10",
      tipo: "Gerencial",
      objetivo: "Indicadores",
      status_ata: "AGUARDANDO_ASSINATURA",
      updated_at: "2026-11-12T10:00:00+00:00",
      pode_cobrar: true,
    },
  ],
};

const STATUS_DOS_SIGNATARIOS = {
  total: 2,
  assinaram: 1,
  signatarios: [
    { signer_id: "s-ana", nome: "Ana Lima", email: "ana@x", status: "signed" },
    { signer_id: "s-bruno", nome: "Bruno Reis", email: "bruno@x", status: "pending" },
  ],
};

function chamadas(): { url: string; metodo: string }[] {
  return vi.mocked(fetch).mock.calls.map(([url, init]) => ({
    url: String(url),
    metodo: (init as RequestInit | undefined)?.method ?? "GET",
  }));
}

beforeEach(() => {
  roteador.push.mockClear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      let corpo: unknown = [];
      if (url.startsWith("/api/pendencias/painel")) corpo = PAINEL;
      else if (url === "/api/reunioes/R1/signatarios/status") corpo = STATUS_DOS_SIGNATARIOS;
      else if (url === "/api/reunioes/R1/signatarios/cobrar" && init?.method === "POST")
        corpo = { cobrados: ["Bruno Reis"], falharam: [] };
      return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("painel de Reuniões", () => {
  it("usa o endpoint do painel e não busca mais 200 linhas", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("1234 atrasadas", { exact: false })).toBeTruthy();
    });
    const vencem = document.getElementById("vencem-3dias") as HTMLElement;
    expect(within(vencem).getByText("7")).toBeTruthy();
    expect(screen.getByText("40%")).toBeTruthy();

    const urls = chamadas().map((c) => c.url);
    expect(urls.some((u) => u.startsWith("/api/pendencias/painel"))).toBe(true);
    expect(urls.filter((u) => u.includes("limit=200"))).toEqual([]);
    expect(urls.filter((u) => u.startsWith("/api/reunioes?") || u.startsWith("/api/pendencias?"))).toEqual([]);
  });

  it("não mostra alerta nem fila e leva ao Início quem procura o que depende dele", async () => {
    render(<DashboardPage />);

    const link = await screen.findByRole("link", { name: /o que depende de você/i });
    expect(link.getAttribute("href")).toBe("/inicio");
    expect(screen.queryByText(/minha fila/i)).toBeNull();
    expect(screen.queryByText(/48 ?h/i)).toBeNull();
  });

  it("mostra quem falta assinar e o Cobrar reenvia o pedido", async () => {
    render(<DashboardPage />);
    const card = document.getElementById("aguardam-assinatura") as HTMLElement;
    await waitFor(() => {
      expect(within(card).getByText("1")).toBeTruthy();
    });
    fireEvent.click(card);

    const modal = screen.getByRole("dialog", { name: "Aguardam Assinatura" });
    await within(modal).findByText(/Falta assinar: Bruno Reis/);
    expect(within(modal).queryByText(/Ana Lima/)).toBeNull();

    fireEvent.click(within(modal).getByRole("button", { name: /Cobrar/ }));

    await within(modal).findByText(/Pedido reenviado para Bruno Reis/);
    expect(chamadas()).toContainEqual({ url: "/api/reunioes/R1/signatarios/cobrar", metodo: "POST" });
  });
});
