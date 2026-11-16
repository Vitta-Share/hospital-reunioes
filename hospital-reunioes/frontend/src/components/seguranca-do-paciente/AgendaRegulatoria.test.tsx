/**
 * @vitest-environment jsdom
 */

/**
 * A Agenda regulatória do Núcleo (issue #1779, PRD #1764).
 *
 * A tela não decide nada: quem edita é o servidor que diz (`pode_editar`), e a
 * próxima data depois do resultado vem dele. O que se trava aqui é o que a
 * pessoa vê (evento, periodicidade, próxima data, link, último resultado) e o
 * que cada botão da Presidência manda para a API.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgendaRegulatoria, type EventoDaAgenda } from "./AgendaRegulatoria";

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token-de-teste" } } }),
    },
  }),
}));

function evento(campos: Partial<EventoDaAgenda>): EventoDaAgenda {
  return {
    id: "e-1",
    evento: "Reunião ordinária",
    periodicidade: "mensal",
    regra: null,
    proxima_data: "2026-12-10",
    link: null,
    antecedencia_dias: 7,
    ativo: true,
    historico: [],
    ...campos,
  };
}

const LISTA: EventoDaAgenda[] = [
  evento({
    id: "notificacao",
    evento: "Notificação externa do mês",
    regra: "Até o 15º dia útil",
    proxima_data: "2026-12-21",
    link: "https://www.gov.br/anvisa",
    historico: [
      {
        data_prevista: "2026-11-20",
        resultado: "Enviada no sistema da vigilância",
        realizada_em: "2026-11-18",
        registrado_por: "p1",
        registrado_em: "2026-11-18T12:00:00+00:00",
      },
    ],
  }),
  evento({ id: "cultura", evento: "Avaliação da cultura de segurança", periodicidade: "bienal", proxima_data: null }),
  evento({ id: "antigo", evento: "Evento desativado", ativo: false }),
];

let chamadas: { url: string; metodo: string; corpo: unknown }[] = [];
let podeEditar = true;

beforeEach(() => {
  chamadas = [];
  podeEditar = true;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const metodo = init?.method ?? "GET";
      chamadas.push({ url, metodo, corpo: init?.body ? JSON.parse(String(init.body)) : undefined });
      const corpo = metodo === "GET" ? { itens: LISTA, pode_editar: podeEditar } : { id: "x" };
      return new Response(JSON.stringify(corpo), { status: 200, headers: { "Content-Type": "application/json" } });
    })
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function cartao(nome: string): Promise<HTMLElement> {
  return (await screen.findByRole("heading", { name: nome })).closest("li") as HTMLElement;
}

describe("o que a pessoa vê", () => {
  it("cada evento com a periodicidade, a próxima data, o link e o último resultado", async () => {
    render(<AgendaRegulatoria />);

    const notificacao = within(await cartao("Notificação externa do mês"));
    expect(notificacao.getByText("Mensal, até o 15º dia útil")).toBeTruthy();
    expect(notificacao.getByText("21/12/2026")).toBeTruthy();
    expect(notificacao.getByRole("link", { name: "Abrir o link" }).getAttribute("href")).toBe(
      "https://www.gov.br/anvisa"
    );
    expect(notificacao.getByText("Enviada no sistema da vigilância")).toBeTruthy();
    expect(notificacao.getByText(/18\/11\/2026/)).toBeTruthy();

    const cultura = within(await cartao("Avaliação da cultura de segurança"));
    expect(cultura.getByText("A cada dois anos")).toBeTruthy();
    expect(cultura.getByText("Sem data marcada")).toBeTruthy();
  });

  it("o evento desativado aparece marcado", async () => {
    render(<AgendaRegulatoria />);

    expect(within(await cartao("Evento desativado")).getByText("Desativado")).toBeTruthy();
  });

  it("quem não é da Presidência só lê", async () => {
    podeEditar = false;
    render(<AgendaRegulatoria />);

    await cartao("Notificação externa do mês");
    expect(screen.queryByRole("button", { name: "Incluir evento" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Registrar resultado" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Desativar" })).toBeNull();
  });
});

describe("o que a Presidência faz", () => {
  it("registra o resultado com a data em que foi feito", async () => {
    render(<AgendaRegulatoria />);
    const notificacao = within(await cartao("Notificação externa do mês"));

    fireEvent.click(notificacao.getByRole("button", { name: "Registrar resultado" }));
    fireEvent.change(notificacao.getByLabelText("Resultado"), { target: { value: "Enviada" } });
    fireEvent.change(notificacao.getByLabelText("Feito em"), { target: { value: "2026-12-15" } });
    fireEvent.click(notificacao.getByRole("button", { name: "Registrar" }));

    await waitFor(() => expect(chamadas.some((c) => c.metodo === "POST")).toBe(true));
    const post = chamadas.find((c) => c.metodo === "POST")!;
    expect(post.url).toBe("/api/nsp/agenda/notificacao/resultado");
    expect(post.corpo).toEqual({ resultado: "Enviada", realizada_em: "2026-12-15" });
    await waitFor(() => expect(chamadas.filter((c) => c.metodo === "GET")).toHaveLength(2));
  });

  it("desativa e reativa um evento", async () => {
    render(<AgendaRegulatoria />);

    fireEvent.click(within(await cartao("Notificação externa do mês")).getByRole("button", { name: "Desativar" }));
    fireEvent.click(within(await cartao("Evento desativado")).getByRole("button", { name: "Reativar" }));

    await waitFor(() => expect(chamadas.filter((c) => c.metodo === "PATCH")).toHaveLength(2));
    const [desativar, reativar] = chamadas.filter((c) => c.metodo === "PATCH");
    expect(desativar).toEqual({ url: "/api/nsp/agenda/notificacao", metodo: "PATCH", corpo: { ativo: false } });
    expect(reativar).toEqual({ url: "/api/nsp/agenda/antigo", metodo: "PATCH", corpo: { ativo: true } });
  });

  it("edita a próxima data e o link de um evento", async () => {
    render(<AgendaRegulatoria />);
    const cultura = within(await cartao("Avaliação da cultura de segurança"));

    fireEvent.click(cultura.getByRole("button", { name: "Editar" }));
    fireEvent.change(cultura.getByLabelText("Próxima data"), { target: { value: "2027-08-01" } });
    fireEvent.change(cultura.getByLabelText("Link"), { target: { value: "https://exemplo.gov.br" } });
    fireEvent.click(cultura.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(chamadas.some((c) => c.metodo === "PATCH")).toBe(true));
    const patch = chamadas.find((c) => c.metodo === "PATCH")!;
    expect(patch.url).toBe("/api/nsp/agenda/cultura");
    expect(patch.corpo).toMatchObject({ proxima_data: "2027-08-01", link: "https://exemplo.gov.br" });
  });

  it("inclui um evento novo", async () => {
    render(<AgendaRegulatoria />);
    await cartao("Notificação externa do mês");

    fireEvent.click(screen.getByRole("button", { name: "Incluir evento" }));
    const formulario = within(screen.getByRole("form", { name: "Novo evento" }));
    fireEvent.change(formulario.getByLabelText("Evento"), { target: { value: "Inspeção da vigilância" } });
    fireEvent.change(formulario.getByLabelText("Periodicidade"), { target: { value: "anual" } });
    fireEvent.click(formulario.getByRole("button", { name: "Salvar" }));

    await waitFor(() => expect(chamadas.some((c) => c.metodo === "POST")).toBe(true));
    const post = chamadas.find((c) => c.metodo === "POST")!;
    expect(post.url).toBe("/api/nsp/agenda");
    expect(post.corpo).toMatchObject({ evento: "Inspeção da vigilância", periodicidade: "anual" });
  });
});
