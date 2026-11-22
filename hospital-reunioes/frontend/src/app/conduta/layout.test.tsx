/**
 * @vitest-environment jsdom
 */

/**
 * A página pública do Canal de Conduta e a chave de abertura (issue #1843,
 * ADR 0097, decisão 11): fechado o canal, a página responde 404.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const naoEncontrado = new Error("NEXT_NOT_FOUND");
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw naoEncontrado;
  },
}));

import { MolduraDoCanal } from "@/components/conduta/publico/MolduraDoCanal";

import CanalDeCondutaLayout from "./layout";
import CanalDeCondutaPage from "./page";

let perguntas: string[];

function backend(resposta: () => Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      perguntas.push(url);
      return resposta();
    })
  );
}

beforeEach(() => {
  perguntas = [];
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("a chave de abertura", () => {
  it("desligada (a rota de abertura responde 404), a página responde 404", async () => {
    backend(() => new Response('{"detail":"Not Found"}', { status: 404 }));

    await expect(CanalDeCondutaLayout({ children: "relato" })).rejects.toBe(naoEncontrado);
    expect(perguntas).toHaveLength(1);
    expect(perguntas[0]).toMatch(/\/conduta\/abertura$/);
  });

  it("sem resposta do backend, o canal fica fechado", async () => {
    backend(() => {
      throw new TypeError("fetch failed");
    });

    await expect(CanalDeCondutaLayout({ children: "relato" })).rejects.toBe(naoEncontrado);
  });

  it("ligada, a página abre", async () => {
    backend(() => new Response('{"aberto":true}', { status: 200 }));

    // Aberta, a tela vai dentro da moldura do canal (logo e rodapé, issue #1846).
    const tela = await CanalDeCondutaLayout({ children: "relato" });
    expect(tela.type).toBe(MolduraDoCanal);
    expect(tela.props.children).toBe("relato");
  });
});

describe("o canal aberto com a tela do relato", () => {
  it("mostra o logo uma vez só e um <main> só, na entrada e nos passos (issue #1846)", async () => {
    backend(() => new Response('{"aberto":true,"textos":{}}', { status: 200 }));

    render(await CanalDeCondutaLayout({ children: <CanalDeCondutaPage /> }));
    // O rodapé só aparece depois que a moldura confirma o canal aberto: daí
    // em diante o logo da moldura está na tela.
    await screen.findByRole("contentinfo");

    expect(screen.getAllByRole("img", { name: "Hospital São Matheus" })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Fazer relato" }));
    await screen.findByRole("heading", { name: "Antes de começar" });

    expect(screen.getAllByRole("img", { name: "Hospital São Matheus" })).toHaveLength(1);
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });
});
