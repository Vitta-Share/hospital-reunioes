/**
 * @vitest-environment jsdom
 */

/**
 * A página "Como este canal protege você" (issue #1846, PRD #1786).
 *
 * Mostra os textos vigentes das Configurações, o contato do encarregado de
 * dados quando ele está preenchido, e abre as versões arquivadas pela data. O
 * backend é um dublê que responde por rota. Textos de teste.
 */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PaginaDeProtecao } from "./PaginaDeProtecao";

const ROTA = "/api/conduta/protecao";

function bloco(chave: string, titulo: string, texto: string, versao: number | null = null) {
  return { chave, titulo, texto, versao, versao_id: versao ? `${chave}-v${versao}` : null };
}

function pagina(campos: Record<string, unknown> = {}) {
  return {
    em: null,
    blocos: [
      bloco("protecao_abertura", "Frase de abertura", "Este canal é do hospital, frase de teste."),
      bloco("protecao_quem_le", "Quem lê e quem não lê", "Leem os três membros do Comitê, texto de teste.", 2),
      bloco("protecao_prazos", "Prazos", "Leitura em até 3 dias úteis."),
    ],
    encarregado: null,
    versoes: ["2026-11-15", "2026-11-10"],
    ...campos,
  };
}

let chamadas: { url: string; init?: RequestInit }[] = [];
let respostas: Record<string, { status: number; corpo: unknown }> = {};

beforeEach(() => {
  chamadas = [];
  respostas = { [ROTA]: { status: 200, corpo: pagina() } };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      chamadas.push({ url, init });
      const r = respostas[url] ?? { status: 404, corpo: { detail: "Not Found" } };
      return new Response(JSON.stringify(r.corpo), { status: r.status });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PaginaDeProtecao", () => {
  it("mostra os textos vigentes das Configurações, bloco a bloco", async () => {
    render(<PaginaDeProtecao />);

    expect(await screen.findByRole("heading", { level: 1, name: "Como este canal protege você" })).toBeTruthy();
    expect(screen.getByText("Este canal é do hospital, frase de teste.")).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2, name: "Quem lê e quem não lê" })).toBeTruthy();
    expect(screen.getByText("Leem os três membros do Comitê, texto de teste.")).toBeTruthy();
    expect(screen.getByText("Leitura em até 3 dias úteis.")).toBeTruthy();
    // A frase de abertura é a frase, não um bloco com título.
    expect(screen.queryByRole("heading", { name: "Frase de abertura" })).toBeNull();
  });

  it("lê sem cookie nem token de login", async () => {
    render(<PaginaDeProtecao />);
    await screen.findByText("Leitura em até 3 dias úteis.");

    expect(chamadas).toHaveLength(1);
    expect(chamadas[0].url).toBe(ROTA);
    expect(chamadas[0].init?.credentials).toBe("omit");
    expect(new Headers(chamadas[0].init?.headers).has("Authorization")).toBe(false);
  });

  it("sem o contato do encarregado de dados, o bloco não aparece", async () => {
    render(<PaginaDeProtecao />);
    await screen.findByText("Leitura em até 3 dias úteis.");

    expect(screen.queryByRole("heading", { name: /encarregado de dados/i })).toBeNull();
  });

  it("mostra o contato do encarregado de dados configurado", async () => {
    respostas[ROTA] = {
      status: 200,
      corpo: pagina({ encarregado: { texto: "Encarregada de Teste, ramal 2041", versao: 1, versao_id: "e-v1" } }),
    };

    render(<PaginaDeProtecao />);

    expect(await screen.findByRole("heading", { level: 2, name: /encarregado de dados/i })).toBeTruthy();
    expect(screen.getByText("Encarregada de Teste, ramal 2041")).toBeTruthy();
  });

  it("abre a versão arquivada de uma data", async () => {
    respostas[`${ROTA}?em=2026-11-10`] = {
      status: 200,
      corpo: pagina({
        em: "2026-11-10",
        blocos: [bloco("protecao_prazos", "Prazos", "Leitura em até 5 dias úteis.", 1)],
      }),
    };
    render(<PaginaDeProtecao />);
    await screen.findByText("Leitura em até 3 dias úteis.");

    fireEvent.click(screen.getByRole("button", { name: "10/11/2026" }));

    expect(await screen.findByText("Leitura em até 5 dias úteis.")).toBeTruthy();
    expect(screen.getByText(/Versão arquivada de 10\/11\/2026/)).toBeTruthy();
    expect(screen.queryByText("Leitura em até 3 dias úteis.")).toBeNull();
  });

  it("com o canal fechado diz que a página não existe", async () => {
    respostas[ROTA] = { status: 404, corpo: { detail: "Not Found" } };

    render(<PaginaDeProtecao />);

    expect(await screen.findByText("Página não encontrada.")).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole("heading", { level: 1 })).toBeNull());
  });

  it("não usa as palavras independente, 100% nem risco zero no que a tela escreve", async () => {
    respostas[ROTA] = { status: 200, corpo: pagina({ blocos: [], versoes: [] }) };
    const { container } = render(<PaginaDeProtecao />);
    await screen.findByRole("heading", { level: 1 });

    expect(container.textContent).not.toMatch(/independent|100\s*%|risco\s+zero/i);
  });
});
