/**
 * @vitest-environment jsdom
 */

/**
 * A pauta de uma reunião do Núcleo (issue #1773, PRD #1764).
 *
 * O servidor monta a pauta, decide o prazo e quem é convocado; a tela mostra
 * os blocos com a situação de cada pendência, deixa a Presidência editar e
 * convocar, e mostra a recusa do prazo antes do clique. Pessoas de teste, sem
 * nome real.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PautaDaReuniao, type Pauta } from "./PautaDaReuniao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const ROTA = "/api/nsp/reunioes/RD_1";

function pauta(campos: Partial<Pauta> = {}): Pauta {
  return {
    id_reuniao: "RD_1",
    disponivel: true,
    disponivel_em: "2027-03-08",
    blocos: [
      {
        chave: "pendencias",
        titulo: "Pendências da reunião anterior",
        sem_dados: false,
        itens: [{ texto: "Revisar o protocolo de quedas.", id_acao: "PA1", situacao: "Atrasada" }],
      },
      { chave: "indicadores", titulo: "Indicadores", sem_dados: true, itens: [] },
    ],
    editada_em: null,
    pode_editar: false,
    convocacao: null,
    pode_convocar: false,
    recusa_da_convocacao: null,
    ...campos,
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

function responder(corpo: object, status = 200) {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

function chamadas(metodo: string) {
  return fetchMock.mock.calls.filter(([, init]) => (init?.method ?? "GET") === metodo);
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a pauta montada pelo sistema", () => {
  it("antes do dia, diz quando a pauta aparece", async () => {
    fetchMock.mockResolvedValue(responder(pauta({ disponivel: false, blocos: [] })));
    render(<PautaDaReuniao idReuniao="RD_1" />);

    expect(await screen.findByText(/A pauta aparece em 08\/03\/2027/)).toBeTruthy();
    expect(fetchMock.mock.calls[0][0]).toBe(`${ROTA}/pauta`);
  });

  it("mostra a pendência com a situação de hoje e o bloco sem dados da fase", async () => {
    fetchMock.mockResolvedValue(responder(pauta()));
    render(<PautaDaReuniao idReuniao="RD_1" />);

    const pendencias = await screen.findByRole("region", { name: "Pendências da reunião anterior" });
    expect(within(pendencias).getByText("Revisar o protocolo de quedas.")).toBeTruthy();
    expect(within(pendencias).getByText("Atrasada")).toBeTruthy();
    const indicadores = screen.getByRole("region", { name: "Indicadores" });
    expect(within(indicadores).getByText("Sem dados nesta fase.")).toBeTruthy();
  });

  it("quem não edita não vê os botões da Presidência", async () => {
    fetchMock.mockResolvedValue(responder(pauta()));
    render(<PautaDaReuniao idReuniao="RD_1" />);

    await screen.findByText("Revisar o protocolo de quedas.");
    expect(screen.queryByRole("button", { name: "Editar a pauta" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Convocar os membros" })).toBeNull();
  });
});

describe("a Presidência edita e convoca", () => {
  it("edita um item, inclui outro e salva a pauta inteira", async () => {
    fetchMock.mockImplementation(async (_rota: string, init?: RequestInit) =>
      init?.method === "PUT" ? responder({ id_reuniao: "RD_1", blocos: [] }) : responder(pauta({ pode_editar: true })),
    );
    render(<PautaDaReuniao idReuniao="RD_1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Editar a pauta" }));
    fireEvent.change(screen.getByLabelText("Item 1 de Pendências da reunião anterior"), {
      target: { value: "Revisar o protocolo de quedas com a enfermagem." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Incluir item em Indicadores" }));
    fireEvent.change(screen.getByLabelText("Item 1 de Indicadores"), { target: { value: "Taxa de quedas" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar a pauta" }));

    await waitFor(() => expect(chamadas("PUT")).toHaveLength(1));
    const [rota, init] = chamadas("PUT")[0];
    expect(rota).toBe(`${ROTA}/pauta`);
    const corpo = JSON.parse(init.body);
    expect(corpo.blocos[0].itens).toEqual([
      { texto: "Revisar o protocolo de quedas com a enfermagem.", id_acao: "PA1", situacao: "Atrasada" },
    ]);
    expect(corpo.blocos[1]).toMatchObject({ titulo: "Indicadores", sem_dados: false, itens: [{ texto: "Taxa de quedas" }] });
  });

  it("convoca em um clique e mostra quem foi convocado", async () => {
    let convocou = false;
    fetchMock.mockImplementation(async (_rota: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        convocou = true;
        return responder({ convocados: [] }, 201);
      }
      return responder(
        convocou
          ? pauta({
              convocacao: {
                convocada_em: "2027-03-08T13:00:00+00:00",
                convocados: [
                  { participante_id: "P1", nome: "Pessoa de Teste P1", estado: "ativo", email_enviado: true },
                  { participante_id: "P2", nome: "Pessoa de Teste P2", estado: "a_vencer", email_enviado: false },
                ],
              },
            })
          : pauta({ pode_convocar: true }),
      );
    });
    render(<PautaDaReuniao idReuniao="RD_1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Convocar os membros" }));

    expect(await screen.findByText("Convocada em 08/03/2027, 2 pessoas:")).toBeTruthy();
    expect(screen.getByText("Pessoa de Teste P1")).toBeTruthy();
    expect(screen.getByText("Pessoa de Teste P2 (e-mail não enviado)")).toBeTruthy();
    expect(chamadas("POST")[0][0]).toBe(`${ROTA}/convocacao`);
  });

  it("fora do prazo, mostra a recusa e não deixa clicar", async () => {
    const recusa = "A reunião ordinária precisa ser convocada com 5 dias úteis de antecedência.";
    fetchMock.mockResolvedValue(responder(pauta({ pode_convocar: true, recusa_da_convocacao: recusa })));
    render(<PautaDaReuniao idReuniao="RD_1" />);

    const botao = (await screen.findByRole("button", { name: "Convocar os membros" })) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
    expect(screen.getByText(recusa)).toBeTruthy();
  });

  it("a recusa do servidor no clique aparece na tela", async () => {
    fetchMock.mockImplementation(async (_rota: string, init?: RequestInit) =>
      init?.method === "POST"
        ? responder({ detail: "A reunião extraordinária precisa ser convocada com pelo menos 24 horas de antecedência." }, 422)
        : responder(pauta({ pode_convocar: true })),
    );
    render(<PautaDaReuniao idReuniao="RD_1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Convocar os membros" }));

    expect(
      await screen.findByText("A reunião extraordinária precisa ser convocada com pelo menos 24 horas de antecedência."),
    ).toBeTruthy();
  });
});
