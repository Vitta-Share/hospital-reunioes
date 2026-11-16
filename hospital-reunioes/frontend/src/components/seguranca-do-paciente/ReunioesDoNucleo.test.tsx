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

describe("o calendário do ano e a pauta (issue #1773)", () => {
  it("a Presidência gera o calendário do ano com o dia e a hora escolhidos", async () => {
    fetchMock.mockImplementation(async (_rota: string, init?: RequestInit) =>
      init?.method === "POST"
        ? responder({ ano: 2027, criadas: Array.from({ length: 12 }, (_, i) => ({ id_reuniao: `R${i}` })), ja_existiam: [] }, 201)
        : responder(calendario({ pode_abrir: true, pode_criar: true })),
    );
    render(<ReunioesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Gerar o calendário do ano" }));
    const form = screen.getByRole("form", { name: "Calendário do ano" });
    fireEvent.change(within(form).getByLabelText("Ano"), { target: { value: "2027" } });
    fireEvent.change(within(form).getByLabelText("Dia do mês"), { target: { value: "15" } });
    fireEvent.change(within(form).getByLabelText("Hora"), { target: { value: "09:30" } });
    fireEvent.submit(form);

    expect(await screen.findByText("12 reuniões ordinárias criadas em 2027.")).toBeTruthy();
    const [rota, init] = fetchMock.mock.calls.find(([, i]) => i?.method === "POST")!;
    expect(rota).toBe("/api/nsp/reunioes/calendario");
    expect(JSON.parse(init.body)).toEqual({ ano: 2027, dia: 15, hora_inicio: "09:30" });
  });

  it("pedir de novo no mesmo ano avisa que nada foi criado", async () => {
    fetchMock.mockImplementation(async (_rota: string, init?: RequestInit) =>
      init?.method === "POST"
        ? responder({ ano: 2027, criadas: [], ja_existiam: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] }, 201)
        : responder(calendario({ pode_abrir: true, pode_criar: true })),
    );
    render(<ReunioesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Gerar o calendário do ano" }));
    const form = screen.getByRole("form", { name: "Calendário do ano" });
    fireEvent.change(within(form).getByLabelText("Ano"), { target: { value: "2027" } });
    fireEvent.submit(form);

    expect(await screen.findByText("O calendário de 2027 já tinha as doze ordinárias. Nada foi criado.")).toBeTruthy();
  });

  it("quem abre a ata abre também a pauta da reunião", async () => {
    fetchMock.mockImplementation(async (rota: string) =>
      rota.endsWith("/pauta")
        ? responder({ disponivel: false, disponivel_em: "2026-11-13", blocos: [] })
        : responder(calendario({ pode_abrir: true, pode_criar: false })),
    );
    render(<ReunioesDoNucleo />);

    fireEvent.click(await screen.findByRole("button", { name: "Pauta de Reunião ordinária de novembro" }));

    expect(await screen.findByText(/A pauta aparece em 13\/11\/2026/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(([r]) => r === "/api/nsp/reunioes/RD_20261120_1/pauta")).toBe(true);
  });

  it("o membro sem Termo não tem o botão da pauta", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: false, pode_criar: false })));
    render(<ReunioesDoNucleo />);

    await screen.findByText("Reunião ordinária de novembro");
    expect(screen.queryByRole("button", { name: /Pauta de/ })).toBeNull();
  });
});

describe("presença e reunião não instalada (issue #1774)", () => {
  const NAO_INSTALADA: ReuniaoDoNucleo = {
    ...REUNIAO,
    id_reuniao: "RD_20261110_1",
    data: "2026-11-10",
    titulo: "Ordinária sem quórum",
    status_ata: "NAO_INSTALADA",
  };

  it("a reunião sem quórum aparece como Não instalada", async () => {
    fetchMock.mockImplementation(async () =>
      responder(calendario({ pode_abrir: true, pode_criar: false, reunioes: [NAO_INSTALADA, REUNIAO] })),
    );
    render(<ReunioesDoNucleo />);

    const linha = (await screen.findByText("Ordinária sem quórum")).closest("li")!;
    expect(within(linha).getByText("Não instalada")).toBeTruthy();
    const outra = screen.getByText("Reunião ordinária de novembro").closest("li")!;
    expect(within(outra).queryByText("Não instalada")).toBeNull();
  });

  it("a Presidência abre a presença da reunião programada", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url === `/api/nsp/reunioes/${REUNIAO.id_reuniao}/presenca`) {
        return responder({
          id_reuniao: REUNIAO.id_reuniao,
          data: REUNIAO.data,
          status_ata: "PROGRAMADA",
          pessoas: [],
          quorum: { total: 0, presentes: 0, minimo: 0, presidencia_ou_suplente: false, instalada: false },
          pode_registrar: false,
        });
      }
      return responder(calendario({ pode_abrir: true, pode_criar: true, reunioes: [NAO_INSTALADA, REUNIAO] }));
    });
    render(<ReunioesDoNucleo />);

    const linha = (await screen.findByText("Reunião ordinária de novembro")).closest("li")!;
    const naoInstalada = screen.getByText("Ordinária sem quórum").closest("li")!;
    expect(within(naoInstalada).queryByRole("button", { name: "Presença" })).toBeNull();
    fireEvent.click(within(linha).getByRole("button", { name: "Presença" }));

    expect(await within(linha).findByText("Sem quórum: 0 presentes de 0, mínimo de 0.")).toBeTruthy();
  });

  it("quem não cria reunião não vê o botão da presença", async () => {
    fetchMock.mockImplementation(async () => responder(calendario({ pode_abrir: true, pode_criar: false })));
    render(<ReunioesDoNucleo />);

    await screen.findByText("Reunião ordinária de novembro");
    expect(screen.queryByRole("button", { name: "Presença" })).toBeNull();
  });
});
