/**
 * @vitest-environment jsdom
 */

/**
 * A página da aba Tecnologia lê o `?demanda=<id>` do endereço: é o link do
 * sino e do e-mail, e um aviso antigo ainda o traz (issue #2279, ADR 0113,
 * decisão 7). Ele abre a Demanda no Quadro. O `?pergunta=` do aviso antigo
 * da Pergunta da Vitta só abre a aba, porque a lista Esperando você saiu.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import TecnologiaPage from "./page";

let endereco = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => endereco,
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ token: "token-de-teste", userId: "auth-1", userEmail: "p1@hsm", loading: false }),
}));

const DEMANDAS = [
  {
    id: "d-1",
    titulo: "O relatório some",
    criado_em: "2026-11-01T10:00:00Z",
    etapa: "em_analise",
    tem_vinculo: true,
    o_que_muda: "O relatório volta a abrir.",
    partes: [],
  },
  {
    id: "d-2",
    titulo: "A escala some no domingo",
    criado_em: "2026-11-02T10:00:00Z",
    etapa: "planejada",
    tem_vinculo: true,
    o_que_muda: "A escala aparece no domingo.",
    partes: [],
  },
];

let pedidos: string[] = [];

function abrirNoEndereco(consulta: string, { largo }: { largo: boolean }) {
  endereco = new URLSearchParams(consulta);
  vi.stubGlobal(
    "matchMedia",
    vi.fn((media: string) => ({
      matches: largo && media === "(min-width: 1280px)",
      media,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  pedidos = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      pedidos.push(url);
      const corpo = url.endsWith("/eu") ? { desenvolvedor: false } : url.endsWith("/projetos") ? [] : DEMANDAS;
      return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
    }),
  );
  render(
    <ToastProvider>
      <TecnologiaPage />
    </ToastProvider>,
  );
}

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("A página da aba Tecnologia", () => {
  it("o ?demanda= do link de um aviso antigo abre a Demanda no painel do Quadro", async () => {
    abrirNoEndereco("demanda=d-2", { largo: true });

    const painel = await screen.findByRole("complementary", { name: "Pedido aberto" });
    expect(within(painel).getByRole("heading", { level: 2, name: "A escala some no domingo" })).toBeTruthy();
    expect(within(painel).getByText("A escala aparece no domingo.")).toBeTruthy();
    // A outra Demanda fica no Quadro, atrás do painel, e não abre.
    expect(within(painel).queryByText("O relatório some")).toBeNull();
    expect(screen.getByRole("region", { name: "Quadro" })).toBeTruthy();
  });

  it("no celular, o mesmo link abre a Demanda ao lado da lista", async () => {
    abrirNoEndereco("demanda=d-2", { largo: false });

    const aberto = await screen.findByRole("region", { name: "Acompanhamento do pedido" });
    expect(within(aberto).getByRole("heading", { level: 2, name: "A escala some no domingo" })).toBeTruthy();
  });

  it("o ?pergunta= de um aviso antigo abre a aba no Quadro, sem pedir a lista Esperando você", async () => {
    abrirNoEndereco("pergunta=p-2", { largo: true });

    expect(await within(await screen.findByRole("region", { name: "Quadro" })).findByText("O relatório some")).toBeTruthy();
    expect(screen.queryByRole("complementary", { name: "Pedido aberto" })).toBeNull();
    expect(pedidos.some((url) => url.includes("/perguntas"))).toBe(false);
  });
});
