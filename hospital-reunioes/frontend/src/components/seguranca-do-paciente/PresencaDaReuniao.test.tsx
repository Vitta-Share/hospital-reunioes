/**
 * @vitest-environment jsdom
 */

/**
 * A presença e o quórum da reunião do Núcleo (issue #1774, PRD #1764).
 *
 * A Presidência marca presente, ausente, ausente justificado ou convidado para
 * cada pessoa; quem apura o quórum é o servidor, e a tela mostra o resultado.
 * Sem quórum, a tela pede a nova data e registra a reunião como não instalada.
 * Pessoas de teste, sem nome real.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PresencaDaReuniao, type Apuracao } from "./PresencaDaReuniao";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

const ID = "RD_20261210_1";
const ROTA = `/api/nsp/reunioes/${ID}/presenca`;

const SEM_QUORUM = { total: 5, presentes: 2, minimo: 3, presidencia_ou_suplente: true, instalada: false };
const COM_QUORUM = { total: 5, presentes: 3, minimo: 3, presidencia_ou_suplente: true, instalada: true };

function apuracao(campos: Partial<Apuracao> = {}): Apuracao {
  return {
    id_reuniao: ID,
    data: "2026-12-10",
    status_ata: "PROGRAMADA",
    pessoas: [
      { participante_id: "PRES1", nome: "Pessoa Presidência", papel: "presidencia", conta_para_quorum: true, situacao: null },
      { participante_id: "MEMB1", nome: "Pessoa Membro", papel: "membro", conta_para_quorum: true, situacao: null },
    ],
    quorum: SEM_QUORUM,
    pode_registrar: true,
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

describe("o registro da presença", () => {
  it("cada pessoa tem as quatro situações e salvar manda a presença ao servidor", async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === ROTA && init?.method === "PUT") {
        return responder(apuracao({ quorum: COM_QUORUM }));
      }
      return responder(apuracao());
    });
    render(<PresencaDaReuniao idReuniao={ID} />);

    const presidencia = await screen.findByRole("combobox", { name: "Presença de Pessoa Presidência" });
    const opcoes = within(presidencia)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(opcoes).toEqual(["Sem registro", "Presente", "Ausente", "Ausente justificado", "Convidado"]);
    fireEvent.change(presidencia, { target: { value: "presente" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Presença de Pessoa Membro" }), {
      target: { value: "ausente_justificado" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar presença" }));

    await waitFor(() => expect(chamadas("PUT", ROTA)).toHaveLength(1));
    expect(JSON.parse(chamadas("PUT", ROTA)[0][1].body as string)).toEqual({
      presencas: [
        { participante_id: "PRES1", situacao: "presente" },
        { participante_id: "MEMB1", situacao: "ausente_justificado" },
      ],
    });
    expect(await screen.findByText("Reunião instalada: 3 presentes de 5, mínimo de 3.")).toBeTruthy();
  });

  it("a Presidência acrescenta um convidado de fora do Núcleo", async () => {
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === "/api/nsp/membros/pessoas") {
        return responder({ pessoas: [{ id: "CONV1", nome: "Pessoa Convidada" }] });
      }
      if (url === ROTA && init?.method === "PUT") return responder(apuracao());
      return responder(apuracao());
    });
    render(<PresencaDaReuniao idReuniao={ID} />);

    const escolha = await screen.findByRole("combobox", { name: "Acrescentar convidado" });
    await screen.findByRole("option", { name: "Pessoa Convidada" });
    fireEvent.change(escolha, { target: { value: "CONV1" } });
    fireEvent.click(screen.getByRole("button", { name: "Acrescentar" }));
    const linha = screen.getByRole("combobox", { name: "Presença de Pessoa Convidada" }) as HTMLSelectElement;
    expect(linha.value).toBe("convidado");
    fireEvent.click(screen.getByRole("button", { name: "Salvar presença" }));

    await waitFor(() => expect(chamadas("PUT", ROTA)).toHaveLength(1));
    expect(JSON.parse(chamadas("PUT", ROTA)[0][1].body as string).presencas).toEqual([
      { participante_id: "CONV1", situacao: "convidado" },
    ]);
  });

  it("quem só lê vê a presença registrada, sem poder mudar", async () => {
    const pessoas = apuracao().pessoas.map((p) => ({ ...p, situacao: "presente" as const }));
    fetchMock.mockImplementation(async () => responder(apuracao({ pessoas, pode_registrar: false })));
    render(<PresencaDaReuniao idReuniao={ID} />);

    expect(await screen.findAllByText("Presente")).toHaveLength(2);
    expect(screen.queryByRole("combobox")).toBeNull();
    expect(screen.queryByRole("button", { name: "Salvar presença" })).toBeNull();
  });
});

describe("o quórum e a reunião não instalada", () => {
  it("antes de registrar a presença, não oferece o reagendamento", async () => {
    fetchMock.mockImplementation(async () => responder(apuracao()));
    render(<PresencaDaReuniao idReuniao={ID} />);

    await screen.findByText("Sem quórum: 2 presentes de 5, mínimo de 3.");
    expect(screen.queryByRole("button", { name: "Registrar como não instalada e reagendar" })).toBeNull();
  });

  it("sem quórum, pede a nova data e registra a reunião como não instalada", async () => {
    const mudou = vi.fn();
    const registrada = apuracao().pessoas.map((p) => ({ ...p, situacao: "ausente" as const }));
    fetchMock.mockImplementation(async (url: string) => {
      if (url === `/api/nsp/reunioes/${ID}/nao-instalada`) {
        return responder({ id_reuniao: ID, status: "NAO_INSTALADA", reagendada: { id_reuniao: "RD_2", data: "2026-12-20" } }, 201);
      }
      return responder(apuracao({ pessoas: registrada }));
    });
    render(<PresencaDaReuniao idReuniao={ID} onMudou={mudou} />);

    expect(await screen.findByText("Sem quórum: 2 presentes de 5, mínimo de 3.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Nova data"), { target: { value: "2026-12-20" } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar como não instalada e reagendar" }));

    await waitFor(() => expect(chamadas("POST", `/api/nsp/reunioes/${ID}/nao-instalada`)).toHaveLength(1));
    expect(JSON.parse(chamadas("POST", `/api/nsp/reunioes/${ID}/nao-instalada`)[0][1].body as string)).toEqual({
      data: "2026-12-20",
      hora_inicio: null,
    });
    await waitFor(() => expect(mudou).toHaveBeenCalled());
  });

  it("sem a Presidência nem o suplente, a tela diz o motivo", async () => {
    const quorum = { ...COM_QUORUM, presidencia_ou_suplente: false, instalada: false };
    fetchMock.mockImplementation(async () => responder(apuracao({ quorum })));
    render(<PresencaDaReuniao idReuniao={ID} />);

    expect(await screen.findByText("Falta a Presidência ou o suplente presente.")).toBeTruthy();
  });

  it("com quórum, não oferece o reagendamento", async () => {
    fetchMock.mockImplementation(async () => responder(apuracao({ quorum: COM_QUORUM })));
    render(<PresencaDaReuniao idReuniao={ID} />);

    expect(await screen.findByText("Reunião instalada: 3 presentes de 5, mínimo de 3.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar como não instalada e reagendar" })).toBeNull();
  });
});
