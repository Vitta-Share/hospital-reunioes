/**
 * @vitest-environment jsdom
 */

/**
 * A tela da aba Tecnologia (issue #636, PRD #634; ADR 0050).
 *
 * Desde a issue #2279 (ADR 0113, decisões 6 e 7) a aba só informa: as abas
 * Quadro e Entregas, sem o chat do Assistente, sem o "Novo pedido" e sem a
 * lista Esperando você. O pedido nasce no GitHub.
 */

import { readdirSync } from "node:fs";
import { join, relative, resolve } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import { TecnologiaModulo } from "./TecnologiaModulo";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ token: "token-de-teste", userId: "auth-1", userEmail: "p1@hsm", loading: false }),
}));

let pedidos: string[] = [];

const DEMANDA = {
  id: "d-1",
  titulo: "O relatório some",
  criado_em: "2026-11-01T10:00:00Z",
  etapa: "em_analise",
  tem_vinculo: true,
  o_que_muda: null,
  partes: [],
};

function montar({ largo = false, demandas = [DEMANDA] }: { largo?: boolean; demandas?: unknown[] } = {}) {
  if (largo) {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((consulta: string) => ({
        matches: consulta === "(min-width: 1280px)",
        media: consulta,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    );
  }
  pedidos = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      pedidos.push(url);
      const corpo = url.endsWith("/eu")
        ? { desenvolvedor: false }
        : url.includes("/entregas")
          ? {
              topo: {
                pedidos: { total: 0, anteriores: 0, bugs: 0, melhorias: 0 },
                entregas: { total: 0, anteriores: 0, g: 0, m: 0, p: 0 },
              },
              semanas: [],
              grupos: [],
              responsaveis: [],
            }
          : url.endsWith("/projetos")
            ? []
            : demandas;
      return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
    }),
  );
  render(
    <ToastProvider>
      <TecnologiaModulo />
    </ToastProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** As páginas da área `/admin/tecnologia`, lidas do disco: no Next, a pasta com `page.tsx` é a rota. */
function paginasDaAba(): string[] {
  const raiz = resolve(process.cwd(), "src/app/admin/tecnologia");
  const achadas: string[] = [];
  const visitar = (pasta: string) => {
    for (const entrada of readdirSync(pasta, { withFileTypes: true })) {
      const caminho = join(pasta, entrada.name);
      if (entrada.isDirectory()) visitar(caminho);
      else if (entrada.name === "page.tsx") achadas.push(relative(raiz, caminho));
    }
  };
  visitar(raiz);
  return achadas.sort();
}

describe("A aba só tem o Quadro e as Entregas (issue #2279, ADR 0113, decisões 6 e 7)", () => {
  it.each([
    ["na tela larga", true],
    ["no celular", false],
  ])("%s, as abas são Quadro e Entregas, sem Novo pedido nem Esperando você", async (_onde, largo) => {
    montar({ largo });

    // O pedido carregou: a tela já está inteira, e o que falta não vai chegar.
    expect(await screen.findByText("O relatório some")).toBeTruthy();
    expect(screen.getAllByRole("tab").map((aba) => aba.textContent)).toEqual(["Quadro", "Entregas"]);
    expect(screen.getByRole("tab", { name: "Quadro" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.queryByRole("button", { name: /Novo pedido|Nova conversa/ })).toBeNull();
    expect(screen.queryByRole("region", { name: "Esperando você" })).toBeNull();
    expect(screen.queryByText(/Esperando você/)).toBeNull();
    // O chat do Assistente também saiu: nenhuma caixa para escrever ao agente.
    expect(screen.queryByRole("textbox", { name: /mensagem/i })).toBeNull();
  });

  it("só pede ao servidor as leituras da aba: a lista, quem está logado e os projetos", async () => {
    montar();

    await waitFor(() => expect(pedidos.length).toBe(3));
    expect([...pedidos].sort()).toEqual([
      "/api/admin/tecnologia/chat",
      "/api/admin/tecnologia/eu",
      "/api/admin/tecnologia/projetos",
    ]);
  });

  it("abre as Entregas, e o Quadro fica montado atrás da aba", async () => {
    montar();
    await screen.findByText("O relatório some");

    fireEvent.click(screen.getByRole("tab", { name: "Entregas" }));

    expect(screen.getByRole("tab", { name: "Entregas" }).getAttribute("aria-selected")).toBe("true");
    await waitFor(() => expect(pedidos.some((url) => url.startsWith("/api/admin/tecnologia/entregas"))).toBe(true));
    expect(await screen.findByText("Nenhuma entrega com esses filtros.")).toBeTruthy();
    expect(screen.getByText("O relatório some").closest("[hidden]")).not.toBeNull();
  });

  it("Ver todos nas Entregas, no pé da coluna Entregue, abre a aba Entregas (issue #1644)", async () => {
    montar({ largo: true });
    const quadro = await screen.findByRole("region", { name: "Quadro" });

    // Sempre à vista, mesmo com a coluna vazia: as Entregas guardam o que passou dos 30 dias.
    const entregue = within(quadro).getByRole("region", { name: "Entregue" });
    fireEvent.click(within(entregue).getByRole("button", { name: "Ver todos nas Entregas" }));

    expect(screen.getByRole("tab", { name: "Entregas" }).getAttribute("aria-selected")).toBe("true");
    expect(await screen.findByText("Nenhuma entrega com esses filtros.")).toBeTruthy();
    expect(quadro.closest("[hidden]")).not.toBeNull();
  });

  it("a área da Tecnologia só tem a página da aba", () => {
    const paginas = paginasDaAba();

    // O piso: a varredura enxerga a página que fica. Sem ele, uma pasta lida
    // errado passaria vazia por "não tem as páginas antigas".
    expect(paginas).toContain("page.tsx");
    expect(paginas).toEqual(["page.tsx"]);
  });
});
