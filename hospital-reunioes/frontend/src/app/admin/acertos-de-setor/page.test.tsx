/**
 * @vitest-environment jsdom
 */

/**
 * A tela de acertos de setor do Super admin (issue #1861).
 *
 * Lista as Reuniões e os responsáveis sem setor e deixa preencher cada um.
 * Preenchido, o item sai da lista. O gate de acesso (403 para quem não é Super
 * admin) mora no backend e no layout do Admin; aqui o que se prova é a tela.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/Toast";

import AcertosDeSetorPage from "./page";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ token: "token-de-teste", loading: false }),
}));

type Chamada = { endereco: string; metodo: string; corpo: Record<string, unknown> | null };

const LISTA = {
  reunioes: [{ id_reuniao: "RD_SEM", titulo: "Reunião antiga", data: "2026-03-10", tipo: "Gerencial" }],
  responsaveis: [{ id: "P_SEM", nome_completo: "Carla Sem Setor", cargo: "Enfermeira", email: "c@hsm.com" }],
};

function montar(lista = LISTA) {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (endereco: string, init?: RequestInit) => {
      chamadas.push({
        endereco,
        metodo: init?.method ?? "GET",
        corpo: init?.body ? JSON.parse(String(init.body)) : null,
      });
      const corpo =
        endereco === "/api/participantes/setores"
          ? ["Faturamento", "UTI Adulto"]
          : endereco === "/api/admin/acertos-de-setor"
            ? lista
            : { ok: true };
      return { ok: true, status: 200, json: async () => corpo } as unknown as Response;
    }),
  );
  render(
    <ToastProvider>
      <AcertosDeSetorPage />
    </ToastProvider>,
  );
  return chamadas;
}

async function preencher(linhaTexto: string, setor: string) {
  const linha = (await screen.findByText(linhaTexto)).closest("li") as HTMLElement;
  fireEvent.click(within(linha).getByRole("combobox"));
  fireEvent.click(await screen.findByRole("option", { name: setor }));
  fireEvent.click(within(linha).getByRole("button", { name: "Salvar" }));
}

beforeEach(() => {
  // O jsdom não implementa `scrollIntoView`, que o `Select` da casa chama ao abrir.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Acertos de setor", () => {
  it("lista as Reuniões e os responsáveis sem setor", async () => {
    montar();

    const reunioes = await screen.findByRole("region", { name: "Reuniões sem setor" });
    const responsaveis = screen.getByRole("region", { name: "Responsáveis sem setor" });
    expect(within(reunioes).getByText("Reunião antiga")).toBeTruthy();
    expect(within(responsaveis).getByText("Carla Sem Setor")).toBeTruthy();
  });

  it("preencher o setor da Reunião grava e tira ela da lista", async () => {
    const chamadas = montar();

    await preencher("Reunião antiga", "UTI Adulto");

    await waitFor(() => expect(screen.queryByText("Reunião antiga")).toBeNull());
    const gravou = chamadas.find((c) => c.metodo === "PATCH");
    expect(gravou?.endereco).toBe("/api/admin/acertos-de-setor/reunioes/RD_SEM");
    expect(gravou?.corpo).toEqual({ setor: "UTI Adulto" });
  });

  it("preencher o setor do responsável grava e tira ele da lista", async () => {
    const chamadas = montar();

    await preencher("Carla Sem Setor", "Faturamento");

    await waitFor(() => expect(screen.queryByText("Carla Sem Setor")).toBeNull());
    const gravou = chamadas.find((c) => c.metodo === "PATCH");
    expect(gravou?.endereco).toBe("/api/admin/acertos-de-setor/responsaveis/P_SEM");
    expect(gravou?.corpo).toEqual({ setor: "Faturamento" });
  });

  it("lista vazia diz que não falta nada", async () => {
    montar({ reunioes: [], responsaveis: [] });

    const reunioes = await screen.findByRole("region", { name: "Reuniões sem setor" });
    expect(within(reunioes).getByText(/Nenhuma reunião sem setor/)).toBeTruthy();
  });
});
