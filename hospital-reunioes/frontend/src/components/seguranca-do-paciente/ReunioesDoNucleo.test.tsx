/**
 * @vitest-environment jsdom
 */

/**
 * O item Reuniões de Segurança do Paciente (issue #1772, PRD #1764).
 *
 * O servidor decide quem vê e quem abre; a tela mostra o calendário mês a mês,
 * liga cada reunião à tela da ata só para quem pode abrir, e dá à Presidência
 * o formulário com os quatro tipos do Núcleo. Pessoas de teste, sem nome real.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReunioesDoNucleo, type ReuniaoDoNucleo } from "./ReunioesDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const TIPOS = ["Ordinária mensal", "Análise de evento", "Apresentação à Diretoria", "Reunião rápida de segurança"];

const REUNIAO: ReuniaoDoNucleo = {
  id_reuniao: "RD_20261120_1",
  data: "2026-11-20",
  hora_inicio: "09:00:00",
  tipo: "Ordinária mensal",
  titulo: "Reunião ordinária de novembro",
  status_ata: "PROGRAMADA",
};

let fetchMock: ReturnType<typeof vi.fn>;

function responder(corpo: object, status = 200) {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

function calendario(campos: { pode_abrir: boolean; pode_criar: boolean; reunioes?: ReuniaoDoNucleo[] }) {
  return { reunioes: [REUNIAO], tipos: TIPOS, ...campos };
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("o calendário do Núcleo", () => {
  it("mostra a reunião no mês dela, com a data, o tipo e o link para a ata", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: true, pode_criar: false })));
    render(<ReunioesDoNucleo />);

    const mes = await screen.findByRole("region", { name: "novembro de 2026" });
    expect(within(mes).getByText("20/11")).toBeTruthy();
    expect(within(mes).getByText("Ordinária mensal, 09:00")).toBeTruthy();
    const link = within(mes).getByRole("link");
    expect(link.getAttribute("href")).toBe("/reunioes/RD_20261120_1");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/nsp/reunioes");
  });

  it("o membro sem Termo vê a reunião, sem link para a ata", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: false, pode_criar: false })));
    render(<ReunioesDoNucleo />);

    expect(await screen.findByText("Reunião ordinária de novembro")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("A ata abre depois que você assina o Termo de Adesão.")).toBeTruthy();
  });

  it("sem reunião, diz que nenhuma está marcada", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: true, pode_criar: false, reunioes: [] })));
    render(<ReunioesDoNucleo />);

    expect(await screen.findByText("Nenhuma reunião do Núcleo marcada.")).toBeTruthy();
  });
});

describe("a Presidência cria a reunião", () => {
  it("só quem pode criar vê o botão", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: true, pode_criar: false })));
    render(<ReunioesDoNucleo />);

    await screen.findByText("Reunião ordinária de novembro");
    expect(screen.queryByRole("button", { name: "Nova reunião" })).toBeNull();
  });

  it("o formulário oferece os quatro tipos do Núcleo e manda o escolhido", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: true, pode_criar: true })));
    render(<ReunioesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Nova reunião" }));
    const form = screen.getByRole("form", { name: "Nova reunião do Núcleo" });
    const tipo = within(form).getByLabelText("Tipo") as HTMLSelectElement;
    expect([...tipo.options].map((o) => o.value)).toEqual(TIPOS);

    fireEvent.change(within(form).getByLabelText("Título"), { target: { value: "Análise da queda" } });
    fireEvent.change(within(form).getByLabelText("Data"), { target: { value: "2026-11-25" } });
    fireEvent.change(tipo, { target: { value: "Análise de evento" } });
    fetchMock.mockResolvedValueOnce(responder({ id_reuniao: "RD_NOVA", tipo: "Análise de evento" }, 201));
    fireEvent.submit(form);

    await waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const [rota, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(rota).toBe("/api/nsp/reunioes");
    expect(JSON.parse(init.body)).toEqual({
      titulo: "Análise da queda",
      data: "2026-11-25",
      tipo: "Análise de evento",
      hora_inicio: null,
    });
  });
});
