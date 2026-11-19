/**
 * A raiz do site sem a capa (issue #1942, ADR 0104 decisão 1).
 *
 * Quem decide a raiz é o middleware (testado em `middleware.test.ts`). Esta
 * página é a rede de baixo: se a requisição chegar até ela, a pessoa segue
 * para o Início, cujo layout manda ao login quem não tem sessão. A capa com
 * os dois botões não volta a aparecer.
 */
import { describe, expect, it, vi } from "vitest";

const redirect = vi.fn((destino: string) => {
  throw new Error(`redirect:${destino}`);
});

vi.mock("next/navigation", () => ({
  redirect: (destino: string) => redirect(destino),
}));

import Raiz from "./page";

describe("a raiz do site", () => {
  it("leva ao Início em vez de mostrar a capa", () => {
    expect(() => Raiz()).toThrow("redirect:/inicio");
  });
});
