/**
 * @vitest-environment jsdom
 */

/**
 * O link pessoal das Pendências (issue #1878): a pessoa que nunca entrou no
 * aplicativo vê as pendências dela e age sempre com anotação; o link vencido
 * ou cancelado mostra a frase do servidor.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import MinhasPendenciasPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "tok-bruno" }),
}));

const DADOS = {
  pessoa: "Bruno Reis",
  pendencias: [
    {
      id_acao: "A1",
      descricao: "Trocar o monitor do leito 4",
      reuniao: "Reunião da UTI",
      prazo: "2026-11-24",
      situacao: "PENDENTE",
      acoes: ["iniciar", "anotar", "concluir", "repactuar"],
    },
  ],
};

function resposta(status: number, corpo: unknown): Response {
  return { ok: status < 400, status, json: async () => corpo } as unknown as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("link pessoal das pendências, tela sem senha", () => {
  it("mostra as pendências da pessoa e só confirma a ação com anotação", async () => {
    const depois = { ...DADOS, pendencias: [] };
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) =>
      init?.method === "POST" ? resposta(200, depois) : resposta(200, DADOS),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<MinhasPendenciasPage />);

    expect(await screen.findByText("Trocar o monitor do leito 4")).toBeTruthy();
    expect(screen.getByText(/Reunião da UTI\. Prazo: 24\/11\/2026\. Pendente\./)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Concluir" }));
    const confirmar = screen.getByRole("button", { name: /Confirmar: Concluir/ }) as HTMLButtonElement;
    expect(confirmar.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/Anotação/), { target: { value: "  " } });
    expect(confirmar.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText(/Anotação/), { target: { value: "Monitor trocado." } });
    expect(confirmar.disabled).toBe(false);
    fireEvent.click(confirmar);

    await screen.findByText("Pendência concluída.");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(post?.[0]).toBe("/api/minhas-pendencias/tok-bruno/pendencias/A1/acoes");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      comando: "concluir",
      anotacao: "Monitor trocado.",
      prazo: null,
    });
    expect(await screen.findByText("Você não tem pendências em aberto.")).toBeTruthy();
  });

  it("repactuar pede o prazo novo além da anotação", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => resposta(200, DADOS)),
    );
    render(<MinhasPendenciasPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Repactuar" }));
    fireEvent.change(screen.getByLabelText(/Anotação/), { target: { value: "Atrasou a entrega." } });
    const confirmar = screen.getByRole("button", { name: /Confirmar: Repactuar/ }) as HTMLButtonElement;
    expect(confirmar.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Prazo novo"), { target: { value: "2026-11-30" } });
    expect(confirmar.disabled).toBe(false);
  });

  it("link vencido mostra a frase do servidor", async () => {
    const frase = "Este link venceu. O e-mail de segunda traz um link novo toda semana.";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => resposta(410, { detail: frase })),
    );

    render(<MinhasPendenciasPage />);

    await waitFor(() => expect(screen.getByText(frase)).toBeTruthy());
    expect(screen.queryByRole("button")).toBeNull();
  });
});
