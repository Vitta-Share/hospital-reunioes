/**
 * @vitest-environment jsdom
 */

/**
 * O cadastro de responsáveis mostra quem tem login no app (issue #1887, ADR
 * 0099 decisão 1): o ouvidor acha na linha "sem login" o e-mail digitado
 * errado, que deixaria o responsável sem ver os casos do setor.
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ResponsaveisDaOuvidoriaPage from "./page";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

vi.mock("@/hooks/useCurrentParticipante", () => ({
  useCurrentParticipante: () => ({
    participante: { id: "p1", perfil_ouvidoria: "ouvidor" },
    loading: false,
  }),
}));

const COM_LOGIN = {
  id: "r-helena",
  setor: "Recepcao",
  papel: "titular",
  nome: "Dra. Helena",
  email: "helena@hsm.br",
  vigencia_inicio: "2026-01-01",
  vigencia_fim: null,
  tem_login: true,
};

const SEM_LOGIN = {
  ...COM_LOGIN,
  id: "r-digitado-errado",
  papel: "substituto",
  nome: "Dr. Bruno",
  email: "bruno@hsm.com.br",
  tem_login: false,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function linhaDe(nome: string): HTMLElement {
  const linha = screen.getByText(nome).closest("li");
  if (!linha) throw new Error(`a linha de ${nome} não está numa <li>`);
  return linha;
}

describe("cada linha do cadastro diz se a pessoa tem login", () => {
  it("mostra tem login e sem login na linha de cada um", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        const corpo = String(url).endsWith("/ouvidoria/responsaveis")
          ? { responsaveis: [COM_LOGIN, SEM_LOGIN] }
          : [];
        return { ok: true, status: 200, json: async () => corpo } as Response;
      })
    );

    render(<ResponsaveisDaOuvidoriaPage />);
    await screen.findByText("Dra. Helena");

    expect(within(linhaDe("Dra. Helena")).getByText("tem login")).toBeTruthy();
    expect(within(linhaDe("Dra. Helena")).queryByText("sem login")).toBeNull();
    expect(within(linhaDe("Dr. Bruno")).getByText("sem login")).toBeTruthy();
    expect(within(linhaDe("Dr. Bruno")).queryByText("tem login")).toBeNull();
  });
});
