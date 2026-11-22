/**
 * A página pública do Canal de Conduta e a chave de abertura (issue #1843,
 * ADR 0097, decisão 11): fechado o canal, a página responde 404.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const naoEncontrado = new Error("NEXT_NOT_FOUND");
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw naoEncontrado;
  },
}));

import CanalDeCondutaLayout from "./layout";

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

    await expect(CanalDeCondutaLayout({ children: "relato" })).resolves.toBe("relato");
  });
});
