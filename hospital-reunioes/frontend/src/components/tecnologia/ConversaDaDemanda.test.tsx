/**
 * @vitest-environment jsdom
 */

/**
 * A Conversa da Demanda (issue #1537, PRD #1529, ADR 0083, decisão 8).
 *
 * A área própria, embaixo da conversa com a IA, em que o diretor e os
 * Desenvolvedores trocam mensagens. A menção é por nome, no formato dos
 * comentários de Pendência: "@" abre a lista de quem vê a Demanda, e o
 * clique escreve "@Nome Completo " no texto. Quem decide quem é avisado é o
 * servidor.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConversaDaDemanda } from "./ConversaDaDemanda";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const URL = "/api/admin/tecnologia/chat/d-1/conversa";

const GUARDADA = {
  mensagens: [
    { id: "m-1", autor: "Diretor do Hospital", texto: "O relatório sumiu de novo.", criado_em: "2026-11-10T10:00:00Z", minha: true },
  ],
  mencionaveis: [
    { id: "P2", nome: "Diretor do Hospital" },
    { id: "P4", nome: "Lucas Sampaio" },
    { id: "P1", nome: "Pedro Vitta" },
  ],
};

type Chamada = { url: string; metodo: string; corpo: unknown };

function montar() {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      const corpo = init?.body ? JSON.parse(String(init.body)) : null;
      chamadas.push({ url, metodo, corpo });
      const resposta =
        metodo === "POST"
          ? { id: "m-2", autor: "Diretor do Hospital", texto: corpo.texto, criado_em: "2026-11-10T10:05:00Z", minha: true }
          : GUARDADA;
      return { ok: true, status: metodo === "POST" ? 201 : 200, json: async () => resposta } as unknown as Response;
    }),
  );
  render(<ConversaDaDemanda demandaId="d-1" token="token-de-teste" />);
  return chamadas;
}

function area() {
  return screen.getByRole("region", { name: "Conversa da Demanda" });
}

describe("A Conversa da Demanda", () => {
  it("mostra as mensagens com quem escreveu e envia uma nova", async () => {
    const chamadas = montar();

    await within(area()).findByText("O relatório sumiu de novo.");
    expect(within(area()).getByText("Diretor do Hospital")).toBeTruthy();

    fireEvent.change(within(area()).getByRole("textbox", { name: "Mensagem para a Conversa" }), {
      target: { value: "Aconteceu de novo agora." },
    });
    fireEvent.click(within(area()).getByRole("button", { name: "Enviar na Conversa" }));

    await within(area()).findByText("Aconteceu de novo agora.");
    expect(chamadas.filter((c) => c.metodo === "POST")).toEqual([
      { url: URL, metodo: "POST", corpo: { texto: "Aconteceu de novo agora." } },
    ]);
  });

  it("o @ abre a lista de quem vê a Demanda e o clique escreve o nome inteiro", async () => {
    const chamadas = montar();
    await within(area()).findByText("O relatório sumiu de novo.");
    const caixa = within(area()).getByRole("textbox", { name: "Mensagem para a Conversa" }) as HTMLTextAreaElement;

    fireEvent.change(caixa, { target: { value: "Olha isso @luc", selectionStart: 14 } });
    fireEvent.click(await within(area()).findByRole("option", { name: "Lucas Sampaio" }));

    expect(caixa.value).toBe("Olha isso @Lucas Sampaio ");
    fireEvent.click(within(area()).getByRole("button", { name: "Enviar na Conversa" }));
    await waitFor(() =>
      expect(chamadas.filter((c) => c.metodo === "POST").map((c) => c.corpo)).toEqual([
        { texto: "Olha isso @Lucas Sampaio" },
      ]),
    );
  });
});

/**
 * O Envio aos desenvolvedores (issue #2011, ADR 0108, decisões 3 a 5): o
 * botão só para quem não é Desenvolvedor (o servidor manda `envio` nulo para
 * ele), desligado sem mensagem nova; o "Entendi assim:" com Enviar e
 * Corrigir; a linha do envio na conversa; a falha com o motivo e "Tente de
 * novo".
 */
describe("O Envio aos desenvolvedores", () => {
  const ENTENDI = {
    id: "e-1",
    topicos: ["A enfermagem imprime a escala sem pedir ajuda."],
    cards: [{ numero: 901, muda: "A parte da escala ganha o botão de imprimir." }],
  };
  const LINHA = {
    id: "m-9",
    autor: "Diretor do Hospital",
    texto: "Enviado aos desenvolvedores em 19/11/2026, às 14:32:\n- A enfermagem imprime a escala sem pedir ajuda.",
    criado_em: "2026-11-19T17:32:00Z",
    minha: true,
    sistema: true,
  };

  type Resposta = { ok: boolean; status: number; corpo: unknown };

  function montarEnvio(envio: unknown, respostas: Record<string, Resposta[]> = {}) {
    const chamadas: Chamada[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const metodo = init?.method ?? "GET";
        const corpo = init?.body ? JSON.parse(String(init.body)) : null;
        chamadas.push({ url, metodo, corpo });
        let r: Resposta;
        if (metodo === "GET") r = { ok: true, status: 200, corpo: { ...GUARDADA, envio } };
        else if (url === URL)
          r = {
            ok: true,
            status: 201,
            corpo: {
              id: "m-2",
              autor: "Diretor do Hospital",
              texto: corpo.texto,
              criado_em: null,
              minha: true,
              sistema: false,
            },
          };
        else r = respostas[url]?.shift() ?? { ok: false, status: 500, corpo: {} };
        return {
          ok: r.ok,
          status: r.status,
          json: async () => r.corpo,
        } as unknown as Response;
      }),
    );
    render(<ConversaDaDemanda demandaId="d-1" token="token-de-teste" />);
    return chamadas;
  }

  const botaoDoEnvio = () =>
    within(area()).getByRole("button", {
      name: "Enviar para os desenvolvedores",
    });

  it("não aparece para o Desenvolvedor", async () => {
    montarEnvio(null);
    await within(area()).findByText("O relatório sumiu de novo.");
    expect(
      within(area()).queryByRole("button", {
        name: "Enviar para os desenvolvedores",
      }),
    ).toBeNull();
  });

  it("fica desligado sem mensagem nova e liga com a mensagem que o diretor escreve", async () => {
    montarEnvio({ mensagens_novas: 0 });
    await within(area()).findByText("O relatório sumiu de novo.");
    expect((botaoDoEnvio() as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(within(area()).getByRole("textbox", { name: "Mensagem para a Conversa" }), {
      target: { value: "Mais uma coisa." },
    });
    fireEvent.click(within(area()).getByRole("button", { name: "Enviar na Conversa" }));

    await within(area()).findByText("Mais uma coisa.");
    expect((botaoDoEnvio() as HTMLButtonElement).disabled).toBe(false);
  });

  it("mostra o Entendi assim e o Enviar põe a linha do envio na conversa e desliga o botão", async () => {
    const chamadas = montarEnvio(
      { mensagens_novas: 1 },
      {
        [`${URL}/interpretar`]: [{ ok: true, status: 200, corpo: ENTENDI }],
        [`${URL}/enviar`]: [{ ok: true, status: 200, corpo: LINHA }],
      },
    );
    await within(area()).findByText("O relatório sumiu de novo.");

    fireEvent.click(botaoDoEnvio());
    const painel = await within(area()).findByRole("group", {
      name: "Entendi assim:",
    });
    expect(within(painel).getByText("A enfermagem imprime a escala sem pedir ajuda.")).toBeTruthy();

    fireEvent.click(within(painel).getByRole("button", { name: "Enviar" }));

    await within(area()).findByText(/Enviado aos desenvolvedores em 19\/11\/2026, às 14:32/);
    expect(within(area()).queryByRole("group", { name: "Entendi assim:" })).toBeNull();
    expect((botaoDoEnvio() as HTMLButtonElement).disabled).toBe(true);
    expect(chamadas.filter((c) => c.url === `${URL}/enviar`).map((c) => c.corpo)).toEqual([{ envio_id: "e-1" }]);
  });

  it("a mensagem escrita com o Entendi assim aberto fica para o próximo envio e o botão segue ligado", async () => {
    montarEnvio(
      { mensagens_novas: 1 },
      {
        [`${URL}/interpretar`]: [{ ok: true, status: 200, corpo: ENTENDI }],
        [`${URL}/enviar`]: [{ ok: true, status: 200, corpo: LINHA }],
      },
    );
    await within(area()).findByText("O relatório sumiu de novo.");

    fireEvent.click(botaoDoEnvio());
    const painel = await within(area()).findByRole("group", {
      name: "Entendi assim:",
    });
    fireEvent.change(within(area()).getByRole("textbox", { name: "Mensagem para a Conversa" }), {
      target: { value: "Esqueci de dizer a ala." },
    });
    fireEvent.click(within(area()).getByRole("button", { name: "Enviar na Conversa" }));
    await within(area()).findByText("Esqueci de dizer a ala.");

    fireEvent.click(within(painel).getByRole("button", { name: "Enviar" }));

    await within(area()).findByText(/Enviado aos desenvolvedores em 19\/11\/2026, às 14:32/);
    expect((botaoDoEnvio() as HTMLButtonElement).disabled).toBe(false);
  });

  it("o Corrigir fecha o painel, volta ao campo e não envia nada", async () => {
    const chamadas = montarEnvio(
      { mensagens_novas: 1 },
      { [`${URL}/interpretar`]: [{ ok: true, status: 200, corpo: ENTENDI }] },
    );
    await within(area()).findByText("O relatório sumiu de novo.");

    fireEvent.click(botaoDoEnvio());
    const painel = await within(area()).findByRole("group", {
      name: "Entendi assim:",
    });
    fireEvent.click(within(painel).getByRole("button", { name: "Corrigir" }));

    expect(within(area()).queryByRole("group", { name: "Entendi assim:" })).toBeNull();
    expect(document.activeElement).toBe(within(area()).getByRole("textbox", { name: "Mensagem para a Conversa" }));
    expect(chamadas.some((c) => c.url === `${URL}/enviar`)).toBe(false);
  });

  it("a falha mostra o motivo e o Tente de novo envia sem perder o Entendi assim", async () => {
    const chamadas = montarEnvio(
      { mensagens_novas: 1 },
      {
        [`${URL}/interpretar`]: [{ ok: true, status: 200, corpo: ENTENDI }],
        [`${URL}/enviar`]: [
          {
            ok: false,
            status: 502,
            corpo: {
              detail: "O desenvolvimento não respondeu, e nada foi enviado.",
            },
          },
          { ok: true, status: 200, corpo: LINHA },
        ],
      },
    );
    await within(area()).findByText("O relatório sumiu de novo.");
    fireEvent.click(botaoDoEnvio());
    const painel = await within(area()).findByRole("group", {
      name: "Entendi assim:",
    });
    fireEvent.click(within(painel).getByRole("button", { name: "Enviar" }));

    expect((await within(area()).findByRole("alert")).textContent).toContain("O desenvolvimento não respondeu");
    expect(within(painel).getByText("A enfermagem imprime a escala sem pedir ajuda.")).toBeTruthy();
    fireEvent.click(within(area()).getByRole("button", { name: "Tente de novo" }));

    await within(area()).findByText(/Enviado aos desenvolvedores em 19\/11\/2026/);
    expect(chamadas.filter((c) => c.url === `${URL}/enviar`)).toHaveLength(2);
  });
});
