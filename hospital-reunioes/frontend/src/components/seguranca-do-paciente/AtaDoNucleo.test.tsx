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

// A assinatura dos presentes e o encerramento (issue #1776).
describe("a ata do Núcleo depois da validação", () => {
  const VALIDACAO = { por: "PRES1", em: "2026-11-18T15:00:00-03:00" };

  it("enviada, diz que espera a assinatura dos presentes e quando encerra", async () => {
    fetchMock.mockImplementation(async () =>
      responder(
        leitura(
          { status_ata: "AGUARDANDO_ASSINATURA" },
          { validacao: VALIDACAO, assinatura: { enviada_em: "2026-11-18T15:00:00-03:00", erro: null } },
        ),
      ),
    );
    render(<AtaDoNucleo idReuniao={ID} />);

    expect(await screen.findByText(/Enviada em 18\/11\/2026 para a assinatura dos presentes/)).toBeTruthy();
    expect(screen.getByText(/encerra sozinha 5 dias úteis depois do envio/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Validar a ata/ })).toBeNull();
  });

  it("validada e não enviada, mostra o aviso da assinatura eletrônica", async () => {
    const erro = "A assinatura eletrônica não respondeu. O aplicativo tenta de novo amanhã.";
    fetchMock.mockImplementation(async () =>
      responder(leitura({ status_ata: "APROVADA" }, { validacao: VALIDACAO, assinatura: { erro } })),
    );
    render(<AtaDoNucleo idReuniao={ID} />);

    expect((await screen.findByRole("alert")).textContent).toContain(erro);
  });

  it("encerrada, baixa a ata assinada pela rota do Núcleo", async () => {
    const abrir = vi.fn();
    vi.stubGlobal("open", abrir);
    const arquivo = "/api/nsp/reunioes/atas/doc-ata-7/arquivo-assinado";
    fetchMock.mockImplementation(async (url: string) => {
      if (url === arquivo) return responder({ url: "https://storage.test/ata.pdf" });
      return responder({
        ...leitura(
          { status_ata: "ASSINADA" },
          { validacao: VALIDACAO, encerramento: { em: "2026-11-26", assinaram: [], nao_assinaram: [] } },
        ),
        documento_id: "doc-ata-7",
      });
    });
    render(<AtaDoNucleo idReuniao={ID} />);

    expect(await screen.findByText(/Encerrada em 26\/11\/2026/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Baixar a ata assinada/ }));

    await waitFor(() => expect(abrir).toHaveBeenCalledWith("https://storage.test/ata.pdf", "_blank", "noopener"));
    expect(chamadas("GET", arquivo)).toHaveLength(1);
  });

  // Envelope cancelado: recusa de um presente ou cancelamento no painel.
  const CANCELADA = "A assinatura eletrônica foi cancelada. A Presidência pode reenviar para todos os presentes.";
  const ASSINATURA_CANCELADA = { enviada_em: "2026-11-18T15:00:00-03:00", cancelada_em: "2026-11-19", erro: CANCELADA };

  it("cancelada, avisa, não promete encerrar e a Presidência reenvia", async () => {
    let cancelada = true;
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url === `${ROTA}/reenviar` && init?.method === "POST") {
        cancelada = false;
        return responder({ id_reuniao: ID, status: "AGUARDANDO_ASSINATURA" });
      }
      return responder(
        leitura(
          { status_ata: "AGUARDANDO_ASSINATURA" },
          {
            validacao: VALIDACAO,
            assinatura: cancelada
              ? ASSINATURA_CANCELADA
              : { enviada_em: "2026-11-24T10:00:00-03:00", erro: null },
          },
        ),
      );
    });
    render(<AtaDoNucleo idReuniao={ID} />);

    expect((await screen.findByRole("alert")).textContent).toContain(CANCELADA);
    expect(screen.queryByText(/encerra sozinha/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Reenviar para assinatura/ }));

    await waitFor(() => expect(chamadas("POST", `${ROTA}/reenviar`)).toHaveLength(1));
    expect(await screen.findByText(/Enviada em 24\/11\/2026 para a assinatura dos presentes/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Reenviar para assinatura/ })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("cancelada, o membro comum vê o aviso e não reenvia", async () => {
    fetchMock.mockImplementation(async () =>
      responder(
        leitura(
          { status_ata: "AGUARDANDO_ASSINATURA", pode_conduzir: false },
          { validacao: VALIDACAO, assinatura: ASSINATURA_CANCELADA },
        ),
      ),
    );
    render(<AtaDoNucleo idReuniao={ID} />);

    expect((await screen.findByRole("alert")).textContent).toContain(CANCELADA);
    expect(screen.queryByRole("button", { name: /Reenviar para assinatura/ })).toBeNull();
  });
});
