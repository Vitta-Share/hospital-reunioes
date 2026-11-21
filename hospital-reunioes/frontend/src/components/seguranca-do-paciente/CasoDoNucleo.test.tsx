/**
 * @vitest-environment jsdom
 */

/**
 * O caso do Núcleo aberto (issue #1997). É a tela que o e-mail de ciência da
 * Ouvidoria abre, com login: abrir já é o Recebido, e quem decide isso é o
 * servidor. O que se trava aqui é o que a tela mostra do caso.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CasoDoNucleo } from "./CasoDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const DA_OUVIDORIA = {
  id: "n7",
  protocolo: "NSP-2026-0007",
  estado: "recebida",
  origem: "ouvidoria",
  relato: "Minha mãe caiu da cama na madrugada e ninguém veio ajudar.",
  justificativa_tecnica: "Queda do leito, internação, madrugada. Dano relatado: escoriação.",
  leito_ou_atendimento: null,
  setor_id: "setor-1",
  setor: "Clínica Médica",
  data_ocorrencia: "2026-11-18",
  turno: "noite",
  hora_aproximada: null,
  chegou_ao_paciente: null,
  grave_ou_morte: null,
  percebido_ou_reclamacao: null,
  criado_em: "2026-11-20T10:00:00+00:00",
  ouvidoria: { estado: "Em análise" },
};

let resposta: { ok: boolean; status: number; corpo: unknown };
const fetchMock = vi.fn(
  async () => ({ ok: resposta.ok, status: resposta.status, json: async () => resposta.corpo }) as Response
);

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  fetchMock.mockClear();
  vi.unstubAllGlobals();
});

describe("o caso do Núcleo", () => {
  it("abre o caso pelo id e mostra o relato e o que a Ouvidoria apurou", async () => {
    resposta = { ok: true, status: 200, corpo: DA_OUVIDORIA };
    render(<CasoDoNucleo id="n7" />);

    expect(await screen.findByRole("heading", { name: "NSP-2026-0007" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/nsp/notificacoes/n7", expect.anything());
    expect(screen.getByText(DA_OUVIDORIA.relato)).toBeTruthy();
    expect(screen.getByText(DA_OUVIDORIA.justificativa_tecnica)).toBeTruthy();
    expect(screen.getByText("Recebida")).toBeTruthy();
  });

  it("o caso que veio da Ouvidoria mostra o selo com o estado da manifestação", async () => {
    resposta = { ok: true, status: 200, corpo: DA_OUVIDORIA };
    render(<CasoDoNucleo id="n7" />);

    expect((await screen.findByTestId("selo-veio-da-ouvidoria")).textContent).toBe("Veio da Ouvidoria: Em análise");
  });

  it("o caso de outra origem não tem o selo nem o bloco da Ouvidoria", async () => {
    resposta = {
      ok: true,
      status: 200,
      corpo: { ...DA_OUVIDORIA, origem: "qr", ouvidoria: undefined, justificativa_tecnica: null },
    };
    render(<CasoDoNucleo id="n7" />);

    await screen.findByRole("heading", { name: "NSP-2026-0007" });
    expect(screen.queryByTestId("selo-veio-da-ouvidoria")).toBeNull();
    expect(screen.queryByText("O que a Ouvidoria apurou")).toBeNull();
  });

  it("a recusa do servidor aparece na tela", async () => {
    resposta = { ok: false, status: 404, corpo: { detail: "Caso não encontrado." } };
    render(<CasoDoNucleo id="n7" />);

    expect((await screen.findByRole("alert")).textContent).toContain("Caso não encontrado.");
  });
});
