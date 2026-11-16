/**
 * @vitest-environment jsdom
 */

/**
 * A ata do Núcleo em dez blocos (issue #1775, PRD #1764).
 *
 * A tela mostra os dez blocos, com os do sistema marcados. Quem conduz a ata
 * (o servidor diz quem) revisa os blocos do agente e valida; o membro comum só
 * lê. Quando a minuta foi descartada, a tela avisa e já abre para a
 * Presidência redigir. Pessoas de teste, sem nome real.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AtaDoNucleo, type LeituraDaAta } from "./AtaDoNucleo";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const ID = "RD_20261210_1";
const ROTA = `/api/nsp/reunioes/${ID}/ata`;

const AVISO = "A IA escreveu nome de membro fora da lista de presença duas vezes, e a minuta foi descartada.";

function leitura(campos: Partial<LeituraDaAta> = {}, ata: Partial<NonNullable<LeituraDaAta["ata"]>> = {}): LeituraDaAta {
  return {
    id_reuniao: ID,
    status_ata: "AGUARDANDO_VALIDACAO",
    pode_conduzir: true,
    ata: {
      modelo: "nsp_dez_blocos",
      resumida: false,
      aviso: null,
      trechos_a_conferir: [],
      deliberacoes: [{ texto: "Treinar as equipes", responsavel: "Coordenação de Enfermagem", prazo: "2027-01-15" }],
      blocos: [
        { chave: "identificacao", titulo: "Identificação", origem: "sistema", itens: ["Data: 10/12/2026."] },
        { chave: "presencas_e_quorum", titulo: "Presenças e quórum", origem: "sistema", itens: ["Presentes: Pessoa A."] },
        {
          chave: "deliberacoes",
          titulo: "Deliberações",
          origem: "agente",
          itens: ["Treinar as equipes. Responsável: Coordenação de Enfermagem; prazo: 15/01/2027."],
        },
        { chave: "plano_de_acao", titulo: "Plano de ação", origem: "agente", itens: ["Revisar a sinalização"] },
      ],
      ...ata,
    },
    ...campos,
  };
}

let fetchMock: ReturnType<typeof vi.fn>;

function responder(corpo: object, status = 200) {
  return new Response(JSON.stringify(corpo), { status, headers: { "Content-Type": "application/json" } });
}

function chamadas(metodo: string, url: string) {
  return fetchMock.mock.calls.filter(([u, init]) => u === url && ((init?.method as string) ?? "GET") === metodo);
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a ata do Núcleo", () => {
  it("mostra os blocos e marca os que vêm do sistema", async () => {
    fetchMock.mockImplementation(async () => responder(leitura()));
    render(<AtaDoNucleo idReuniao={ID} />);

    expect(await screen.findByText("Presentes: Pessoa A.")).toBeTruthy();
    expect(screen.getAllByText("do sistema")).toHaveLength(2);
    expect(screen.getByText("Revisar a sinalização")).toBeTruthy();
  });

  it("o membro comum só lê: sem revisar nem validar", async () => {
    fetchMock.mockImplementation(async () => responder(leitura({ pode_conduzir: false })));
    render(<AtaDoNucleo idReuniao={ID} />);

    expect(await screen.findByText("A Presidência revisa e valida esta ata.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Validar a ata/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Revisar/ })).toBeNull();
  });

  it("com a minuta descartada, avisa e já abre para a Presidência redigir", async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === ROTA && init?.method === "PUT") return responder({ id_reuniao: ID });
      return responder(leitura({}, { aviso: AVISO }));
    });
    render(<AtaDoNucleo idReuniao={ID} />);

    expect((await screen.findByRole("alert")).textContent).toContain(AVISO);
    const plano = screen.getByRole("textbox", { name: "Plano de ação" });
    fireEvent.change(plano, { target: { value: "Primeira ação\nSegunda ação" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar a revisão" }));

    await waitFor(() => expect(chamadas("PUT", ROTA)).toHaveLength(1));
    const corpo = JSON.parse(chamadas("PUT", ROTA)[0][1].body as string);
    expect(corpo.blocos.plano_de_acao).toEqual(["Primeira ação", "Segunda ação"]);
    expect(corpo.deliberacoes[0].responsavel).toBe("Coordenação de Enfermagem");
  });

  it("validar chama o servidor e mostra a recusa quando falta prazo", async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === `${ROTA}/validar` && init?.method === "POST") {
        return responder({ detail: "Complete antes de validar: a deliberação 1 está sem prazo." }, 422);
      }
      return responder(leitura());
    });
    render(<AtaDoNucleo idReuniao={ID} />);

    fireEvent.click(await screen.findByRole("button", { name: /Validar a ata/ }));

    expect(await screen.findByText("Complete antes de validar: a deliberação 1 está sem prazo.")).toBeTruthy();
    expect(chamadas("POST", `${ROTA}/validar`)).toHaveLength(1);
  });

  it("a apresentação à Diretoria mostra a ata resumida", async () => {
    fetchMock.mockImplementation(async () => responder(leitura({}, { resumida: true })));
    render(<AtaDoNucleo idReuniao={ID} />);

    expect(await screen.findByRole("heading", { name: "Ata resumida do Núcleo" })).toBeTruthy();
  });
});
