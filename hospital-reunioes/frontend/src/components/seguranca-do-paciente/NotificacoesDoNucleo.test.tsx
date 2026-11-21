/**
 * @vitest-environment jsdom
 */

/**
 * Notificações, a lista de casos do Núcleo (issue #1987).
 *
 * A tela não decide quem vê quem notificou: o servidor manda a identidade só
 * para a Presidência e o Acesso pleno, e a tela mostra o que vier. O que se
 * trava aqui é o que aparece de cada caso.
 */
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotificacoesDoNucleo } from "./NotificacoesDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const CASO = {
  id: "n1",
  protocolo: "NSP-2026-0001",
  estado: "recebida",
  origem: "qr",
  relato: "A bomba de infusão alarmou e ninguém ouviu.",
  leito_ou_atendimento: "Leito 4",
  setor_id: "setor-uti",
  setor: "UTI Adulto",
  data_ocorrencia: "2026-11-19",
  turno: "noite",
  hora_aproximada: null,
  chegou_ao_paciente: "com_dano",
  grave_ou_morte: true,
  percebido_ou_reclamacao: null,
  criado_em: "2026-11-20T10:00:00+00:00",
};

let corpo: unknown;

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => corpo }) as Response)
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a lista de casos", () => {
  it("mostra protocolo, setor, estado, origem, gravidade e relato de cada caso", async () => {
    corpo = { notificacoes: [CASO] };
    render(<NotificacoesDoNucleo />);

    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });
    expect(within(caso).getByText("UTI Adulto")).toBeTruthy();
    expect(within(caso).getByText("Recebida")).toBeTruthy();
    expect(within(caso).getByText("Pelo QR")).toBeTruthy();
    expect(within(caso).getByText("Grave ou houve morte")).toBeTruthy();
    expect(within(caso).getByText(CASO.relato)).toBeTruthy();
  });

  it("sem a identidade no corpo, não há linha de quem notificou", async () => {
    corpo = { notificacoes: [CASO] };
    render(<NotificacoesDoNucleo />);

    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });
    expect(within(caso).queryByText(/Notificado por/)).toBeNull();
  });

  it("com a identidade no corpo, mostra o nome ou Sem identificação", async () => {
    corpo = {
      notificacoes: [
        { ...CASO, anonimo: false, notificante: { nome: "Profissional de Teste", contato: "p@hsm.test" } },
        { ...CASO, id: "n2", protocolo: "NSP-2026-0002", anonimo: true, notificante: null },
      ],
    };
    render(<NotificacoesDoNucleo />);

    const identificada = await screen.findByRole("article", { name: "NSP-2026-0001" });
    expect(within(identificada).getByText("Notificado por Profissional de Teste (p@hsm.test)")).toBeTruthy();
    const anonima = screen.getByRole("article", { name: "NSP-2026-0002" });
    expect(within(anonima).getByText("Notificado sem identificação")).toBeTruthy();
  });

  it("o caso que veio da Ouvidoria mostra o selo com o estado da manifestação (issue #1997)", async () => {
    corpo = {
      notificacoes: [
        {
          ...CASO,
          origem: "ouvidoria",
          ouvidoria: { estado: "Respondida" },
          anonimo: false,
          notificante: null,
        },
      ],
    };
    render(<NotificacoesDoNucleo />);

    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });
    expect(within(caso).getByTestId("selo-veio-da-ouvidoria").textContent).toBe("Veio da Ouvidoria: Respondida");
    expect(within(caso).queryByText(/Notificado/)).toBeNull();
  });

  it("o caso que não veio da Ouvidoria não tem o selo", async () => {
    corpo = { notificacoes: [CASO] };
    render(<NotificacoesDoNucleo />);

    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });
    expect(within(caso).queryByTestId("selo-veio-da-ouvidoria")).toBeNull();
  });

  it("o protocolo abre o caso", async () => {
    corpo = { notificacoes: [CASO] };
    render(<NotificacoesDoNucleo />);

    const caso = await screen.findByRole("article", { name: "NSP-2026-0001" });
    expect(within(caso).getByRole("link", { name: "NSP-2026-0001" }).getAttribute("href")).toBe(
      "/seguranca-do-paciente/notificacoes/n1"
    );
  });

  it("sem casos, o estado vazio", async () => {
    corpo = { notificacoes: [] };
    render(<NotificacoesDoNucleo />);

    await waitFor(() => expect(screen.getByText("Nenhuma notificação ainda.")).toBeTruthy());
  });
});
